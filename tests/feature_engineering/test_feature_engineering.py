"""Tests for app.feature_engineering — services.py only, no HTTP surface.

Covers the Gold-layer read/flatten contract: happy path, the two typed
error conditions, graceful weather/risk absence, tenant isolation, and the
batch path's partial-failure + bounded-query behaviour.
"""
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.etl.gold.models import PumpFeatureWindow, StationRiskComposite, WeatherDailyRollup
from app.feature_engineering import services
from app.feature_engineering.schemas import FEATURE_KEYS
from app.pump.models import Pump, PumpStatus

NOW = datetime.now(UTC)
FRESH_END = NOW - timedelta(minutes=1)
STALE_END = NOW - services.MAX_WINDOW_AGE - timedelta(minutes=5)


# --------------------------------------------------------------------------- #
# builders (inline ORM, matching tests/prediction/test_prediction.py style)
# --------------------------------------------------------------------------- #
def _make_pump(db: Session, station, tag: str = "PS1-P01") -> Pump:
    pump = Pump(
        tenant_id=station.tenant_id,
        station_id=station.id,
        tag_number=tag,
        status=PumpStatus.OPERATIONAL,
    )
    db.add(pump)
    db.commit()
    db.refresh(pump)
    return pump


def _make_window(
    db: Session,
    tenant_id: uuid.UUID,
    pump_id: uuid.UUID,
    *,
    window_end: datetime = FRESH_END,
    vibration_mean=2.0,
    vibration_std=0.4,
    temperature_mean=48.0,
    temperature_std=1.1,
    pressure_mean=4100.0,
    pressure_std=30.0,
    motor_current_mean=12.5,
    sample_count=60,
) -> PumpFeatureWindow:
    row = PumpFeatureWindow(
        tenant_id=tenant_id,
        pump_id=pump_id,
        window_start=window_end - timedelta(minutes=5),
        window_end=window_end,
        vibration_mean=vibration_mean,
        vibration_std=vibration_std,
        temperature_mean=temperature_mean,
        temperature_std=temperature_std,
        pressure_mean=pressure_mean,
        pressure_std=pressure_std,
        motor_current_mean=motor_current_mean,
        sample_count=sample_count,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_weather(
    db: Session, tenant_id: uuid.UUID, station_id: uuid.UUID, *, day: datetime = NOW
) -> WeatherDailyRollup:
    row = WeatherDailyRollup(
        tenant_id=tenant_id,
        station_id=station_id,
        day=day,
        temperature_mean=25.0,
        precipitation_total_mm=3.5,
        wind_speed_max_m_s=7.0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_risk(
    db: Session, tenant_id: uuid.UUID, station_id: uuid.UUID, *, computed_at: datetime = NOW
) -> StationRiskComposite:
    row = StationRiskComposite(
        tenant_id=tenant_id,
        station_id=station_id,
        computed_at=computed_at,
        composite_score=0.62,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@contextmanager
def _count_queries(db: Session):
    """Count SELECT round-trips issued on the session's bind. No such helper
    exists elsewhere in the suite, so this uses SQLAlchemy's own event hook
    rather than a bespoke session spy."""
    bind = db.get_bind()
    counter = {"n": 0}

    def _on_exec(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            counter["n"] += 1

    event.listen(bind, "after_cursor_execute", _on_exec)
    try:
        yield counter
    finally:
        event.remove(bind, "after_cursor_execute", _on_exec)


# --------------------------------------------------------------------------- #
# build_feature_vector
# --------------------------------------------------------------------------- #
def test_happy_path_flattens_all_three_tiers(db_session: Session, station_a):
    pump = _make_pump(db_session, station_a)
    _make_window(db_session, station_a.tenant_id, pump.id)
    _make_weather(db_session, station_a.tenant_id, station_a.id)
    _make_risk(db_session, station_a.tenant_id, station_a.id)

    vec = services.build_feature_vector(db_session, station_a.tenant_id, pump.id)

    assert set(FEATURE_KEYS).issubset(set(vec.keys()))
    assert all(isinstance(v, float) for v in vec.values())
    # sensor tier
    assert vec["vibration_mean"] == 2.0
    assert vec["pressure_std"] == 30.0
    assert vec["sample_count"] == 60.0
    # weather tier
    assert vec["weather_temperature_mean"] == 25.0
    assert vec["weather_precipitation_total_mm"] == 3.5
    assert vec["weather_data_available"] == 1.0
    # risk tier
    assert vec["regional_risk_score"] == 0.62
    assert vec["risk_data_available"] == 1.0


def test_no_window_raises_unavailable(db_session: Session, station_a):
    pump = _make_pump(db_session, station_a)
    with pytest.raises(services.FeatureVectorUnavailableError) as exc:
        services.build_feature_vector(db_session, station_a.tenant_id, pump.id, raise_on_missing=True)
    assert exc.value.pump_id == pump.id
    assert exc.value.tenant_id == station_a.tenant_id


def test_stale_window_raises_stale(db_session: Session, station_a):
    pump = _make_pump(db_session, station_a)
    _make_window(db_session, station_a.tenant_id, pump.id, window_end=STALE_END)

    with pytest.raises(services.StaleFeatureDataError) as exc:
        services.build_feature_vector(db_session, station_a.tenant_id, pump.id)
    assert exc.value.last_window_end.year == STALE_END.year
    assert str(services.MAX_WINDOW_AGE) in str(exc.value)


def test_missing_weather_and_risk_degrade_gracefully(db_session: Session, station_a):
    pump = _make_pump(db_session, station_a)
    _make_window(db_session, station_a.tenant_id, pump.id)

    vec = services.build_feature_vector(db_session, station_a.tenant_id, pump.id)

    assert vec["weather_data_available"] == 0.0
    assert vec["risk_data_available"] == 0.0
    assert vec["weather_temperature_mean"] == 0.0
    assert vec["regional_risk_score"] == 0.0
    # sensor tier still fully populated
    assert vec["vibration_mean"] == 2.0


def test_null_columns_in_window_fill_zero(db_session: Session, station_a):
    pump = _make_pump(db_session, station_a)
    _make_window(
        db_session,
        station_a.tenant_id,
        pump.id,
        vibration_std=None,
        motor_current_mean=None,
    )

    vec = services.build_feature_vector(db_session, station_a.tenant_id, pump.id)
    assert vec["vibration_std"] == 0.0
    assert vec["motor_current_mean"] == 0.0
    assert vec["vibration_mean"] == 2.0


def test_tenant_isolation(db_session: Session, station_a, station_b):
    """A window under tenant B must not satisfy a tenant-A request for the
    same pump id."""
    pump_b = _make_pump(db_session, station_b, tag="PS1-PB1")
    _make_window(db_session, station_b.tenant_id, pump_b.id)

    with pytest.raises(services.FeatureVectorUnavailableError):
        services.build_feature_vector(db_session, station_a.tenant_id, pump_b.id)


# --------------------------------------------------------------------------- #
# build_feature_batch
# --------------------------------------------------------------------------- #
def test_batch_omits_pumps_without_a_fresh_window(db_session: Session, station_a):
    full = _make_pump(db_session, station_a, tag="PS1-P01")
    _make_window(db_session, station_a.tenant_id, full.id)
    _make_weather(db_session, station_a.tenant_id, station_a.id)

    no_data = _make_pump(db_session, station_a, tag="PS1-P02")
    stale = _make_pump(db_session, station_a, tag="PS1-P03")
    _make_window(db_session, station_a.tenant_id, stale.id, window_end=STALE_END)

    out = services.build_feature_batch(
        db_session, station_a.tenant_id, [full.id, no_data.id, stale.id]
    )

    assert set(out) == {full.id}
    assert out[full.id]["weather_data_available"] == 1.0
    assert out[full.id]["vibration_mean"] == 2.0


def test_batch_empty_input_returns_empty(db_session: Session, station_a):
    assert services.build_feature_batch(db_session, station_a.tenant_id, []) == {}


def test_batch_query_count_is_bounded(db_session: Session, station_a, station_b):
    """Query count must not grow with the number of pumps."""

    def _fleet(station, n: int) -> list[uuid.UUID]:
        ids = []
        for i in range(n):
            p = _make_pump(db_session, station, tag=f"{station.code}-B{i}")
            _make_window(db_session, station.tenant_id, p.id)
            ids.append(p.id)
        _make_weather(db_session, station.tenant_id, station.id)
        _make_risk(db_session, station.tenant_id, station.id)
        return ids

    tenant_a_id = station_a.tenant_id
    tenant_b_id = station_b.tenant_id

    small = _fleet(station_a, 1)
    # Read args before opening the counter so an expired-attribute refresh
    # doesn't get counted as one of the batch's queries.
    with _count_queries(db_session) as c1:
        services.build_feature_batch(db_session, tenant_a_id, small)
    small_count = c1["n"]

    large = _fleet(station_b, 6)
    with _count_queries(db_session) as c2:
        services.build_feature_batch(db_session, tenant_b_id, large)
    large_count = c2["n"]

    assert small_count == large_count
    # window + pump + weather + risk
    assert large_count == 4


def test_batch_matches_single_for_a_fresh_pump(db_session: Session, station_a):
    pump = _make_pump(db_session, station_a)
    _make_window(db_session, station_a.tenant_id, pump.id)
    _make_weather(db_session, station_a.tenant_id, station_a.id)
    _make_risk(db_session, station_a.tenant_id, station_a.id)

    single = services.build_feature_vector(db_session, station_a.tenant_id, pump.id)
    batch = services.build_feature_batch(db_session, station_a.tenant_id, [pump.id])

    assert batch[pump.id] == single
