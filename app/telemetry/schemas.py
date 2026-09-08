import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.telemetry.models import ConnectorStatus, TelemetryStatus


class TelemetryEnvelope(BaseModel):
    asset_key: str = Field(min_length=1, max_length=120)
    asset_type: str = Field(default="pump", max_length=40)
    observed_at: datetime
    received_at: datetime | None = None
    measurement: str = Field(min_length=1, max_length=80)
    value: float | None = None
    unit: str = Field(min_length=1, max_length=30)
    source_event_id: str = Field(min_length=1, max_length=250)
    schema_version: str = "1"


class ConnectorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    connector_type: str = "rest"
    configuration: dict = Field(default_factory=dict)


class ConnectorUpdate(BaseModel):
    enabled: bool | None = None
    configuration: dict | None = None


class ConnectorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    connector_type: str
    status: ConnectorStatus
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str | None = None


class TelemetryIngestResponse(BaseModel):
    accepted: int
    rejected: int
    duplicates: int
    quarantined: int
    connector_id: uuid.UUID


class IngestionSummary(BaseModel):
    connector_id: uuid.UUID
    connector_name: str
    status: ConnectorStatus
    received: int
    accepted: int
    rejected: int
    duplicates: int
    latest_observed_at: datetime | None = None
    latest_received_at: datetime | None = None
    freshness_status: str


class TelemetryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    asset_key: str
    measurement: str
    observed_at: datetime
    received_at: datetime
    value: float | None
    unit: str
    status: TelemetryStatus
    reason_code: str | None
