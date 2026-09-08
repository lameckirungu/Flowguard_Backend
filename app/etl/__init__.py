# app/etl/__init__.py

# 1. Import Bronze Layer components
from .bronze import (
    BronzePumpTelemetry,
    BronzeRegionalRisk,
    BronzeWeatherAPI,
    get_raw_telemetry,
    ingest_telemetry_reading,
)

# 3. Import Gold Layer components
from .gold import GoldPumpFeatures, compute_and_store_gold_features, get_ml_features

# 2. Import Silver Layer components
from .silver import (
    RegionalRiskScore,
    SensorReading,
    WeatherReading,
    fetch_and_store_regional_risk,
    fetch_and_store_weather,
    get_cleaned_telemetry,
    process_bronze_to_silver,
)

# Expose them all cleanly to the rest of the application
__all__ = [
    # Bronze Models & Services
    "BronzePumpTelemetry",
    "BronzeWeatherAPI",
    "BronzeRegionalRisk",
    "ingest_telemetry_reading",
    "get_raw_telemetry",
    
    # Silver Models & Services
    "SensorReading",
    "WeatherReading",
    "RegionalRiskScore",
    "process_bronze_to_silver",
    "get_cleaned_telemetry",
    "fetch_and_store_weather",
    "fetch_and_store_regional_risk",
    
    # Gold Models & Services
    "GoldPumpFeatures",
    "compute_and_store_gold_features",
    "get_ml_features"
]