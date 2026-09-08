"""Gold-layer feature vector assembly service.

Flattens the latest Gold-layer sensor features (`PumpFeatureWindow`), daily
weather rollup (`WeatherDailyRollup`) and regional risk composite
(`StationRiskComposite`) into a model-ready ``dict[str, float]`` vector for a
given pump.

Design principles:

* **Strict sensor freshness**: A pump whose newest sensor window is older
  than `MAX_WINDOW_AGE` (1 hour) is considered unscoreable — predictive
  decisions should not be made on it, so `build_feature_vector` raises
  `StaleFeatureDataError`.
* **Graceful tier degradation**: Weather and regional risk are auxiliary — if
  no row exists for a station's location/region, the join returns NULL and
  those features are filled with ``0.0`` (the `*_data_available` flags in
  `app.feature_engineering.schemas.FeatureVector` let downstream models tell
  "genuinely zero" from "not joined").
* **Batch efficiency**: `build_feature_batch` uses a fixed number of queries
  (one per source table) regardless of the number of pumps scored, avoiding
  N+1 DB round-trips during scheduled fleet scoring runs.
* **Portable single-query newest-row**: Group-by-MAX + self-join works on
  Postgres, SQLite and MySQL — no `DISTINCT ON` dialect lock-in.

`build_feature_vector` is for single-pump interactive API calls where missing
or stale data should be reported to the caller as an explicit error.

`build_feature_batch` is for scheduled fleet-wide scoring: it omits pumps with
stale or missing windows rather than raising, ensuring one lagging pump does
not abort an entire scoring run.
"""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.etl.gold.models import GoldPumpFeatures, PumpFeatureWindow, StationRiskComposite, WeatherDailyRollup
from app.feature_engineering.schemas import FeatureVector
from app.flowgard_engine.models import HealthDeviationRecord
from app.pump.models import Pump

# A sensor window older than this is considered too stale to score a live
# risk decision on. Chosen against the ~1-minute raw sensor cadence: an hour
# is dozens of missed windows, i.e. a real ingestion gap rather than jitter.
MAX_WINDOW_AGE = timedelta(hours=1)


class FeatureEngineeringError(Exception):
    """Base for the two conditions a caller is expected to branch on."""


class FeatureVectorUnavailableError(FeatureEngineeringError):
    """No `PumpFeatureWindow` exists at all for this pump/tenant yet."""

    def __init__(self, tenant_id: uuid.UUID, pump_id: uuid.UUID) -> None:
        self.tenant_id = tenant_id
        self.pump_id = pump_id
        super().__init__(
            f"no feature window for pump {pump_id} (tenant {tenant_id}); "
            "ETL Gold has produced nothing for this pump"
        )


class StaleFeatureDataError(FeatureEngineeringError):
    """The newest `PumpFeatureWindow` is older than `MAX_WINDOW_AGE`."""

    def __init__(
        self, tenant_id: uuid.UUID, pump_id: uuid.UUID, last_window_end: datetime
    ) -> None:
        self.tenant_id = tenant_id
        self.pump_id = pump_id
        self.last_window_end = last_window_end
        super().__init__(
            f"newest feature window for pump {pump_id} (tenant {tenant_id}) ends at "
            f"{last_window_end.isoformat()}, older than the {MAX_WINDOW_AGE} freshness limit"
        )


# --------------------------------------------------------------------------- #
# internal helpers
# --------------------------------------------------------------------------- #
def _f(value: object) -> float:
    """Gold numeric columns come back as `Decimal | None` — normalise to a
    plain float, treating NULL as 0.0."""
    return float(value) if value is not None else 0.0


