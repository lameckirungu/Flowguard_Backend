"""Smoke tests for app.etl — no routes.py by design (see app/etl/README.md).

Bronze landing is exercised end-to-end including tenant scoping;
silver/gold/simulator transform logic is confirmed to run without crashing.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.etl.bronze import services as bronze_services
from app.etl.bronze.models import BronzePumpTelemetry
from app.etl.gold import services as gold_services
from app.etl.silver import services as silver_services
from app.etl.simulator import services as simulator_services
from app.pump.models import Pump
from app.station.models import Station


def _ensure_pump(db_session: Session, tenant_id: uuid.UUID) -> uuid.UUID:
    """Helper to guarantee a pump exists to satisfy Bronze FK constraints."""
    # 1. Check if the Pytest fixtures already built a pump
    pump = db_session.scalar(select(Pump).where(Pump.tenant_id == tenant_id).limit(1))
    if pump:
        return pump.id
        
    # 2. If not, build a dummy Station and Pump for the test
    station = db_session.scalar(select(Station).where(Station.tenant_id == tenant_id).limit(1))
    if not station:
        station = Station(tenant_id=tenant_id, name="Test Station", code="TS-01")
        db_session.add(station)
        db_session.flush()
        
    # FIX: Re-added the tag using the correct column name 'tag_number'
    new_pump = Pump(tenant_id=tenant_id, station_id=station.id, tag_number="SMOKE-PUMP")
    db_session.add(new_pump)
    db_session.commit()
    return new_pump.id


def test_bronze_landing_is_tenant_scoped(db_session: Session, tenant_a, tenant_b):
    # FIX: Ensure a real pump exists so we don't violate foreign key constraints
    pump_id = _ensure_pump(db_session, tenant_a.id)
    
    reading_data = {
        "timestamp": datetime.now(UTC),
        "pump_id": pump_id,
        "vibration_axial_mm_s": 3.2,
        "vibration_radial_mm_s": 2.1,
        "temperature_bearing_c": 45.0,
        "temperature_casing_c": 50.0,
        "pressure_suction_psi": 40.0,
        "pressure_discharge_psi": 600.0,
        "motor_current_amps": 120.0,
        "motor_voltage_v": 415.0,
        "rul_hours": 1200,
        "failure_risk_7_day": 0,
    }
    
    event_a = bronze_services.ingest_telemetry_reading(
        db_session,
        tenant_a.id,
        reading_data
    )
    db_session.commit()

    events_for_a = db_session.scalars(
        select(BronzePumpTelemetry).where(BronzePumpTelemetry.tenant_id == tenant_a.id)
    ).all()
    assert [e.id for e in events_for_a] == [event_a.id]

    events_for_b = db_session.scalars(
        select(BronzePumpTelemetry).where(BronzePumpTelemetry.tenant_id == tenant_b.id)
    ).all()
    assert events_for_b == []


def test_silver_conforming_smoke(db_session: Session, tenant_a):
    silver_services.process_bronze_to_silver(db_session, tenant_a.id)


def test_gold_aggregation_smoke(db_session: Session, tenant_a):
    pump_id = _ensure_pump(db_session, tenant_a.id)
    gold_services.compute_and_store_gold_features(
        db_session, tenant_a.id, pump_id
    )


def test_simulator_smoke(db_session: Session, tenant_a):
    # FIX: Provide a real pump ID to the simulator
    pump_id = _ensure_pump(db_session, tenant_a.id)
    
    simulator_services.record_simulated_reading(
        db_session, tenant_a.id, pump_id, wear_multiplier=0.1
    )