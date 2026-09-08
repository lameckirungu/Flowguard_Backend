"""Smoke tests for the maintenance_schedule module: router registration + tenant scoping."""
from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.maintenance_schedule import services
from app.maintenance_schedule.schemas import ScheduledMaintenanceCreate
from app.pump.models import Pump, PumpStatus


def test_router_registered():
    from app.main import app

    assert any(path.startswith("/api/v1/maintenance-schedule") for path in app.openapi()["paths"])


def test_list_requires_auth(client):
    response = client.get("/api/v1/maintenance-schedule")
    assert response.status_code == 401


def test_service_enforces_tenant_scope(db_session: Session, station_a, station_b):
    pump_a = Pump(
        tenant_id=station_a.tenant_id,
        station_id=station_a.id,
        tag_number="PS1-P01",
        status=PumpStatus.OPERATIONAL,
    )
    db_session.add(pump_a)
    db_session.commit()
    db_session.refresh(pump_a)

    entry_a = services.create_scheduled_maintenance(
        db_session,
        station_a.tenant_id,
        ScheduledMaintenanceCreate(
            pump_id=pump_a.id,
            station_id=station_a.id,
            scheduled_date=date.today() + timedelta(days=14),
        ),
    )

    assert [e.id for e in services.list_scheduled_maintenance(db_session, station_a.tenant_id)] == [
        entry_a.id
    ]
    assert services.list_scheduled_maintenance(db_session, station_b.tenant_id) == []


def test_rank_schedule_by_rul_success(db_session: Session, station_a):
    pump = Pump(
        tenant_id=station_a.tenant_id,
        station_id=station_a.id,
        tag_number="PS1-P02",
        status=PumpStatus.OPERATIONAL,
    )
    db_session.add(pump)
    db_session.commit()

    services.create_scheduled_maintenance(
        db_session,
        station_a.tenant_id,
        ScheduledMaintenanceCreate(
            pump_id=pump.id,
            station_id=station_a.id,
            scheduled_date=date.today() + timedelta(days=7),
        ),
    )

    ranked = services.rank_schedule_by_rul(db_session, station_a.tenant_id)
    assert len(ranked) >= 1
    assert ranked[0].priority_rank == 1


def test_maintenance_schedule_routes_crud(client, headers_a, station_a, db_session):
    pump = Pump(
        tenant_id=station_a.tenant_id,
        station_id=station_a.id,
        tag_number="PS1-P03",
        status=PumpStatus.OPERATIONAL,
    )
    db_session.add(pump)
    db_session.commit()

    # Create schedule via HTTP
    res = client.post(
        "/api/v1/maintenance-schedule",
        json={
            "pump_id": str(pump.id),
            "station_id": str(station_a.id),
            "scheduled_date": (date.today() + timedelta(days=10)).isoformat(),
        },
        headers=headers_a,
    )
    assert res.status_code == 201
    entry_id = res.json()["id"]

    # List schedules via HTTP
    res = client.get("/api/v1/maintenance-schedule", headers=headers_a)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Get single schedule via HTTP
    res = client.get(f"/api/v1/maintenance-schedule/{entry_id}", headers=headers_a)
    assert res.status_code == 200

    # Update schedule via HTTP
    res = client.patch(
        f"/api/v1/maintenance-schedule/{entry_id}",
        json={"status": "confirmed"},
        headers=headers_a,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "confirmed"

    # Trigger RUL ranking via HTTP
    res = client.post("/api/v1/maintenance-schedule/rank", headers=headers_a)
    assert res.status_code == 200

    # 404 test
    res = client.get("/api/v1/maintenance-schedule/00000000-0000-0000-0000-000000000000", headers=headers_a)
    assert res.status_code == 404
