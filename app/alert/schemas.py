"""Pydantic v2 request/response models for the alert module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.alert.models import AlertSeverity, AlertStatus


class AlertCreate(BaseModel):
    pump_id: uuid.UUID
    station_id: uuid.UUID
    severity: AlertSeverity
    message: str
    triggered_at: datetime
    source: str | None = None


class AlertUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: AlertStatus | None = None
    assigned_to_user_id: uuid.UUID | None = None
    resolution_note: str | None = Field(default=None, min_length=1, max_length=4000)


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    pump_id: uuid.UUID
    station_id: uuid.UUID
    severity: AlertSeverity
    status: AlertStatus
    message: str
    triggered_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    source: str | None = None
    assigned_to_user_id: uuid.UUID | None = None
    resolution_note: str | None = None
