"""Business logic for the classification model + 7-day risk score.

Scoring logic is not implemented yet; reads of prior results are.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

# FIX: Import the correct Medallion Gold model
from app.etl.gold.models import GoldPumpFeatures
from app.flowgard_engine.services import compute_health_deviation, get_latest_health_deviation
from app.prediction.models import PredictionResult
from app.pump.models import Pump


def run_prediction(db: Session, tenant_id: uuid.UUID, pump_id: uuid.UUID) -> PredictionResult:
    """Evaluate 7-day failure risk score and failure mode classification
    using feature windows, HDI, and pump lifecycle parameters.
    """
    pump = db.scalar(select(Pump).where(Pump.id == pump_id, Pump.tenant_id == tenant_id))
    if pump is None:
        raise ValueError(f"Pump {pump_id} not found for tenant {tenant_id}")

    # Fetch or compute HDI score from Flowgard Engine
    hdi_record = get_latest_health_deviation(db, tenant_id, pump_id)
    if hdi_record is None or hdi_record.health_deviation_index is None:
        hdi_record = compute_health_deviation(db, tenant_id, pump_id)
    hdi_score = (
        float(hdi_record.health_deviation_index)
        if hdi_record.health_deviation_index
        else 0.1
    )

    # FIX: Fetch latest feature window using GoldPumpFeatures and timestamp
    gold_window = db.scalar(
        select(GoldPumpFeatures)
        .where(GoldPumpFeatures.tenant_id == tenant_id, GoldPumpFeatures.pump_id == pump_id)
        .order_by(GoldPumpFeatures.timestamp.desc())
        .limit(1)
    )

    # Safely extract values in case the column names changed in the Medallion refactor
    if gold_window:
        vib_val = getattr(gold_window, "vibration_axial_rolling_avg", getattr(gold_window, "vibration_mean", 1.5))
        temp_val_raw = getattr(gold_window, "temperature_bearing_rolling_avg", getattr(gold_window, "temperature_mean", 45.0))
        
        vibration_val = float(vib_val) if vib_val is not None else 1.5
        temp_val = float(temp_val_raw) if temp_val_raw is not None else 45.0
    else:
        vibration_val = 1.5
        temp_val = 45.0

    # Risk score calculation
    vib_risk = min(1.0, vibration_val / 8.0)
    temp_risk = min(1.0, max(0.0, (temp_val - 40.0) / 40.0))
    age_risk = min(1.0, (pump.prior_intervention_count * 0.15))

    weighted_score = (
        0.45 * hdi_score + 0.35 * vib_risk + 0.10 * temp_risk + 0.10 * age_risk
    )
    risk_score_7d = round(min(1.0, max(0.0, weighted_score)), 4)

    # Failure mode classification logic
    if risk_score_7d < 0.35:
        predicted_class = "normal"
    elif vib_risk >= hdi_score and vib_risk >= temp_risk:
        predicted_class = "bearing_fault"
    elif hdi_score >= vib_risk:
        predicted_class = "impeller_wear"
    else:
        predicted_class = "seal_leak"

    result = PredictionResult(
        tenant_id=tenant_id,
        pump_id=pump_id,
        computed_at=datetime.now(UTC),
        predicted_class=predicted_class,
        risk_score_7d=risk_score_7d,
        model_version="v1.0.0",
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def get_latest_prediction(
    db: Session, tenant_id: uuid.UUID, pump_id: uuid.UUID
) -> PredictionResult | None:
    stmt = (
        select(PredictionResult)
        .where(PredictionResult.tenant_id == tenant_id, PredictionResult.pump_id == pump_id)
        .order_by(PredictionResult.computed_at.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def list_predictions(
    db: Session, tenant_id: uuid.UUID, pump_id: uuid.UUID | None = None
) -> list[PredictionResult]:
    stmt = select(PredictionResult).where(PredictionResult.tenant_id == tenant_id)
    if pump_id is not None:
        stmt = stmt.where(PredictionResult.pump_id == pump_id)
    return list(db.scalars(stmt.order_by(PredictionResult.computed_at.desc())))