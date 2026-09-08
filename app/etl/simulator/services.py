from datetime import datetime
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

from app.etl.bronze.models import BronzePumpTelemetry


def generate_live_reading(tenant_id: UUID | str, pump_id: UUID | str, wear_multiplier: float) -> dict:
    """Simulates a single sensor reading with progressive degradation for a specific tenant pump."""
    return {
        "tenant_id": UUID(str(tenant_id)) if not isinstance(tenant_id, UUID) else tenant_id,
        "timestamp": datetime.now(),
        "pump_id": UUID(str(pump_id)) if not isinstance(pump_id, UUID) else pump_id,
        "vibration_axial_mm_s": round(float(np.random.normal(2.5, 0.2) + (wear_multiplier * 6.5)), 2),
        "vibration_radial_mm_s": round(float(np.random.normal(2.2, 0.2) + (wear_multiplier * 5.0)), 2),
        "temperature_bearing_c": round(float(np.random.normal(65.0, 1.5) + (wear_multiplier * 35.0)), 2),
        "temperature_casing_c": round(float(np.random.normal(55.0, 1.0) + (wear_multiplier * 20.0)), 2),
        "pressure_suction_psi": round(float(np.random.normal(45.0, 2.0)), 2),
        "pressure_discharge_psi": round(float(np.random.normal(600.0, 10.0) - (wear_multiplier * 80.0)), 2),
        "motor_current_amps": round(float(np.random.normal(120.0, 2.5) + (wear_multiplier * 45.0)), 2),
        "motor_voltage_v": round(float(np.random.normal(415.0, 5.0)), 2),
        "rul_hours": max(0, int(1200 - (wear_multiplier * 1200))),
        "failure_risk_7_day": 1 if wear_multiplier > 0.8 else 0,
    }

def record_simulated_reading(session: Session, tenant_id: UUID | str, pump_id: UUID | str, wear_multiplier: float) -> BronzePumpTelemetry:
    """Generates and writes a single simulated telemetry record to Bronze storage."""
    payload = generate_live_reading(tenant_id, pump_id, wear_multiplier)
    reading = BronzePumpTelemetry(**payload)
    session.add(reading)
    session.commit()
    session.refresh(reading)
    return reading