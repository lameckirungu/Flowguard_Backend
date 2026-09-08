import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.alert.models import AlertSeverity, AlertStatus


class Deadline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acknowledge_minutes: int = Field(ge=1, le=43200)
    response_minutes: int = Field(ge=1, le=43200)

    @model_validator(mode="after")
    def ordered(self):
        if self.response_minutes < self.acknowledge_minutes:
            raise ValueError("Response deadline must not precede acknowledgement")
        return self


class PolicyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    critical: Deadline
    warning: Deadline
    info: Deadline


class IncidentFilters(BaseModel):
    status: AlertStatus | None = None
    severity: AlertSeverity | None = None
    owner_id: uuid.UUID | None = None
    unassigned: bool = False
    overdue: bool = False
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 25
