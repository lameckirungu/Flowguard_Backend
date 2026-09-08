import time
from datetime import datetime

import numpy as np
from sqlalchemy import create_engine, text

# Updated with the URL-encoded password
engine = create_engine('postgresql://postgres:Kabarnet%409@localhost:5432/kpc_predictive_maintenance')

def generate_live_reading(pump_id, wear_multiplier):
    """Simulates a single sensor reading with progressive degradation."""
    return {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'pump_id': pump_id,
        'vibration_axial_mm_s': round(np.random.normal(2.5, 0.2) + (wear_multiplier * 6.5), 2),
        'vibration_radial_mm_s': round(np.random.normal(2.2, 0.2) + (wear_multiplier * 5.0), 2),
        'temperature_bearing_c': round(np.random.normal(65.0, 1.5) + (wear_multiplier * 35.0), 2),
        'temperature_casing_c': round(np.random.normal(55.0, 1.0) + (wear_multiplier * 20.0), 2),
        'pressure_suction_psi': round(np.random.normal(45.0, 2.0), 2),
        'pressure_discharge_psi': round(np.random.normal(600.0, 10.0) - (wear_multiplier * 80.0), 2),
        'motor_current_amps': round(np.random.normal(120.0, 2.5) + (wear_multiplier * 45.0), 2),
        'motor_voltage_v': round(np.random.normal(415.0, 5.0), 2),
        'rul_hours': max(0, int(1200 - (wear_multiplier * 1200))), # RUL drops as wear increases
        'failure_risk_7_day': 1 if wear_multiplier > 0.8 else 0
    }

def stream_data():
    print("🚀 Starting KPC Sensor Stream. Press Ctrl+C to stop.")
    degradation = 0.0 
    
    insert_query = text("""
        INSERT INTO bronze_pump_telemetry (
            timestamp, pump_id, vibration_axial_mm_s, vibration_radial_mm_s, 
            temperature_bearing_c, temperature_casing_c, pressure_suction_psi, 
            pressure_discharge_psi, motor_current_amps, motor_voltage_v, 
            rul_hours, failure_risk_7_day
        ) VALUES (
            :timestamp, :pump_id, :vibration_axial_mm_s, :vibration_radial_mm_s, 
            :temperature_bearing_c, :temperature_casing_c, :pressure_suction_psi, 
            :pressure_discharge_psi, :motor_current_amps, :motor_voltage_v, 
            :rul_hours, :failure_risk_7_day
        )
    """)

    while True:
        try:
            reading = generate_live_reading('PUMP_01', degradation)
            
            with engine.begin() as conn:
                conn.execute(insert_query, reading)
                
            print(f"[{reading['timestamp']}] 📡 Inserted {reading['pump_id']} | Vib: {reading['vibration_axial_mm_s']} | Temp: {reading['temperature_bearing_c']}")  # noqa: E501
            
            degradation += 0.005 # Simulate progressive wear
            if degradation > 1.0:
                degradation = 0.0 # Reset pump cycle
                print("\n🔧 Pump Replaced. Resetting degradation cycle.\n")

            time.sleep(3) # Send data every 3 seconds
            
        except KeyboardInterrupt:
            print("\n🛑 Streaming stopped by user.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    stream_data()