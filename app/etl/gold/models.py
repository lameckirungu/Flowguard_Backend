from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class GoldPumpFeatures(Base, TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pump_features"
    __table_args__ = {'schema': 'gold'}
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    pump_id: Mapped[UUID] = mapped_column(ForeignKey("master.pump.id"), index=True)
    vibration_axial_mm_s: Mapped[float] = mapped_column(Float)
    temperature_bearing_c: Mapped[float] = mapped_column(Float)
    pressure_discharge_psi: Mapped[float] = mapped_column(Float)
    motor_current_amps: Mapped[float] = mapped_column(Float)
    vibration_axial_rolling_avg: Mapped[float] = mapped_column(Float)
    vibration_axial_rolling_std: Mapped[float] = mapped_column(Float, nullable=True)
    temperature_bearing_rolling_avg: Mapped[float] = mapped_column(Float)
    temperature_bearing_rolling_max: Mapped[float] = mapped_column(Float)
    pressure_discharge_rolling_avg: Mapped[float] = mapped_column(Float)
    rul_hours: Mapped[int] = mapped_column(Integer)
    failure_risk_7_day: Mapped[int] = mapped_column(Integer)


class PumpFeatureWindow(Base, TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pump_feature_windows"
    window_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime, index=True)
    pump_id: Mapped[UUID] = mapped_column(ForeignKey("master.pump.id"), index=True)
    vibration_mean: Mapped[float] = mapped_column(Float, nullable=True)
    vibration_std: Mapped[float] = mapped_column(Float, nullable=True)
    temperature_mean: Mapped[float] = mapped_column(Float, nullable=True)
    temperature_std: Mapped[float] = mapped_column(Float, nullable=True)
    pressure_mean: Mapped[float] = mapped_column(Float, nullable=True)
    pressure_std: Mapped[float] = mapped_column(Float, nullable=True)
    motor_current_mean: Mapped[float] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)

    pump = relationship("Pump", lazy="select")


class StationRiskComposite(Base, TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "station_risk_composites"
    station_id: Mapped[UUID] = mapped_column(ForeignKey("master.station.id"), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    composite_score: Mapped[float] = mapped_column(Float, nullable=True)


class WeatherDailyRollup(Base, TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "weather_daily_rollups"
    station_id: Mapped[UUID] = mapped_column(ForeignKey("master.station.id"), index=True)
    day: Mapped[datetime] = mapped_column(DateTime, index=True)
    temperature_mean: Mapped[float] = mapped_column(Float, nullable=True)
    precipitation_total_mm: Mapped[float] = mapped_column(Float, nullable=True)
    wind_speed_max_m_s: Mapped[float] = mapped_column(Float, nullable=True)