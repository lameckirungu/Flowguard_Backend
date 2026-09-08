import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import SessionLocal
from app.etl.gold.services import compute_and_store_gold_features
from app.etl.silver.services import (
    fetch_and_store_regional_risk,
    fetch_and_store_weather,
    process_bronze_to_silver,
)
from app.pump.models import Pump
from app.station.models import Station
from app.tenant.models import Tenant


def run_pipeline_cycle():
    with SessionLocal() as session:
        tenant = session.query(Tenant).filter(Tenant.slug == "kpc").one_or_none()
        stations = session.query(Station).filter(Station.tenant_id == tenant.id).all()
        
        # Use station.id UUIDs
        for station in stations:
            fetch_and_store_weather(session, tenant.id, station.id, float(station.latitude), float(station.longitude))
            fetch_and_store_regional_risk(session, tenant.id, station.id)

        process_bronze_to_silver(session, tenant.id)

        # Use pump.id UUIDs
        pumps = session.query(Pump).filter(Pump.tenant_id == tenant.id).all()
        for pump in pumps:
            compute_and_store_gold_features(session, tenant.id, pump.id)

def main():
    print("⚙️ Starting Flowgard ETL Pipeline Orchestrator. Press Ctrl+C to stop.")
    while True:
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Processing micro-batch...")
            run_pipeline_cycle()
            print("✅ Pipeline sync complete.")
            time.sleep(15)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()