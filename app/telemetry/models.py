import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ConnectorStatus(enum.StrEnum):
    DISABLED = "disabled"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class TelemetryStatus(enum.StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"
    DUPLICATE = "duplicate"


class Connector(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "connector"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_connector_tenant_name"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(40), nullable=False, default="rest")
    status: Mapped[ConnectorStatus] = mapped_column(
        Enum(ConnectorStatus, name="connector_status"),
        nullable=False,
        default=ConnectorStatus.DISABLED,
    )
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class TelemetryRecord(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    __tablename__ = "telemetry_record"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "connector_id", "source_event_id", name="uq_telemetry_source_event"
        ),
    )

    connector_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connector.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    measurement: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float | None] = mapped_column(nullable=True)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(250), nullable=False)
    source_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[TelemetryStatus] = mapped_column(
        Enum(TelemetryStatus, name="telemetry_status"), nullable=False
    )
    reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)


class IngestionCheckpoint(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    __tablename__ = "ingestion_checkpoint"
    connector_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connector.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    last_source_event_id: Mapped[str | None] = mapped_column(String(250), nullable=True)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
