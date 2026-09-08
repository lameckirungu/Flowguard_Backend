from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.etl.gold.models import GoldPumpFeatures
from app.etl.silver.models import SensorReading


def compute_and_store_gold_features(session: Session, tenant_id: UUID, pump_id: UUID) -> None:
    """Computes rolling window aggregations from Silver and inserts them into Gold."""
    
    # Define reusable window arguments as a dictionary to unpack
    window_kwargs = {
        "partition_by": SensorReading.pump_id,
        "order_by": SensorReading.timestamp.asc(),
        "rows": (-2, 0)
    }

    is_sqlite = session.bind and session.bind.dialect.name == "sqlite"
    if is_sqlite:
        max_vib = func.max(SensorReading.vibration_axial_mm_s).over(**window_kwargs)
        min_vib = func.min(SensorReading.vibration_axial_mm_s).over(**window_kwargs)
        vib_std_expr = (max_vib - min_vib) / 2.0
    else:
        vib_std_expr = func.stddev(SensorReading.vibration_axial_mm_s).over(**window_kwargs)

    query = (
        select(
            SensorReading.timestamp,
            SensorReading.pump_id,
            SensorReading.vibration_axial_mm_s,
            SensorReading.temperature_bearing_c,
            SensorReading.pressure_discharge_psi,
            SensorReading.motor_current_amps,
            func.avg(SensorReading.vibration_axial_mm_s).over(**window_kwargs).label("vib_avg"),
            vib_std_expr.label("vib_std"),
            func.avg(SensorReading.temperature_bearing_c).over(**window_kwargs).label("temp_avg"),
            func.max(SensorReading.temperature_bearing_c).over(**window_kwargs).label("temp_max"),
            func.avg(SensorReading.pressure_discharge_psi).over(**window_kwargs).label("press_avg"),
            SensorReading.rul_hours,
            SensorReading.failure_risk_7_day,
        )
        .where(SensorReading.tenant_id == tenant_id, SensorReading.pump_id == pump_id)
        .order_by(SensorReading.timestamp.desc())
        .limit(100)
    )

    results = session.execute(query).all()

    gold_records = [
        GoldPumpFeatures(
            tenant_id=tenant_id,
            timestamp=row.timestamp,
            pump_id=row.pump_id,
            vibration_axial_mm_s=row.vibration_axial_mm_s,
            temperature_bearing_c=row.temperature_bearing_c,
            pressure_discharge_psi=row.pressure_discharge_psi,
            motor_current_amps=row.motor_current_amps,
            vibration_axial_rolling_avg=row.vib_avg,
            vibration_axial_rolling_std=row.vib_std or 0.0,
            temperature_bearing_rolling_avg=row.temp_avg,
            temperature_bearing_rolling_max=row.temp_max,
            pressure_discharge_rolling_avg=row.press_avg,
            rul_hours=row.rul_hours,
            failure_risk_7_day=row.failure_risk_7_day,
        )
        for row in reversed(results)
    ]

    if gold_records:
        session.add_all(gold_records)
        session.commit()

def get_ml_features(session: Session, tenant_id: UUID, pump_id: UUID, limit: int = 50) -> list[GoldPumpFeatures]:
    stmt = select(GoldPumpFeatures).where(
        GoldPumpFeatures.tenant_id == tenant_id, GoldPumpFeatures.pump_id == pump_id
    ).order_by(GoldPumpFeatures.timestamp.desc()).limit(limit)
    return list(session.scalars(stmt).all())