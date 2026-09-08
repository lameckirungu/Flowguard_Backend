import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.etl.silver.models import SensorReading
from app.explainability.models import FeatureAttribution
from app.flowgard_engine.models import HealthDeviationRecord
from app.model_metrics.models import ModelMetric
from app.operations.schemas import (
    DashboardSummary,
    ModelSummary,
    PumpHealth,
    SensorSnapshot,
    ShapFeature,
    StationStatus,
)
from app.prediction.models import PredictionResult
from app.pump.models import Pump
from app.rul.models import RulEstimate
from app.station.models import Station


def _latest(db: Session, model, tenant_id: uuid.UUID, pump_id: uuid.UUID, order_column):
    return db.scalar(
        select(model)
        .where(model.tenant_id == tenant_id, model.pump_id == pump_id)
        .order_by(order_column.desc())
        .limit(1)
    )


def _pump_health(db: Session, tenant_id: uuid.UUID, pump: Pump, station: Station) -> PumpHealth:
    prediction = _latest(db, PredictionResult, tenant_id, pump.id, PredictionResult.computed_at)
    hdi = _latest(db, HealthDeviationRecord, tenant_id, pump.id, HealthDeviationRecord.computed_at)
    rul = _latest(db, RulEstimate, tenant_id, pump.id, RulEstimate.computed_at)
    attribution = _latest(
        db, FeatureAttribution, tenant_id, pump.id, FeatureAttribution.computed_at
    )
    sensor = _latest(db, SensorReading, tenant_id, pump.id, SensorReading.recorded_at)

    shap = []
    if attribution:
        shap = [
            ShapFeature(feature=name, value=float(value))
            for name, value in sorted(
                attribution.shap_values.items(), key=lambda item: abs(float(item[1])), reverse=True
            )
        ]
    computed_candidates = [
        value
        for value in (
            prediction.computed_at if prediction else None,
            hdi.computed_at if hdi else None,
            rul.computed_at if rul else None,
            attribution.computed_at if attribution else None,
        )
        if value is not None
    ]
    return PumpHealth(
        id=pump.id,
        pump_id=pump.tag_number,
        station_id=station.id,
        station_code=station.code,
        station_name=station.name,
        risk_probability=float(prediction.risk_score_7d or 0) if prediction else 0,
        predicted_class=prediction.predicted_class if prediction else None,
        health_deviation_index=float(hdi.health_deviation_index or 0) if hdi else 0,
        sensors=SensorSnapshot(
            vibration_g=float(sensor.vibration_g)
            if sensor and sensor.vibration_g is not None
            else None,
            vibration_mm_s=(
                float(sensor.vibration_mm_s)
                if sensor and sensor.vibration_mm_s is not None
                else None
            ),
            temperature_c=(
                float(sensor.temperature_c) if sensor and sensor.temperature_c is not None else None
            ),
            pressure_kpa=float(sensor.pressure_kpa)
            if sensor and sensor.pressure_kpa is not None
            else None,
            motor_current_a=(
                float(sensor.motor_current_a)
                if sensor and sensor.motor_current_a is not None
                else None
            ),
            recorded_at=sensor.recorded_at if sensor else None,
        ),
        rul_days=float(rul.remaining_useful_life_days)
        if rul and rul.remaining_useful_life_days is not None
        else None,
        rul_ci_low_days=float(rul.confidence_lower_days)
        if rul and rul.confidence_lower_days is not None
        else None,
        rul_ci_high_days=float(rul.confidence_upper_days)
        if rul and rul.confidence_upper_days is not None
        else None,
        shap_top_features=shap,
        component_states={
            key: float(value)
            for key, value in (attribution.component_scores if attribution else {}).items()
        },
        computed_at=max(computed_candidates) if computed_candidates else None,
    )


