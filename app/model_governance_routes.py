import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.auth import require_permission
from app.core.db import get_db
from app.core.permissions import Permission
from app.core.tenancy import get_current_tenant_id
from app.etl.gold.models import PumpFeatureWindow
from app.prediction.models import PredictionResult
from app.telemetry.models import TelemetryRecord, TelemetryStatus

router = APIRouter(prefix="/api/v1/model-governance", tags=["model-governance"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(get_current_tenant_id)):
    latest = db.scalar(
        select(PredictionResult)
        .where(PredictionResult.tenant_id == tenant_id)
        .order_by(PredictionResult.computed_at.desc())
        .limit(1)
    )
    features = (
        db.scalar(
            select(func.count(PumpFeatureWindow.id)).where(PumpFeatureWindow.tenant_id == tenant_id)
        )
        or 0
    )
    predictions = (
        db.scalar(
            select(func.count(PredictionResult.id)).where(PredictionResult.tenant_id == tenant_id)
        )
        or 0
    )
    accepted = (
        db.scalar(
            select(func.count(TelemetryRecord.id)).where(
                TelemetryRecord.tenant_id == tenant_id,
                TelemetryRecord.status == TelemetryStatus.ACCEPTED,
            )
        )
        or 0
    )
    return {
        "model_version": latest.model_version if latest else "v1.0.0",
        "feature_version": latest.feature_version if latest else "pump-window-v1",
        "model_status": "production",
        "last_inference_at": latest.computed_at if latest else None,
        "prediction_count": predictions,
        "feature_window_count": features,
        "telemetry_accepted_count": accepted,
        "monitoring_status": "insufficient_sample" if predictions < 30 else "available",
        "drift_status": "inconclusive",
        "coverage_status": "available" if accepted else "unavailable",
    }


@router.get("/inference-runs")
def inference_runs(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.RUN_MODELS)),
):
    rows = db.execute(
        select(
            PredictionResult.computed_at,
            PredictionResult.model_version,
            func.count(PredictionResult.id),
        )
        .where(PredictionResult.tenant_id == tenant_id)
        .group_by(PredictionResult.computed_at, PredictionResult.model_version)
        .order_by(PredictionResult.computed_at.desc())
        .limit(50)
    )
    return [
        {
            "completed_at": at,
            "model_version": version,
            "status": "succeeded",
            "prediction_count": count,
        }
        for at, version, count in rows
    ]


@router.get("/predictions/{prediction_id}/provenance")
def prediction_provenance(
    prediction_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    result = db.scalar(
        select(PredictionResult).where(
            PredictionResult.id == prediction_id, PredictionResult.tenant_id == tenant_id
        )
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return {
        "prediction_id": result.id,
        "pump_id": result.pump_id,
        "computed_at": result.computed_at,
        "model_version": result.model_version,
        "feature_version": result.feature_version,
        "input_watermark": result.input_watermark,
        "data_quality": result.data_quality,
        "confidence": result.confidence,
        "rul_hours": result.rul_hours,
        "rul_low_hours": result.rul_low_hours,
        "rul_high_hours": result.rul_high_hours,
    }
