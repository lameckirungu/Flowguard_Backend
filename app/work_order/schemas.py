import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.work_order.models import WorkOrderSource, WorkOrderStatus

OutcomeLabel = Literal["confirmed_failure", "degraded", "no_fault_found", "preventive_only", "inconclusive"]
Condition = Literal["serviceable", "restricted", "out_of_service", "unknown"]


class WorkOrderBase(BaseModel):
    pump_id: uuid.UUID
    station_id: uuid.UUID
    title: str
    description: str | None = None
    priority: str = "normal"
    due_at: datetime | None = None


class WorkOrderCreate(WorkOrderBase):
    assigned_to_user_id: uuid.UUID | None = None
    source_alert_id: uuid.UUID | None = None
    source_prediction_id: uuid.UUID | None = None
    source: WorkOrderSource = WorkOrderSource.MANUAL


class WorkOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: WorkOrderStatus | None = None
    assigned_to_user_id: uuid.UUID | None = None
    priority: Literal["low", "normal", "high", "critical"] | None = None
    due_at: datetime | None = None
    completion_note: str | None = Field(default=None, max_length=4000)


class WorkOrderOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    completion_note: str = Field(min_length=1, max_length=4000)
    outcome: OutcomeLabel
    post_maintenance_condition: Condition
    root_cause: str | None = Field(default=None, max_length=250)
    corrective_action: str | None = Field(default=None, max_length=4000)
    downtime_minutes: int | None = Field(default=None, ge=0, le=5256000)
    follow_up_required: bool = False
    follow_up_due_at: datetime | None = None
    correction_reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def follow_up(self):
        if self.follow_up_required and self.follow_up_due_at is None:
            raise ValueError("Follow-up work requires a due date")
        if self.follow_up_due_at and self.follow_up_due_at.tzinfo is None:
            raise ValueError("Follow-up date must include a timezone")
        if not self.follow_up_required and self.follow_up_due_at:
            raise ValueError("Enable follow-up before specifying its due date")
        return self


class VerificationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    result: Literal["passed", "failed", "inconclusive"]
    note: str = Field(min_length=1, max_length=4000)
    correction_reason: str | None = Field(default=None, min_length=1, max_length=1000)


class WorkOrderRead(WorkOrderBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    status: WorkOrderStatus
    source: WorkOrderSource
    created_at: datetime
    created_by_user_id: uuid.UUID | None = None
    assigned_to_user_id: uuid.UUID | None = None
    source_alert_id: uuid.UUID | None = None
    source_prediction_id: uuid.UUID | None = None
    closed_at: datetime | None = None
    completion_note: str | None = None
    root_cause: str | None = None
    corrective_action: str | None = None
    downtime_minutes: int | None = None
    follow_up_required: bool = False
    outcome: str | None = None
    post_maintenance_condition: str | None = None
    completed_by_user_id: uuid.UUID | None = None
    verified_at: datetime | None = None
    verified_by_user_id: uuid.UUID | None = None
    verification_result: str | None = None
    verification_note: str | None = None
    follow_up_due_at: datetime | None = None
    parent_work_order_id: uuid.UUID | None = None