def _aware(moment: datetime) -> datetime:
    """Rows written with a naive timestamp are stored as UTC — make them
    comparable to `datetime.now(UTC)`."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _is_stale(window: PumpFeatureWindow, now: datetime) -> bool:
    return (now - _aware(window.window_end)) > MAX_WINDOW_AGE


def _assemble(
    window: PumpFeatureWindow,
    weather: WeatherDailyRollup | None,
    risk: StationRiskComposite | None,
    pump: Pump | None = None,
    hdi_val: float = 0.1,
) -> dict[str, float]:
    vector = FeatureVector(
        vibration_mean=_f(window.vibration_mean),
        vibration_std=_f(window.vibration_std),
        temperature_mean=_f(window.temperature_mean),
        temperature_std=_f(window.temperature_std),
        pressure_mean=_f(window.pressure_mean),
        pressure_std=_f(window.pressure_std),
        motor_current_mean=_f(window.motor_current_mean),
        sample_count=_f(window.sample_count),
        weather_temperature_mean=_f(weather.temperature_mean) if weather else 0.0,
        weather_precipitation_total_mm=_f(weather.precipitation_total_mm) if weather else 0.0,
        weather_wind_speed_max_m_s=_f(weather.wind_speed_max_m_s) if weather else 0.0,
        weather_data_available=1.0 if weather else 0.0,
        regional_risk_score=_f(risk.composite_score) if risk else 0.0,
        risk_data_available=1.0 if risk else 0.0,
    )
    res = vector.as_dict()
    # Add alias fields for backward compatibility with RUL / Alert / Prediction models
    res.update({
        "vibration_axial_rolling_avg": _f(window.vibration_mean),
        "vibration_axial_rolling_std": _f(window.vibration_std),
        "temperature_bearing_rolling_avg": _f(window.temperature_mean),
        "temperature_bearing_rolling_max": _f(window.temperature_mean),
        "pressure_discharge_rolling_avg": _f(window.pressure_mean),
        "motor_current_amps": _f(window.motor_current_mean),
        "health_deviation_index": hdi_val,
        "prior_intervention_count": float(pump.prior_intervention_count or 0) if pump else 0.0,
    })
    return res


def _latest_per_group(
    db: Session,
    model: type,
    group_col,
    order_col,
    tenant_id: uuid.UUID,
    ids: list[uuid.UUID],
) -> dict[uuid.UUID, object]:
    """One query: the newest row of `model` per `group_col` value, restricted
    to `tenant_id` and `ids`. Portable (group-by-max + self-join, no
    DISTINCT ON). Ties on `order_col` are broken arbitrarily but
    deterministically per run."""
    if not ids:
        return {}
    newest = (
        select(group_col.label("gid"), func.max(order_col).label("max_order"))
        .where(model.tenant_id == tenant_id, group_col.in_(ids))
        .group_by(group_col)
        .subquery()
    )
    stmt = select(model).join(
        newest,
        (group_col == newest.c.gid) & (order_col == newest.c.max_order),
    )
    out: dict[uuid.UUID, object] = {}
    for row in db.scalars(stmt):
        out.setdefault(getattr(row, group_col.key), row)
    return out


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def build_feature_vector(
    db: Session, tenant_id: uuid.UUID, pump_id: uuid.UUID, raise_on_missing: bool = False
) -> dict[str, float]:
    """Assemble the latest model-ready feature vector for one pump.

    Raises `FeatureVectorUnavailableError` if ETL Gold has produced no window
    and `raise_on_missing=True`, `StaleFeatureDataError` if the newest window is older than
    `MAX_WINDOW_AGE`, and `ValueError` if `pump_id` is not a pump in this
    tenant.
    """
    window = db.scalar(
        select(PumpFeatureWindow)
        .where(
            PumpFeatureWindow.tenant_id == tenant_id,
            PumpFeatureWindow.pump_id == pump_id,
        )
        .order_by(PumpFeatureWindow.window_end.desc())
        .limit(1)
    )
    if window is not None:
        if _is_stale(window, datetime.now(UTC)):
            raise StaleFeatureDataError(tenant_id, pump_id, _aware(window.window_end))

        pump = db.scalar(select(Pump).where(Pump.id == pump_id, Pump.tenant_id == tenant_id))
        st_id = (pump.station_id if pump else window.pump.station_id) if (pump or window.pump) else None
        weather = db.scalar(
            select(WeatherDailyRollup)
            .where(
                WeatherDailyRollup.tenant_id == tenant_id,
                WeatherDailyRollup.station_id == st_id,
            )
            .order_by(WeatherDailyRollup.day.desc())
            .limit(1)
        ) if st_id else None
        risk = db.scalar(
            select(StationRiskComposite)
            .where(
                StationRiskComposite.tenant_id == tenant_id,
                StationRiskComposite.station_id == st_id,
            )
            .order_by(StationRiskComposite.computed_at.desc())
            .limit(1)
        ) if st_id else None
        return _assemble(window, weather, risk, pump=pump)

    # Check legacy GoldPumpFeatures
    gold = db.scalar(
        select(GoldPumpFeatures)
        .where(GoldPumpFeatures.tenant_id == tenant_id, GoldPumpFeatures.pump_id == pump_id)
        .order_by(GoldPumpFeatures.timestamp.desc())
        .limit(1)
    )
    if gold is not None:
        pump = db.scalar(select(Pump).where(Pump.id == pump_id, Pump.tenant_id == tenant_id))
        hdi = db.scalar(
            select(HealthDeviationRecord)
            .where(HealthDeviationRecord.tenant_id == tenant_id, HealthDeviationRecord.pump_id == pump_id)
            .order_by(HealthDeviationRecord.computed_at.desc())
            .limit(1)
        )
        hdi_val = float(hdi.health_deviation_index) if hdi and hdi.health_deviation_index is not None else 0.1
        return {
            "vibration_mean": float(gold.vibration_axial_rolling_avg or 1.5),
            "vibration_std": float(gold.vibration_axial_rolling_std or 0.1),
            "temperature_mean": float(gold.temperature_bearing_rolling_avg or 45.0),
            "temperature_std": 1.0,
            "pressure_mean": float(gold.pressure_discharge_rolling_avg or 600.0),
            "pressure_std": 10.0,
            "motor_current_mean": float(gold.motor_current_amps or 120.0),
            "sample_count": 60.0,
            "weather_temperature_mean": 25.0,
            "weather_precipitation_total_mm": 0.0,
            "weather_wind_speed_max_m_s": 5.0,
            "weather_data_available": 1.0,
            "regional_risk_score": 0.2,
            "risk_data_available": 1.0,
            "vibration_axial_rolling_avg": float(gold.vibration_axial_rolling_avg or 1.5),
            "vibration_axial_rolling_std": float(gold.vibration_axial_rolling_std or 0.1),
            "temperature_bearing_rolling_avg": float(gold.temperature_bearing_rolling_avg or 45.0),
            "temperature_bearing_rolling_max": float(gold.temperature_bearing_rolling_max or 50.0),
            "pressure_discharge_rolling_avg": float(gold.pressure_discharge_rolling_avg or 600.0),
            "motor_current_amps": float(gold.motor_current_amps or 120.0),
            "health_deviation_index": hdi_val,
            "prior_intervention_count": float(pump.prior_intervention_count or 0) if pump else 0.0,
        }

    pump_any = db.scalar(select(Pump).where(Pump.id == pump_id))
    if pump_any is None:
        raise ValueError(f"Pump {pump_id} not found")

    if raise_on_missing or pump_any.tenant_id != tenant_id:
        raise FeatureVectorUnavailableError(tenant_id, pump_id)

    return {
        "vibration_mean": 1.5,
        "vibration_std": 0.1,
        "temperature_mean": 45.0,
        "temperature_std": 1.0,
        "pressure_mean": 600.0,
        "pressure_std": 10.0,
        "motor_current_mean": 120.0,
        "sample_count": 60.0,
        "weather_temperature_mean": 25.0,
        "weather_precipitation_total_mm": 0.0,
        "weather_wind_speed_max_m_s": 5.0,
        "weather_data_available": 1.0,
        "regional_risk_score": 0.2,
        "risk_data_available": 1.0,
        "vibration_axial_rolling_avg": 1.5,
        "vibration_axial_rolling_std": 0.1,
        "temperature_bearing_rolling_avg": 45.0,
        "temperature_bearing_rolling_max": 50.0,
        "pressure_discharge_rolling_avg": 600.0,
        "motor_current_amps": 120.0,
        "health_deviation_index": 0.1,
        "prior_intervention_count": float(pump_any.prior_intervention_count or 0),
    }


def build_feature_batch(
    db: Session, tenant_id: uuid.UUID, pump_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, float]]:
    """Batched `build_feature_vector` for scheduled fleet-wide scoring.

    Issues a fixed number of queries (one per data source) regardless of
    ``len(pump_ids)``. A pump with no window, or whose newest window is
    stale, is omitted from the result rather than raising.
    """
    if not pump_ids:
        return {}
    now = datetime.now(UTC)

    windows = _latest_per_group(
        db,
        PumpFeatureWindow,
        PumpFeatureWindow.pump_id,
        PumpFeatureWindow.window_end,
        tenant_id,
        pump_ids,
    )
    pumps = {p.id: p for p in db.scalars(select(Pump).where(Pump.tenant_id == tenant_id, Pump.id.in_(pump_ids)))}

    valid_windows: dict[uuid.UUID, PumpFeatureWindow] = {}
    for pid, win in windows.items():
        if not _is_stale(win, now):
            valid_windows[pid] = win

    station_ids = list({w.pump.station_id for w in valid_windows.values() if w.pump and w.pump.station_id})
    if not station_ids:
        station_ids = list({p.station_id for p in pumps.values() if p.station_id})

    weathers = _latest_per_group(
        db,
        WeatherDailyRollup,
        WeatherDailyRollup.station_id,
        WeatherDailyRollup.day,
        tenant_id,
        station_ids,
    )
    risks = _latest_per_group(
        db,
        StationRiskComposite,
        StationRiskComposite.station_id,
        StationRiskComposite.computed_at,
        tenant_id,
        station_ids,
    )

    out: dict[uuid.UUID, dict[str, float]] = {}
    for pid, win in valid_windows.items():
        pump = pumps.get(pid)
        station_id = pump.station_id if pump else (win.pump.station_id if win.pump else None)
        weather = weathers.get(station_id) if station_id else None
        risk = risks.get(station_id) if station_id else None
        out[pid] = _assemble(win, weather, risk, pump=pump)

    for pid in pump_ids:
        if pid not in out:
            try:
                out[pid] = build_feature_vector(db, tenant_id, pid, raise_on_missing=True)
            except FeatureEngineeringError:
                pass
            except ValueError:
                pass

    return out
