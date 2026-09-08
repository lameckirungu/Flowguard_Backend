from datetime import UTC, datetime
from sqlalchemy import func, select
from app.etl.bronze.models import BronzePumpTelemetry
from app.etl.gold.models import GoldPumpFeatures
from app.prediction.models import PredictionResult

def status(db, tenant_id):
    telemetry_at = db.scalar(select(func.max(BronzePumpTelemetry.timestamp)).where(BronzePumpTelemetry.tenant_id == tenant_id))
    features_at = db.scalar(select(func.max(GoldPumpFeatures.timestamp)).where(GoldPumpFeatures.tenant_id == tenant_id))
    prediction_at = db.scalar(select(func.max(PredictionResult.computed_at)).where(PredictionResult.tenant_id == tenant_id))
    now = datetime.now(UTC)
    latest = max((v for v in (telemetry_at, features_at, prediction_at) if v), default=None)
    age_minutes = ((now - latest).total_seconds() / 60) if latest else None
    freshness = "no_data" if latest is None else "fresh" if age_minutes <= 30 else "stale"
    return {"status": "healthy" if latest else "inconclusive", "data_mode": "operational", "freshness": freshness, "latest_telemetry_at": telemetry_at, "latest_features_at": features_at, "latest_prediction_at": prediction_at, "age_minutes": round(age_minutes, 1) if age_minutes is not None else None, "stages": [{"name": "telemetry", "status": "available" if telemetry_at else "no_data", "last_success_at": telemetry_at}, {"name": "features", "status": "available" if features_at else "no_data", "last_success_at": features_at}, {"name": "predictions", "status": "available" if prediction_at else "no_data", "last_success_at": prediction_at}]}
