"""Idempotently bootstrap the KPC demo from the prototype SNAP dataset.

The snapshot may be supplied as JSON or as the frontend's generated
data/mockData.ts file. Credentials come from environment settings only.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.alert.models import Alert, AlertSeverity
from app.core.auth import hash_password
from app.core.config import settings
from app.core.db import SessionLocal
from app.etl.silver.models import SensorReading
from app.explainability.models import FeatureAttribution
from app.flowgard_engine.models import HealthDeviationRecord
from app.maintenance_schedule.models import ScheduledMaintenance
from app.model_metrics.models import ModelMetric
from app.prediction.models import PredictionResult
from app.pump.models import Pump
from app.rul.models import RulEstimate
from app.station.models import Station
from app.tenant.models import Tenant
from app.user.models import User, UserRole
from app.work_order.models import WorkOrder, WorkOrderSource


def load_snapshot(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    marker = "export const SNAP"
    start = text.index("{", text.index(marker))
    end_marker = ";\n\nexport const stations"
    end = text.index(end_marker, start)
    return json.loads(text[start:end])


def utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=parsed.tzinfo or UTC)


def get_or_create_tenant(db) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == "kpc"))
    if tenant:
        return tenant
    tenant = Tenant(
        name="Kenya Pipeline Company",
        slug="kpc",
        fluid_type="petroleum_products",
        pressure_threshold_kpa=4500,
        vibration_threshold_mm_s=7.1,
        branding_display_name="KPC",
        branding_primary_color="#006633",
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def bootstrap(snapshot: dict) -> None:
    generated_at = utc(snapshot["generated_at"])
    with SessionLocal() as db:
        tenant = get_or_create_tenant(db)
        station_by_code: dict[str, Station] = {}
        for source in snapshot["stations"]:
            station = db.scalar(
                select(Station).where(
                    Station.tenant_id == tenant.id, Station.code == source["code"]
                )
            )
            if station is None:
                station = Station(
                    tenant_id=tenant.id,
                    code=source["code"],
                    name=source["name"],
                    latitude=source["lat"],
                    longitude=source["lon"],
                    commissioned_on=date(1994, 1, 1),
                )
                db.add(station)
                db.flush()
            else:
                station.name = source["name"]
                station.latitude = source["lat"]
                station.longitude = source["lon"]
            station_by_code[station.code] = station
        db.commit()

        for source in snapshot["pumps"]:
            station = station_by_code[source["station_code"]]
            pump = db.scalar(
                select(Pump).where(
                    Pump.tenant_id == tenant.id, Pump.tag_number == source["pump_id"]
                )
            )
            if pump is None:
                pump = Pump(
                    tenant_id=tenant.id,
                    station_id=station.id,
                    tag_number=source["pump_id"],
                    manufacturer="Demo asset",
                    model_number="Prototype snapshot",
                    install_date=date(1994, 1, 1),
                    design_life_years=25,
                    rated_pressure_kpa=500,
                )
                db.add(pump)
                db.flush()

            exists = db.scalar(
                select(PredictionResult).where(
                    PredictionResult.tenant_id == tenant.id,
                    PredictionResult.pump_id == pump.id,
                    PredictionResult.model_version == "prototype-snapshot",
                )
            )
            if exists:
                continue
            sensors = source["sensors"]
            db.add(
                SensorReading(
                    tenant_id=tenant.id,
                    pump_id=pump.id,
                    recorded_at=generated_at,
                    vibration_g=sensors.get("vibration_g"),
                    temperature_c=sensors.get("temperature_c"),
                    pressure_kpa=(sensors.get("pressure_bar") or 0) * 100,
                    motor_current_a=sensors.get("motor_current_a"),
                )
            )
            db.add(
                HealthDeviationRecord(
                    tenant_id=tenant.id,
                    pump_id=pump.id,
                    computed_at=generated_at,
                    health_deviation_index=source["health_deviation_index"],
                )
            )
            predicted_class = source.get("actual_failure_mode") or (
                "normal" if source["risk_probability"] < 0.15 else "mechanical_anomaly"
            )
            db.add(
                PredictionResult(
                    tenant_id=tenant.id,
                    pump_id=pump.id,
                    computed_at=generated_at,
                    predicted_class=predicted_class,
                    risk_score_7d=source["risk_probability"],
                    model_version="prototype-snapshot",
                )
            )
            if source.get("rul_hours") is not None:
                db.add(
                    RulEstimate(
                        tenant_id=tenant.id,
                        pump_id=pump.id,
                        computed_at=generated_at,
                        remaining_useful_life_days=source["rul_hours"] / 24,
                        confidence_lower_days=source["rul_ci_low"] / 24,
                        confidence_upper_days=source["rul_ci_high"] / 24,
                        model_version="prototype-snapshot",
                    )
                )
            shap_values = {item["feature"]: item["value"] for item in source["shap_top_features"]}
            components = {key: value for key, value in source["component_states"].items()}
            db.add(
                FeatureAttribution(
                    tenant_id=tenant.id,
                    pump_id=pump.id,
                    computed_at=generated_at,
                    shap_values=shap_values,
                    component_scores=components,
                    top_component=max(components, key=components.get),
                    model_version="prototype-snapshot",
                )
            )
            if source["risk_probability"] >= 0.15:
                severity = (
                    AlertSeverity.CRITICAL
                    if source["risk_probability"] >= 0.5
                    else AlertSeverity.WARNING
                )
                db.add(
                    Alert(
                        tenant_id=tenant.id,
                        pump_id=pump.id,
                        station_id=station.id,
                        severity=severity,
                        message=f"{source['pump_id']} exceeds the demo risk threshold",
                        triggered_at=generated_at,
                        source="prototype-snapshot",
                    )
                )
                due_at = generated_at + timedelta(
                    days=(source.get("rul_ci_low") or source.get("rul_hours") or 168) / 24
                )
                work_order = WorkOrder(
                    tenant_id=tenant.id,
                    pump_id=pump.id,
                    station_id=station.id,
                    title=f"Inspect {max(components, key=components.get).title()}",
                    description="Imported from the model-backed prototype snapshot.",
                    source=WorkOrderSource.ALERT,
                    priority="high" if severity == AlertSeverity.CRITICAL else "normal",
                    due_at=due_at,
                )
                db.add(work_order)
                db.flush()
                db.add(
                    ScheduledMaintenance(
                        tenant_id=tenant.id,
                        pump_id=pump.id,
                        station_id=station.id,
                        work_order_id=work_order.id,
                        scheduled_date=due_at.date(),
                        created_from="prototype-snapshot",
                    )
                )
            db.commit()

        metrics = snapshot["model_metrics"]
        for name, value in (
            ("classification_accuracy", metrics["classification_accuracy"]),
            ("classification_sensitivity", metrics["classification_sensitivity"]),
            ("rul_mae_hours", metrics["rul_mae_hours"]),
        ):
            existing = db.scalar(
                select(ModelMetric).where(
                    ModelMetric.tenant_id == tenant.id,
                    ModelMetric.model_version == "prototype-snapshot",
                    ModelMetric.metric_name == name,
                )
            )
            if existing is None:
                db.add(
                    ModelMetric(
                        tenant_id=tenant.id,
                        model_name="flowgard",
                        model_version="prototype-snapshot",
                        dataset_split="test",
                        metric_name=name,
                        metric_value=value,
                        confusion_matrix=(
                            {"matrix": metrics["confusion_matrix"]}
                            if name == "classification_accuracy"
                            else None
                        ),
                        evaluated_at=generated_at,
                    )
                )

        demo_users = (
            (
                settings.seed_admin_email,
                settings.seed_admin_password,
                "Flowgard Administrator",
                UserRole.ADMIN,
            ),
            (
                settings.seed_planner_email,
                settings.seed_planner_password,
                "Maintenance Planner",
                UserRole.PLANNER,
            ),
            (
                settings.seed_technician_email,
                settings.seed_technician_password,
                "Field Technician",
                UserRole.TECHNICIAN,
            ),
            (
                settings.seed_viewer_email,
                settings.seed_viewer_password,
                "Operations Viewer",
                UserRole.VIEWER,
            ),
        )
        legacy_users = db.scalars(
            select(User).where(User.email.in_(("admin.local", "legacy-admin.com")))
        ).all()
        for legacy_user in legacy_users:
            legacy_user.email = "legacy-admin.com"
            legacy_user.is_active = False

        for email, password, full_name, role in demo_users:
            if not email or not password:
                continue
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                db.add(
                    User(
                        tenant_id=tenant.id,
                        email=email,
                        hashed_password=hash_password(password),
                        full_name=full_name,
                        role=role,
                    )
                )
            else:
                user.tenant_id = tenant.id
                user.full_name = full_name
                user.role = role
                user.is_active = True
                user.hashed_password = hash_password(password)
        db.commit()
        pump_count = len(db.scalars(select(Pump).where(Pump.tenant_id == tenant.id)).all())
        print(f"Bootstrapped KPC demo: {len(station_by_code)} stations, {pump_count} pumps")


if __name__ == "__main__":
    snapshot_path = Path(os.environ.get("DEMO_SNAPSHOT_PATH", "../flowgard-web/data/mockData.ts"))
    bootstrap(load_snapshot(snapshot_path))