def list_pump_health(db: Session, tenant_id: uuid.UUID) -> list[PumpHealth]:
    stations = {
        station.id: station
        for station in db.scalars(select(Station).where(Station.tenant_id == tenant_id)).all()
    }
    pumps = db.scalars(select(Pump).where(Pump.tenant_id == tenant_id)).all()
    return [_pump_health(db, tenant_id, pump, stations[pump.station_id]) for pump in pumps]


def model_summary(db: Session, tenant_id: uuid.UUID) -> ModelSummary:
    rows = db.scalars(
        select(ModelMetric)
        .where(ModelMetric.tenant_id == tenant_id)
        .order_by(ModelMetric.evaluated_at.desc())
    ).all()
    latest_by_name = {}
    for row in rows:
        latest_by_name.setdefault(row.metric_name, row)
    accuracy = latest_by_name.get("classification_accuracy")
    sensitivity = latest_by_name.get("classification_sensitivity")
    rul_mae = latest_by_name.get("rul_mae_hours")
    representative = accuracy or sensitivity or rul_mae
    matrix = accuracy.confusion_matrix if accuracy and accuracy.confusion_matrix else None
    if isinstance(matrix, dict):
        matrix = matrix.get("matrix")
    return ModelSummary(
        classification_accuracy=float(accuracy.metric_value) if accuracy else None,
        classification_sensitivity=float(sensitivity.metric_value) if sensitivity else None,
        confusion_matrix=matrix,
        rul_mae_hours=float(rul_mae.metric_value) if rul_mae else None,
        model_version=representative.model_version if representative else None,
        evaluated_at=representative.evaluated_at if representative else None,
    )


def dashboard(db: Session, tenant_id: uuid.UUID) -> DashboardSummary:
    pump_health = list_pump_health(db, tenant_id)
    station_rows = db.scalars(
        select(Station).where(Station.tenant_id == tenant_id).order_by(Station.code)
    ).all()
    statuses = []
    for station in station_rows:
        station_pumps = [pump for pump in pump_health if pump.station_id == station.id]
        max_risk = max((pump.risk_probability for pump in station_pumps), default=0)
        statuses.append(
            StationStatus(
                id=station.id,
                code=station.code,
                name=station.name,
                lat=float(station.latitude) if station.latitude is not None else None,
                lon=float(station.longitude) if station.longitude is not None else None,
                pump_count=len(station_pumps),
                max_risk=max_risk,
                alert=max_risk >= 0.5,
            )
        )
    generated = max((pump.computed_at for pump in pump_health if pump.computed_at), default=None)
    latest_sensor = max(
        (pump.sensors.recorded_at for pump in pump_health if pump.sensors.recorded_at),
        default=None,
    )
    if settings.data_mode == "demo_snapshot":
        freshness_status = "demo"
    elif generated is None and latest_sensor is None:
        freshness_status = "unavailable"
    else:
        from datetime import UTC, datetime
        latest = max(value for value in (generated, latest_sensor) if value is not None)
        age = (datetime.now(UTC) - latest).total_seconds()
        freshness_status = "fresh" if age <= settings.telemetry_freshness_seconds else "stale"
    rul_values = [pump.rul_days for pump in pump_health if pump.rul_days is not None]
    return DashboardSummary(
        generated_at=generated,
        station_count=len(statuses),
        pump_count=len(pump_health),
        critical_count=sum(pump.risk_probability >= 0.5 for pump in pump_health),
        watch_count=sum(0.15 <= pump.risk_probability < 0.5 for pump in pump_health),
        healthy_count=sum(pump.risk_probability < 0.15 for pump in pump_health),
        earliest_rul_days=min(rul_values) if rul_values else None,
        stations=statuses,
        pumps=sorted(pump_health, key=lambda pump: pump.risk_probability, reverse=True),
        model_metrics=model_summary(db, tenant_id),
        data_provenance="backend",
        data_mode=settings.data_mode,
        freshness_status=freshness_status,
        latest_sensor_at=latest_sensor,
        latest_prediction_at=generated,
        synthetic_data=settings.data_mode != "operational",
    )
