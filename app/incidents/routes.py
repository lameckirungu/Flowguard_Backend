import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select

from app.alert.models import Alert
from app.audit.models import AuditEvent
from app.core.auth import CurrentUser, require_permission
from app.core.db import get_db
from app.core.permissions import Permission
from app.incidents import services
from app.incidents.schemas import IncidentFilters, PolicyWrite
from app.reporting.csv import csv_response
from app.user.models import User
from app.work_order.models import WorkOrder

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])
reader = require_permission(Permission.VIEW_OPERATIONS)


@router.get("")
def queue(filters: IncidentFilters = Depends(), db=Depends(get_db), current=Depends(reader)):
    return services.queue(db, current.tenant_id, filters)


@router.get("/policy")
def policy(db=Depends(get_db), current=Depends(reader)):
    return services.policy(db, current.tenant_id)


@router.put("/policy")
def save_policy(payload: PolicyWrite, db=Depends(get_db),
                current=Depends(require_permission(Permission.MANAGE_TENANT))):
    return services.save_policy(db, current, payload)


@router.get("/owners")
def owners(db=Depends(get_db), current=Depends(require_permission(Permission.MANAGE_ALERTS))):
    return services.owners(db, current.tenant_id)


@router.get("/export.csv")
def export(filters: IncidentFilters = Depends(), db=Depends(get_db),
           current=Depends(require_permission(Permission.EXPORT_REPORTS))):
    result = services.queue(db, current.tenant_id, filters, export=True)
    columns = ["reference", "pump_code", "station_code", "station_name", "severity", "status",
               "owner_name", "message", "triggered_at", "acknowledged_at", "resolved_at",
               "acknowledge_due_at", "response_due_at", "acknowledgement_overdue",
               "response_overdue", "resolution_note"]
    return csv_response("flowgard-incidents.csv", columns, result["items"])


@router.get("/{incident_id}/history")
def history(incident_id: uuid.UUID, db=Depends(get_db), current=Depends(reader)):
    tenant = current.tenant_id
    if db.scalar(select(Alert.id).where(Alert.id == incident_id, Alert.tenant_id == tenant)) is None:
        raise HTTPException(404, "Incident not found")
    rows = db.execute(select(AuditEvent, User.email).outerjoin(User, and_(
        User.id == AuditEvent.actor_user_id, User.tenant_id == tenant)).where(
        AuditEvent.tenant_id == tenant, AuditEvent.entity_type == "alert",
        AuditEvent.entity_id == incident_id).order_by(AuditEvent.created_at.desc()).limit(100))
    work = db.scalars(select(WorkOrder).where(WorkOrder.tenant_id == tenant,
        WorkOrder.source_alert_id == incident_id).order_by(WorkOrder.created_at.desc()).limit(100))
    return {"events": [{"id": e.id, "action": e.action, "actor": actor or "System",
                        "at": e.created_at, "before": e.previous_value, "after": e.new_value}
                       for e, actor in rows],
            "work_orders": [{"id": w.id, "reference": f"WO-{str(w.id)[:8].upper()}",
                             "title": w.title, "status": w.status.value} for w in work]}
