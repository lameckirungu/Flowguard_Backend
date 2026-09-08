from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SensorReading(Base, TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sensor_reading"
    __table_args__ = {'schema': 'silver'}
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

class WeatherReading(Base, TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "weather_reading"
    __table_args__ = {'schema': 'silver'}
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("master.station.id"), index=True)
    temperature_c: Mapped[float] = mapped_column(Float)
    precipitation_mm: Mapped[float] = mapped_column(Float)
    wind_speed_m_s: Mapped[float] = mapped_column(Float)
    humidity_percent: Mapped[float] = mapped_column(Float)

class RegionalRiskScore(Base, TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "regional_risk_score"
    __table_args__ = {'schema': 'silver'}
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    station_id: Mapped[UUID] = mapped_column(ForeignKey("master.station.id"), index=True)
    composite_risk_score: Mapped[float] = mapped_column(Float)
    incident_count_30d: Mapped[int] = mapped_column(Integer)