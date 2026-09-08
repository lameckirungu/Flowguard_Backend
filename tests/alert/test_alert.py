"""Smoke tests for the alert module: router registration + tenant scoping."""
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.alert import services
from app.alert.models import AlertSeverity
from app.alert.schemas import AlertCreate
from app.pump.models import Pump, PumpStatus


def test_router_registered():
    from app.main import app

    assert any(path.startswith("/api/v1/alerts") for path in app.openapi()["paths"])


def test_list_alerts_requires_auth(client):
    response = client.get("/api/v1/alerts")
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

    alert_a = services.create_alert(
        db_session,
        station_a.tenant_id,
        AlertCreate(
            pump_id=pump_a.id,
            station_id=station_a.id,
            severity=AlertSeverity.WARNING,
            message="Vibration above threshold",
            triggered_at=datetime.now(UTC),
        ),
    )

    assert [a.id for a in services.list_alerts(db_session, station_a.tenant_id)] == [alert_a.id]
    assert services.list_alerts(db_session, station_b.tenant_id) == []
    assert services.get_alert(db_session, station_b.tenant_id, alert_a.id) is None


def test_alert_routes_crud(client, headers_a, station_a, db_session):
    pump = Pump(
        tenant_id=station_a.tenant_id,
        station_id=station_a.id,
        tag_number="PS1-P02",
        status=PumpStatus.OPERATIONAL,
    )
    db_session.add(pump)
    db_session.commit()

    # Create alert via HTTP
    res = client.post(
        "/api/v1/alerts",
        json={
            "pump_id": str(pump.id),
            "station_id": str(station_a.id),
            "severity": "critical",
            "message": "High bearing temp",
            "triggered_at": datetime.now(UTC).isoformat(),
        },
        headers=headers_a,
    )
    assert res.status_code == 201
    alert_id = res.json()["id"]

    # List alerts via HTTP
    res = client.get("/api/v1/alerts", headers=headers_a)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Get single alert via HTTP
    res = client.get(f"/api/v1/alerts/{alert_id}", headers=headers_a)
    assert res.status_code == 200
    assert res.json()["message"] == "High bearing temp"

    # Acknowledge/update alert via HTTP
    res = client.patch(
        f"/api/v1/alerts/{alert_id}",
        json={"status": "acknowledged"},
        headers=headers_a,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "acknowledged"

    # 404 test
    res = client.get("/api/v1/alerts/00000000-0000-0000-0000-000000000000", headers=headers_a)
    assert res.status_code == 404


def test_evaluate_thresholds(client, headers_a, station_a, db_session):
    pump = Pump(
        tenant_id=station_a.tenant_id,
        station_id=station_a.id,
        tag_number="PS1-P03",
        status=PumpStatus.OPERATIONAL,
    )
    db_session.add(pump)
    db_session.commit()

    res = client.post(f"/api/v1/alerts/pumps/{pump.id}/evaluate", headers=headers_a)
    assert res.status_code == 200
    assert isinstance(res.json(), list)
