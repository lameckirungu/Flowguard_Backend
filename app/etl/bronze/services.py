from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.etl.bronze.models import BronzePumpTelemetry


def ingest_telemetry_reading(session: Session, tenant_id: UUID, reading_data: dict) -> BronzePumpTelemetry:
    """Inserts a single raw sensor reading into the Bronze storage, securely scoped to the tenant."""
    reading_data["tenant_id"] = tenant_id 
    new_reading = BronzePumpTelemetry(**reading_data)
    session.add(new_reading)
    session.commit()
    session.refresh(new_reading)
    return new_reading

def get_raw_telemetry(session: Session, tenant_id: UUID, pump_id: str, limit: int = 100):
    """Retrieves the most recent raw telemetry data strictly filtered by tenant."""
    stmt = select(BronzePumpTelemetry).where(
        BronzePumpTelemetry.tenant_id == tenant_id,
        BronzePumpTelemetry.pump_id == pump_id
    ).order_by(BronzePumpTelemetry.timestamp.desc()).limit(limit)
    
    return session.scalars(stmt).all()