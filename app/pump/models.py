"""Pump reference data, including lifecycle metadata used downstream by
rul (remaining useful life) and flowgard_engine (health deviation).
"""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class PumpStatus(enum.StrEnum):
    OPERATIONAL = "operational"
    MAINTENANCE = "maintenance"
    STANDBY = "standby"
    DECOMMISSIONED = "decommissioned"


class Pump(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "pump"
    __table_args__ = {'schema': 'master'}

    station_id: Mapped[uuid.UUID] = mapped_column(
        # FIX: Point the Foreign Key specifically to the 'master' schema
        ForeignKey("master.station.id", ondelete="CASCADE"), nullable=False, index=True
    )

    tag_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_number: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Lifecycle metadata — the raw inputs RUL/flowgard_engine reason over
    # once that logic is implemented.
    install_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    design_life_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_overhaul_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    prior_intervention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    rated_flow_m3_per_hour: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    rated_pressure_kpa: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    status: Mapped[PumpStatus] = mapped_column(
        Enum(PumpStatus, name="pump_status"), nullable=False, default=PumpStatus.OPERATIONAL
    )
    commissioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Pump id={self.id} tag={self.tag_number!r}>"