"""Business logic for alerts.

`create_alert`/read functions are implemented (plain persistence, not
"logic"). Deciding *when* to raise an alert from a Diagnostic result
(pressure residual, risk score, RUL) is threshold-evaluation logic that
belongs to a future `evaluate_thresholds`-style function — not implemented
yet.
"""
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alert.models import Alert, AlertStatus
from app.alert.schemas import AlertCreate, AlertUpdate
from app.audit.services import record_event
from app.core.permissions import Permission, has_permission
from app.user.models import User
from app.pump.models import Pump
from app.station.models import Station


def create_alert(db: Session, tenant_id: uuid.UUID, payload: AlertCreate) -> Alert:
    pump = db.scalar(select(Pump).where(Pump.id == payload.pump_id, Pump.tenant_id == tenant_id))
    station = db.scalar(select(Station).where(Station.id == payload.station_id, Station.tenant_id == tenant_id))
    if pump is None or station is None or pump.station_id != station.id:
        raise HTTPException(422, "Pump and station must belong to this organisation and match")
    alert = Alert(tenant_id=tenant_id, **payload.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def get_alert(db: Session, tenant_id: uuid.UUID, alert_id: uuid.UUID) -> Alert | None:
    return db.scalar(select(Alert).where(Alert.id == alert_id, Alert.tenant_id == tenant_id))


def list_alerts(
    db: Session,
    tenant_id: uuid.UUID,
    status_filter: AlertStatus | None = None,
    pump_id: uuid.UUID | None = None,
) -> list[Alert]:
    stmt = select(Alert).where(Alert.tenant_id == tenant_id)
    if status_filter is not None:
        stmt = stmt.where(Alert.status == status_filter)
    if pump_id is not None:
        stmt = stmt.where(Alert.pump_id == pump_id)
    return list(db.scalars(stmt.order_by(Alert.triggered_at.desc())))


def update_alert(
    db: Session,
    tenant_id: uuid.UUID,
    alert_id: uuid.UUID,
    payload: AlertUpdate,
    actor_user_id: uuid.UUID | None = None,
) -> Alert | None:
    alert = db.scalar(select(Alert).where(
        Alert.id == alert_id, Alert.tenant_id == tenant_id).with_for_update())
    if alert is None:
        return None
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is None:
        raise HTTPException(422, "Status is required")
    if alert.status == AlertStatus.RESOLVED:
        raise HTTPException(409, "Resolved incidents cannot be changed")
    if changes.get("status") == AlertStatus.TRIGGERED and alert.status != AlertStatus.TRIGGERED:
        raise HTTPException(409, "An acknowledged incident cannot return to triggered")
    owner_id = changes.get("assigned_to_user_id")
    if owner_id:
        owner = db.scalar(select(User).where(User.id == owner_id,
            User.tenant_id == tenant_id, User.is_active.is_(True)))
        if owner is None or not has_permission(owner.role.value, Permission.MANAGE_ALERTS):
            raise HTTPException(422, "Choose an active incident owner in this organisation")
    target = changes.get("status", alert.status)
    if target == AlertStatus.RESOLVED:
        if not (changes.get("resolution_note") or "").strip():
            raise HTTPException(422, "Explain the resolution before resolving the incident")
        changes["resolved_at"] = datetime.now(UTC)
    elif "resolution_note" in changes:
        raise HTTPException(422, "Resolution notes require a resolved status")
    if target == AlertStatus.ACKNOWLEDGED and alert.acknowledged_at is None:
        changes["acknowledged_at"] = datetime.now(UTC)
    previous = {key: getattr(alert, key) for key in changes}
    for field, value in changes.items():
        setattr(alert, field, value)
    record_event(
        db, tenant_id, actor_user_id, "alert", alert.id, "updated",
        previous_value={key: str(value) for key, value in previous.items()},
        new_value={key: str(value) for key, value in changes.items()},
    )
    db.commit()
    db.refresh(alert)
    return alert


def evaluate_thresholds(db: Session, tenant_id: uuid.UUID, pump_id: uuid.UUID) -> list[Alert]:
    """Compare the latest Flowgard/prediction/RUL results against the
    tenant's configured thresholds (app.tenant) and raise alerts as needed.
    Not implemented yet.
    """
    raise NotImplementedError("alert threshold evaluation is not implemented yet")
