import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import SessionLocal
from app.etl.simulator.services import record_simulated_reading
from app.pump.models import Pump
from app.tenant.models import Tenant


def run_stream():
    print("🚀 Starting KPC Telemetry Simulator. Press Ctrl+C to stop.")
    with SessionLocal() as db:
        tenant = db.query(Tenant).filter(Tenant.slug == "kpc").one_or_none()
        pumps = db.query(Pump).filter(Pump.tenant_id == tenant.id).all()
        
        # Use UUIDs instead of tags
        pump_ids = [p.id for p in pumps]
        print(f"📡 Simulating live stream across {len(pump_ids)} KPC pumps...")

        wear_tracker = {pid: 0.0 for pid in pump_ids}

        while True:
            try:
                for pid in pump_ids:
                    wear = wear_tracker[pid]
                    reading = record_simulated_reading(db, tenant.id, pid, wear)
                    print(f"[{reading.timestamp.strftime('%H:%M:%S')}] 📡 {reading.pump_id} | Vib: {reading.vibration_axial_mm_s} mm/s | Temp: {reading.temperature_bearing_c}°C")  # noqa: E501
                    
                    wear_tracker[pid] += 0.005
                    if wear_tracker[pid] > 1.0: wear_tracker[pid] = 0.0
                time.sleep(3)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    run_stream()