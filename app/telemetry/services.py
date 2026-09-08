import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.telemetry.models import (
    Connector,
    ConnectorStatus,
    IngestionCheckpoint,
    TelemetryRecord,
    TelemetryStatus,
)
from app.telemetry.schemas import TelemetryEnvelope


def create_connector(
    db: Session, tenant_id: uuid.UUID, name: str, connector_type: str, configuration: dict
) -> Connector:
    connector = Connector(
        tenant_id=tenant_id, name=name, connector_type=connector_type, configuration=configuration
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector


def list_connectors(db: Session, tenant_id: uuid.UUID) -> list[Connector]:
    return list(
        db.scalars(
            select(Connector).where(Connector.tenant_id == tenant_id).order_by(Connector.name)
        )
    )


def ingest(
    db: Session, tenant_id: uuid.UUID, connector_id: uuid.UUID, envelopes: list[TelemetryEnvelope]
) -> dict[str, int | uuid.UUID]:
    connector = db.scalar(
        select(Connector).where(Connector.id == connector_id, Connector.tenant_id == tenant_id)
    )
    if connector is None:
        raise ValueError("Connector not found")
    if connector.status == ConnectorStatus.DISABLED:
        raise ValueError("Connector is disabled")
    checkpoint = db.scalar(
        select(IngestionCheckpoint).where(IngestionCheckpoint.connector_id == connector.id)
    )
    if checkpoint is None:
        checkpoint = IngestionCheckpoint(tenant_id=tenant_id, connector_id=connector.id)
        db.add(checkpoint)
    counts = {"accepted": 0, "rejected": 0, "duplicates": 0, "quarantined": 0}
    now = datetime.now(UTC)
    for payload in envelopes:
        received_at = payload.received_at or now
        status = TelemetryStatus.ACCEPTED
        reason_code = None
        reason_detail = None
        if payload.value is None:
            status, reason_code, reason_detail = (
                TelemetryStatus.REJECTED,
                "missing_value",
                "Measurement value is required",
            )
        elif payload.observed_at > received_at + timedelta(minutes=5):
            status, reason_code, reason_detail = (
                TelemetryStatus.QUARANTINED,
                "future_timestamp",
                "Observed time is too far ahead",
            )
        elif payload.measurement not in {
            "vibration",
            "vibration_mm_s",
            "temperature",
            "temperature_c",
            "pressure",
            "pressure_kpa",
            "motor_current",
            "motor_current_a",
        }:
            status, reason_code, reason_detail = (
                TelemetryStatus.REJECTED,
                "unknown_measurement",
                "Measurement is not supported",
            )
        record = TelemetryRecord(
            tenant_id=tenant_id,
            connector_id=connector.id,
            asset_key=payload.asset_key,
            measurement=payload.measurement,
            observed_at=payload.observed_at,
            received_at=received_at,
            value=payload.value,
            unit=payload.unit,
            source_event_id=payload.source_event_id,
            source_payload=payload.model_dump(mode="json"),
            status=status,
            reason_code=reason_code,
            reason_detail=reason_detail,
        )
        duplicate = db.scalar(
            select(TelemetryRecord).where(
                TelemetryRecord.tenant_id == tenant_id,
                TelemetryRecord.connector_id == connector.id,
                TelemetryRecord.source_event_id == payload.source_event_id,
            )
        )
        if duplicate is not None:
            counts["duplicates"] += 1
            checkpoint.duplicate_count += 1
            continue
        db.add(record)
        db.flush()
        counts[status.value if status.value != "duplicate" else "duplicates"] += 1
        checkpoint.processed_count += 1
        checkpoint.last_source_event_id = payload.source_event_id
        checkpoint.last_processed_at = now
        if status == TelemetryStatus.ACCEPTED:
            checkpoint.accepted_count += 1
        elif status == TelemetryStatus.REJECTED:
            checkpoint.rejected_count += 1
        elif status == TelemetryStatus.QUARANTINED:
            checkpoint.rejected_count += 1
    connector.last_success_at = now
    connector.status = ConnectorStatus.HEALTHY
    db.commit()
    return {**counts, "connector_id": connector.id}


def summary(db: Session, tenant_id: uuid.UUID) -> list[dict]:
    result = []
    for connector in list_connectors(db, tenant_id):
        checkpoint = db.scalar(
            select(IngestionCheckpoint).where(IngestionCheckpoint.connector_id == connector.id)
        )
        latest = db.execute(
            select(
                func.max(TelemetryRecord.observed_at), func.max(TelemetryRecord.received_at)
            ).where(
                TelemetryRecord.connector_id == connector.id,
                TelemetryRecord.tenant_id == tenant_id,
                TelemetryRecord.status == TelemetryStatus.ACCEPTED,
            )
        ).one()
        latest_observed, latest_received = latest
        freshness = (
            "unavailable"
            if latest_observed is None
            else "fresh"
            if datetime.now(UTC) - latest_observed
            <= timedelta(seconds=settings.telemetry_freshness_seconds)
            else "stale"
        )
        result.append(
            {
                "connector_id": connector.id,
                "connector_name": connector.name,
                "status": connector.status,
                "received": checkpoint.processed_count if checkpoint else 0,
                "accepted": checkpoint.accepted_count if checkpoint else 0,
                "rejected": checkpoint.rejected_count if checkpoint else 0,
                "duplicates": checkpoint.duplicate_count if checkpoint else 0,
                "latest_observed_at": latest_observed,
                "latest_received_at": latest_received,
                "freshness_status": freshness,
            }
        )
    return result
