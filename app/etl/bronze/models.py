from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

JSON_TYPE = JSONB().with_variant(JSON, "sqlite")


class BronzePumpTelemetry(Base, TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pump_telemetry"
    __table_args__ = {'schema': 'bronze'}
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    pump_id: Mapped[UUID] = mapped_column(ForeignKey("master.pump.id"), index=True)
    vibration_axial_mm_s: Mapped[float] = mapped_column(Float)
    vibration_radial_mm_s: Mapped[float] = mapped_column(Float)
    temperature_bearing_c: Mapped[float] = mapped_column(Float)
    temperature_casing_c: Mapped[float] = mapped_column(Float)
    pressure_suction_psi: Mapped[float] = mapped_column(Float)
    pressure_discharge_psi: Mapped[float] = mapped_column(Float)
    motor_current_amps: Mapped[float] = mapped_column(Float)
    motor_voltage_v: Mapped[float] = mapped_column(Float)
    rul_hours: Mapped[int] = mapped_column(Integer)
    failure_risk_7_day: Mapped[int] = mapped_column(Integer)

class BronzeWeatherAPI(Base, TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "weather_api"
    __table_args__ = {'schema': 'bronze'}
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("master.station.id"), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON_TYPE)

class BronzeRegionalRisk(Base, TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "regional_risk"
    __table_args__ = {'schema': 'bronze'}
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("master.station.id"), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON_TYPE)