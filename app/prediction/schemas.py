"""Pydantic v2 models for the prediction module."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PredictionResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    pump_id: uuid.UUID
    computed_at: datetime
    predicted_class: str | None = None
    risk_score_7d: float | None = None
    model_version: str | None = None
    feature_version: str | None = None
    input_watermark: datetime | None = None
    data_quality: str = "insufficient_evidence"
    confidence: float | None = None
    rul_hours: float | None = None
    rul_low_hours: float | None = None
    rul_high_hours: float | None = None
