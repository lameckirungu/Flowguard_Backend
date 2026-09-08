import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.work_order.schemas import OutcomeLabel


class ResultFilters(BaseModel):
    start: date | None = None
    end: date | None = None
    station_id: uuid.UUID | None = None
    pump_id: uuid.UUID | None = None
    outcome: OutcomeLabel | Literal["unlabelled"] | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)

    @model_validator(mode="after")
    def dates(self):
        today = datetime.now(UTC).date()
        self.end = self.end or today
        self.start = self.start or self.end - timedelta(days=29)
        if self.start > self.end or (self.end - self.start).days > 365:
            raise ValueError("Choose an ordered date range of at most 366 days")
        return self
