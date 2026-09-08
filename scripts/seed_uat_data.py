"""Seed representative operational records for the UAT dashboard.

Safe to run repeatedly; records are identified by the UAT model version.
This is synthetic grading data, not production telemetry.
"""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.alert.models import Alert, AlertSeverity, AlertStatus
from app.core.db import SessionLocal
from app.explainability.models import FeatureAttribution
from app.flowgard_engine.models import HealthDeviationRecord
from app.maintenance_schedule.models import ScheduledMaintenance, ScheduleStatus
from app.model_metrics.models import ModelMetric
from app.prediction.models import PredictionResult
from app.pump.models import Pump
from app.rul.models import RulEstimate
from app.station.models import Station
from app.tenant.models import Tenant
from app.user.models import User  # register master.user before ORM flush ordering
from app.work_order.models import WorkOrder, WorkOrderSource, WorkOrderStatus

VERSION = "uat-synthetic-v1"
NOW = datetime.now(UTC).replace(microsecond=0)


def seed() -> None:
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == "kpc"))
        if tenant is None:
            raise RuntimeError("Seed the tenant before seeding UAT data")
        stations = {s.id: s for s in db.scalars(select(Station).where(Station.tenant_id == tenant.id)).all()}
        pumps = list(db.scalars(select(Pump).where(Pump.tenant_id == tenant.id).order_by(Pump.tag_number)).all())
        if not pumps:
            raise RuntimeError("Seed the pump fleet before seeding UAT data")

        for index, pump in enumerate(pumps):
            station = stations[pump.station_id]
            risk = (0.07 + (index % 10) * 0.055) if index % 7 else 0.72
            hdi = round(risk * 0.78, 3)
            rul_days = max(8.0, round(180 - risk * 190, 1))
            prediction = db.scalar(select(PredictionResult).where(PredictionResult.tenant_id == tenant.id, PredictionResult.pump_id == pump.id, PredictionResult.model_version == VERSION))
            if prediction is None:
                prediction = PredictionResult(tenant_id=tenant.id, pump_id=pump.id, computed_at=NOW, predicted_class="mechanical_anomaly" if risk >= 0.5 else "normal", risk_score_7d=risk, model_version=VERSION, feature_version="uat-features-v1", data_quality="sufficient", confidence=round(0.82 - risk * 0.15, 3), rul_hours=rul_days * 24, rul_low_hours=max(24, (rul_days - 12) * 24), rul_high_hours=(rul_days + 18) * 24)
                db.add(prediction); db.flush()
            hdi_record = db.scalar(select(HealthDeviationRecord).where(HealthDeviationRecord.tenant_id == tenant.id, HealthDeviationRecord.pump_id == pump.id, HealthDeviationRecord.computed_at == NOW))
            if hdi_record is None:
                db.add(HealthDeviationRecord(tenant_id=tenant.id, pump_id=pump.id, computed_at=NOW, pressure_residual=round(risk * 42, 2), health_deviation_index=hdi))
            rul = db.scalar(select(RulEstimate).where(RulEstimate.tenant_id == tenant.id, RulEstimate.pump_id == pump.id, RulEstimate.model_version == VERSION))
            if rul is None:
                db.add(RulEstimate(tenant_id=tenant.id, pump_id=pump.id, computed_at=NOW, remaining_useful_life_days=rul_days, confidence_lower_days=max(1, rul_days - 12), confidence_upper_days=rul_days + 18, mc_dropout_samples=100, model_version=VERSION))
            attribution = db.scalar(select(FeatureAttribution).where(FeatureAttribution.tenant_id == tenant.id, FeatureAttribution.pump_id == pump.id, FeatureAttribution.model_version == VERSION))
            if attribution is None:
                values = {"vibration": round(0.25 + risk * 0.4, 3), "pressure residual": round(0.18 + risk * 0.25, 3), "temperature": round(0.12 + risk * 0.15, 3)}
                db.add(FeatureAttribution(tenant_id=tenant.id, pump_id=pump.id, computed_at=NOW, shap_values=values, component_scores={"bearing": values["vibration"], "seal": values["pressure residual"], "motor": values["temperature"]}, top_component=max(values, key=values.get), model_version=VERSION))
            if risk >= 0.5:
                alert = db.scalar(select(Alert).where(Alert.tenant_id == tenant.id, Alert.pump_id == pump.id, Alert.source == VERSION))
                if alert is None:
                    db.add(Alert(tenant_id=tenant.id, pump_id=pump.id, station_id=station.id, severity=AlertSeverity.CRITICAL, status=AlertStatus.TRIGGERED, message=f"{pump.tag_number} shows elevated predictive failure risk", triggered_at=NOW - timedelta(hours=index + 1), source=VERSION))
                work = db.scalar(select(WorkOrder).where(WorkOrder.tenant_id == tenant.id, WorkOrder.pump_id == pump.id, WorkOrder.source_prediction_id == prediction.id))
                if work is None:
                    work = WorkOrder(tenant_id=tenant.id, pump_id=pump.id, station_id=station.id, source_prediction_id=prediction.id, title=f"Inspect {pump.tag_number} bearing and seal", description="UAT work order generated from the predictive risk signal.", status=WorkOrderStatus.OPEN if index % 2 else WorkOrderStatus.IN_PROGRESS, source=WorkOrderSource.ALERT, priority="high", due_at=NOW + timedelta(days=max(2, int(rul_days / 10))))
                    db.add(work); db.flush()
                scheduled = db.scalar(select(ScheduledMaintenance).where(ScheduledMaintenance.tenant_id == tenant.id, ScheduledMaintenance.pump_id == pump.id, ScheduledMaintenance.created_from == VERSION))
                if scheduled is None:
                    db.add(ScheduledMaintenance(tenant_id=tenant.id, pump_id=pump.id, station_id=station.id, work_order_id=work.id, scheduled_date=date.today() + timedelta(days=max(2, int(rul_days / 10))), priority_rank=index + 1, status=ScheduleStatus.PLANNED, created_from=VERSION))
        metrics = (("classification_accuracy", 0.91), ("classification_sensitivity", 0.88), ("rul_mae_hours", 18.4))
        for name, value in metrics:
            existing = db.scalar(select(ModelMetric).where(ModelMetric.tenant_id == tenant.id, ModelMetric.model_version == VERSION, ModelMetric.metric_name == name))
            if existing is None:
                db.add(ModelMetric(tenant_id=tenant.id, model_name="flowgard", model_version=VERSION, dataset_split="uat", metric_name=name, metric_value=value, confusion_matrix={"matrix": [[42, 4], [6, 48]]} if name == "classification_accuracy" else None, evaluated_at=NOW))
        db.commit()
        print(f"Seeded UAT operational records for {len(pumps)} pumps")


if __name__ == "__main__":
    seed()
