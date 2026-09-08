import uuid
from datetime import datetime

from pydantic import BaseModel


class SensorSnapshot(BaseModel):
    vibration_g: float | None = None
    vibration_mm_s: float | None = None
    temperature_c: float | None = None
    pressure_kpa: float | None = None
    motor_current_a: float | None = None
    recorded_at: datetime | None = None


class ShapFeature(BaseModel):
    feature: str
    value: float


class PumpHealth(BaseModel):
    id: uuid.UUID
    pump_id: str
    station_id: uuid.UUID
    station_code: str
    station_name: str
    risk_probability: float
    predicted_class: str | None = None
    health_deviation_index: float
    sensors: SensorSnapshot
    rul_days: float | None = None
    rul_ci_low_days: float | None = None
    rul_ci_high_days: float | None = None
    shap_top_features: list[ShapFeature]
    component_states: dict[str, float]
    computed_at: datetime | None = None


class StationStatus(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    lat: float | None = None
    lon: float | None = None
    pump_count: int
    max_risk: float
    alert: bool


class ModelSummary(BaseModel):
    classification_accuracy: float | None = None
    classification_sensitivity: float | None = None
    confusion_matrix: list[list[int]] | None = None
    rul_mae_hours: float | None = None
    model_version: str | None = None
    evaluated_at: datetime | None = None


class DashboardSummary(BaseModel):
    generated_at: datetime | None = None
    station_count: int
    pump_count: int
    critical_count: int
    watch_count: int
    healthy_count: int
    earliest_rul_days: float | None = None
    stations: list[StationStatus]
    pumps: list[PumpHealth]
    model_metrics: ModelSummary
    data_provenance: str = "backend"
    data_mode: str = "demo_snapshot"
    freshness_status: str = "demo"
    latest_sensor_at: datetime | None = None
    latest_prediction_at: datetime | None = None
    synthetic_data: bool = True


class Capabilities(BaseModel):
    dashboard: bool = True
    assets: bool = True
    demo_analytics: bool = True
    live_telemetry: bool = False
    live_rul: bool = False
    automatic_alerts: bool = True
    automatic_scheduling: bool = True
    smtp_digest: bool = False
    admin_console: bool = True
    data_mode: str = "demo_snapshot"
