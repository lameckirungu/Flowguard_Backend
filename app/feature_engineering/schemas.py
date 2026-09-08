"""The one definition of what a model-ready feature vector contains.

`app.feature_engineering.services` builds a `FeatureVector` and returns it as
a plain ``dict[str, float]`` (see the module docstring there for why the
public contract is a dict). Consumers that want type checking can
``FeatureVector.model_validate(vec)`` the dict back.

Keeping this in one place means a renamed/removed feature is a construction
error here, not a `KeyError` inside prediction / rul / explainability three
modules downstream.

Field naming maps directly onto the ETL Gold tables
(`app/etl/gold/models.py`):

* sensor tier   -> ``PumpFeatureWindow``   (joined on ``pump_id``)
* weather tier  -> ``WeatherDailyRollup``  (joined on the pump's ``station_id``)
* risk tier     -> ``StationRiskComposite`` (joined on the pump's ``station_id``)

Only columns that actually exist on those tables are represented. The
project proposal's three-tier schema also names ``*_min`` / ``*_max`` /
``*_trend`` sensor stats, a 30-day cumulative rainfall figure and an average
humidity figure; none of those columns exist in the current Gold schema, so
they are intentionally absent rather than faked.
"""
from pydantic import BaseModel, ConfigDict

# Every value is a float so the assembled vector round-trips through
# ``dict[str, float]`` without loss. ``0.0`` is the fill value for a NULL
# column or an absent weather/risk join — the ``*_data_available`` flags let
# a downstream model tell "genuinely zero" from "not joined".
_ZERO = 0.0


class FeatureVector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # --- sensor tier: PumpFeatureWindow -------------------------------------
    vibration_mean: float = _ZERO
    vibration_std: float = _ZERO
    temperature_mean: float = _ZERO
    temperature_std: float = _ZERO
    pressure_mean: float = _ZERO
    pressure_std: float = _ZERO
    motor_current_mean: float = _ZERO
    # Number of raw readings behind the window — lets a model down-weight a
    # thin window instead of treating it like a full one.
    sample_count: float = _ZERO

    # --- weather tier: WeatherDailyRollup ---------------------------------
    weather_temperature_mean: float = _ZERO
    weather_precipitation_total_mm: float = _ZERO
    weather_wind_speed_max_m_s: float = _ZERO
    # 1.0 if a WeatherDailyRollup row was joined, else 0.0.
    weather_data_available: float = _ZERO

    # --- regional risk tier: StationRiskComposite -------------------------
    regional_risk_score: float = _ZERO
    # 1.0 if a StationRiskComposite row was joined, else 0.0.
    risk_data_available: float = _ZERO

    def as_dict(self) -> dict[str, float]:
        return {key: float(value) for key, value in self.model_dump().items()}


# Stable ordering / membership check for consumers and tests.
FEATURE_KEYS: tuple[str, ...] = tuple(FeatureVector.model_fields.keys())
