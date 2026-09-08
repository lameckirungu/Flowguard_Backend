from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select

from app.alert.models import Alert, AlertStatus
from app.audit.services import record_event
from app.incidents.models import IncidentPolicy
from app.pump.models import Pump
from app.station.models import Station
from app.tenant.models import Tenant
from app.user.models import User, UserRole

DEFAULTS = {
    "critical": {"acknowledge_minutes": 30, "response_minutes": 120},
    "warning": {"acknowledge_minutes": 240, "response_minutes": 1440},
    "info": {"acknowledge_minutes": 1440, "response_minutes": 4320},
}


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def policy(db, tenant_id):
    row = db.scalar(select(IncidentPolicy).where(
        IncidentPolicy.tenant_id == tenant_id
    ).order_by(IncidentPolicy.revision.desc()).limit(1))
    return {"revision": row.revision if row else 0,
            "deadlines": row.deadlines if row else DEFAULTS,
            "applies_to": "All unresolved incidents; deadlines start at trigger time",
            "response_definition": "Resolution with an explanation"}


def save_policy(db, current, payload):
    db.scalar(select(Tenant).where(Tenant.id == current.tenant_id).with_for_update())
    previous = policy(db, current.tenant_id)
    if previous["revision"] != payload.expected_revision:
        raise HTTPException(409, "Policy changed; refresh before saving")
    row = IncidentPolicy(tenant_id=current.tenant_id, revision=previous["revision"] + 1,
        deadlines=payload.model_dump(exclude={"expected_revision"}),
        created_at=datetime.now(UTC), created_by_user_id=current.id)
    db.add(row)
    db.flush()
    record_event(db, current.tenant_id, current.id, "incident_policy", row.id,
                 "revised", previous, {"revision": row.revision, "deadlines": row.deadlines})
    db.commit()
    return policy(db, current.tenant_id)


def owners(db, tenant_id):
    return [{"id": u.id, "name": u.full_name, "email": u.email} for u in db.scalars(
        select(User).where(User.tenant_id == tenant_id, User.is_active.is_(True),
            User.role.in_([UserRole.ADMIN, UserRole.PLANNER, UserRole.TECHNICIAN]))
        .order_by(User.full_name, User.id))]


def queue(db, tenant_id, filters, *, export=False):
    now = datetime.now(UTC)
    rules = policy(db, tenant_id)
    conditions = [Alert.tenant_id == tenant_id]
    if filters.status:
        conditions.append(Alert.status == filters.status)
    if filters.severity:
        conditions.append(Alert.severity == filters.severity)
    if filters.owner_id:
        conditions.append(Alert.assigned_to_user_id == filters.owner_id)
    if filters.unassigned:
        conditions.append(Alert.assigned_to_user_id.is_(None))
    if filters.overdue:
        breaches = []
        for severity, times in rules["deadlines"].items():
            breaches.append(and_(Alert.severity == severity, or_(
                and_(Alert.status == AlertStatus.TRIGGERED,
                     Alert.triggered_at < now - timedelta(minutes=times["acknowledge_minutes"])),
                Alert.triggered_at < now - timedelta(minutes=times["response_minutes"]))))
        conditions.extend([Alert.status != AlertStatus.RESOLVED, or_(*breaches)])
    total = db.scalar(select(func.count()).select_from(Alert).where(*conditions))
    query = select(Alert, Pump.tag_number, Station.code, Station.name, User.full_name).outerjoin(
        Pump, and_(Pump.id == Alert.pump_id, Pump.tenant_id == tenant_id)).outerjoin(
        Station, and_(Station.id == Alert.station_id, Station.tenant_id == tenant_id)).outerjoin(
        User, and_(User.id == Alert.assigned_to_user_id, User.tenant_id == tenant_id)
    ).where(*conditions).order_by(Alert.triggered_at.desc(), Alert.id)
    if export and total > 10000:
        raise HTTPException(422, "Export exceeds 10,000 incidents; narrow the filters")
    if not export:
        query = query.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
    items = []
    for alert, pump, code, station, owner in db.execute(query):
        times = rules["deadlines"][alert.severity.value]
        ack = utc(alert.triggered_at) + timedelta(minutes=times["acknowledge_minutes"])
        response = utc(alert.triggered_at) + timedelta(minutes=times["response_minutes"])
        items.append({"id": alert.id, "reference": f"INC-{str(alert.id)[:8].upper()}",
            "pump_code": pump or "Unknown pump", "station_code": code or "",
            "station_name": station or "Unknown station", "message": alert.message,
            "severity": alert.severity.value, "status": alert.status.value,
            "owner_id": alert.assigned_to_user_id, "owner_name": owner or "Unassigned",
            "triggered_at": alert.triggered_at, "acknowledged_at": alert.acknowledged_at,
            "resolved_at": alert.resolved_at, "resolution_note": alert.resolution_note,
            "acknowledge_due_at": ack, "response_due_at": response,
            "acknowledgement_overdue": alert.status == AlertStatus.TRIGGERED and now > ack,
            "response_overdue": alert.status != AlertStatus.RESOLVED and now > response})
    return {"items": items, "total": total, "page": filters.page,
            "page_size": filters.page_size, "policy_revision": rules["revision"], "as_of": now}
