-- 1. BRONZE LAYER (The Raw Storage)
CREATE TABLE IF NOT EXISTS bronze_pump_telemetry (
    timestamp TIMESTAMP,
    pump_id VARCHAR(50),
    vibration_axial_mm_s FLOAT,
    vibration_radial_mm_s FLOAT,
    temperature_bearing_c FLOAT,
    temperature_casing_c FLOAT,
    pressure_suction_psi FLOAT,
    pressure_discharge_psi FLOAT,
    motor_current_amps FLOAT,
    motor_voltage_v FLOAT,
    rul_hours INTEGER,
    failure_risk_7_day INTEGER,
    ingestion_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. SILVER LAYER (The Real-Time Filter)
CREATE OR REPLACE VIEW silver_pump_telemetry AS
SELECT * FROM bronze_pump_telemetry
WHERE motor_current_amps > 0 
  AND temperature_bearing_c BETWEEN 0 AND 200
  AND timestamp IS NOT NULL;

-- 3. GOLD LAYER (The Cached ML Features)
CREATE MATERIALIZED VIEW gold_ml_features AS
SELECT 
    timestamp,
    pump_id,
    vibration_axial_mm_s,
    temperature_bearing_c,
    pressure_discharge_psi,
    -- 3-reading rolling averages for ML context
    AVG(vibration_axial_mm_s) OVER (PARTITION BY pump_id ORDER BY timestamp ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS rolling_3_avg_vib,
    AVG(temperature_bearing_c) OVER (PARTITION BY pump_id ORDER BY timestamp ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS rolling_3_avg_temp,
    rul_hours,
    failure_risk_7_day
FROM silver_pump_telemetry;