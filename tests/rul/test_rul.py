"""Smoke tests for the rul module: router registration + tenant scoping."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.pump.models import Pump, PumpStatus
from app.rul import services
from app.station.models import Station


def test_router_registered():
    from app.main import app

    assert any(path.startswith("/api/v1/rul") for path in app.openapi()["paths"])


def test_list_requires_auth(client):
    response = client.get("/api/v1/rul")
    assert response.status_code == 401


def test_list_is_tenant_scoped_and_empty_for_unknown_pump(db_session: Session, tenant_a):
    assert services.list_rul_estimates(db_session, tenant_a.id) == []
    assert services.get_latest_rul_estimate(db_session, tenant_a.id, uuid.uuid4()) is None


def test_run_rul_estimate_success(db_session: Session, tenant_a):
    station = Station(tenant_id=tenant_a.id, code="ST1", name="Station 1")
    db_session.add(station)
    db_session.commit()

    pump = Pump(tenant_id=tenant_a.id, station_id=station.id, tag_number="PUMP-RUL-01", status=PumpStatus.OPERATIONAL)
    db_session.add(pump)
    db_session.commit()

    estimate = services.run_rul_estimate(db_session, tenant_a.id, pump.id)
    assert estimate.pump_id == pump.id
    assert estimate.remaining_useful_life_days > 0
    assert estimate.confidence_lower_days <= estimate.remaining_useful_life_days
    assert estimate.confidence_upper_days >= estimate.remaining_useful_life_days
