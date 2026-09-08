import random
from datetime import datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.etl.bronze.models import BronzePumpTelemetry, BronzeRegionalRisk, BronzeWeatherAPI
from app.etl.silver.models import RegionalRiskScore, SensorReading, WeatherReading


def process_bronze_to_silver(session: Session, tenant_id: UUID):
    """Applies data quality gates to raw telemetry and moves it to Silver."""
    stmt = select(BronzePumpTelemetry).where(BronzePumpTelemetry.tenant_id == tenant_id)
    raw_records = session.scalars(stmt).all()
    
    valid_readings = []
    for raw in raw_records:
        if raw.motor_current_amps is None or raw.motor_current_amps <= 0: continue
        if raw.temperature_bearing_c is None or not (0 <= raw.temperature_bearing_c <= 200): continue
        if raw.timestamp is None: continue
            
        clean_record = SensorReading(
            tenant_id=raw.tenant_id,
            timestamp=raw.timestamp,
            pump_id=raw.pump_id,
            vibration_axial_mm_s=raw.vibration_axial_mm_s,
            vibration_radial_mm_s=raw.vibration_radial_mm_s,
            temperature_bearing_c=raw.temperature_bearing_c,
            temperature_casing_c=raw.temperature_casing_c,
            pressure_suction_psi=raw.pressure_suction_psi,
            pressure_discharge_psi=raw.pressure_discharge_psi,
            motor_current_amps=raw.motor_current_amps,
            motor_voltage_v=raw.motor_voltage_v,
            rul_hours=raw.rul_hours,
            failure_risk_7_day=raw.failure_risk_7_day
        )
        valid_readings.append(clean_record)
        
    if valid_readings:
        session.add_all(valid_readings)
        session.commit()

def fetch_and_store_weather(session: Session, tenant_id: UUID, station_id: UUID, lat: float, lon: float):
    """Fetches Weather API data, lands JSON in Bronze, and conforms to Silver."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
    
    try:
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        raw_data = response.json()
    except httpx.RequestError as e:
        print(f"⚠️ Weather API failed for {station_id}: {e}")
        return
    
    current_time = datetime.now()
    
    # 1. Land the raw payload in the Bronze layer
    bronze_record = BronzeWeatherAPI(
        tenant_id=tenant_id, 
        station_id=station_id, 
        timestamp=current_time, 
        raw_payload=raw_data
    )
    session.add(bronze_record)
    
    # 2. Extract values from the new 'current' dictionary block
    current = raw_data.get("current", {})
    temp = current.get("temperature_2m")
    
    # 3. Apply Silver data quality gate and store
    if temp is not None and -50.0 <= temp <= 60.0:
        silver_record = WeatherReading(
            tenant_id=tenant_id,
            station_id=station_id,
            timestamp=current_time,
            temperature_c=temp,
            wind_speed_m_s=current.get("wind_speed_10m", 0.0),
            precipitation_mm=current.get("precipitation", 0.0),
            humidity_percent=current.get("relative_humidity_2m", 0.0)
        )
        session.add(silver_record)
        
    session.commit()

def fetch_and_store_regional_risk(session: Session, tenant_id: UUID, station_id: UUID):
    """Simulates regional risk extraction, lands JSON in Bronze, and conforms to Silver."""
    current_time = datetime.now()
    raw_payload = {
        "station_code": str(station_id), # FIX: Convert UUID to string for JSON serialization
        "population_density_km2": random.randint(50, 5000),
        "land_use_category": random.choice(["agricultural", "urban", "industrial", "protected"]),
        "incidents_past_30_days": random.randint(0, 5),
        "security_threat_level": random.uniform(0.1, 0.9)
    }

    bronze_record = BronzeRegionalRisk(
        tenant_id=tenant_id, 
        station_id=station_id, 
        timestamp=current_time, 
        raw_payload=raw_payload
    )
    session.add(bronze_record)
    
    incidents = raw_payload.get("incidents_past_30_days", 0)
    composite_score = min((incidents * 10) + (raw_payload.get("security_threat_level", 0.0) * 50), 100.0)
    
    if 0.0 <= composite_score <= 100.0:
        silver_record = RegionalRiskScore(
            tenant_id=tenant_id,
            station_id=station_id,
            timestamp=current_time,
            composite_risk_score=composite_score,
            incident_count_30d=incidents
        )
        session.add(silver_record)
    session.commit()

def get_cleaned_telemetry(session: Session, tenant_id: UUID, pump_id: UUID, limit: int = 100):
    stmt = select(SensorReading).where(
        SensorReading.tenant_id == tenant_id, 
        SensorReading.pump_id == pump_id
    ).order_by(SensorReading.timestamp.desc()).limit(limit)
    return session.scalars(stmt).all()