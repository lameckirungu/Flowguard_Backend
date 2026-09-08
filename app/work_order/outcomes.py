from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import and_, select

from app.audit.models import AuditEvent
from app.audit.services import record_event
from app.user.models import User
from app.work_order.models import WorkOrder, WorkOrderStatus

EVIDENCE = ("completion_note", "outcome", "post_maintenance_condition", "root_cause",
            "corrective_action", "downtime_minutes", "follow_up_required", "follow_up_due_at",
            "completed_by_user_id", "closed_at", "verified_at", "verified_by_user_id",
            "verification_result", "verification_note")


def snapshot(row):
    return {key: str(getattr(row, key)) if getattr(row, key) is not None else None for key in EVIDENCE}


def locked(db, tenant, identifier):
    row = db.scalar(select(WorkOrder).where(
        WorkOrder.id == identifier, WorkOrder.tenant_id == tenant).with_for_update())
    if row is None:
        raise HTTPException(404, "Work order not found")
    return row


def correction_allowed(row, current, reason, already_recorded):
    if already_recorded and (current.role not in {"admin", "planner"} or not reason):
        raise HTTPException(403, "A planner or administrator must provide a correction reason")


def record_outcome(db, current, identifier, payload):
    row = locked(db, current.tenant_id, identifier)
    if row.status == WorkOrderStatus.CANCELLED:
        raise HTTPException(409, "Cancelled work cannot receive an outcome")
    correction_allowed(row, current, payload.correction_reason, row.outcome is not None)
    before = snapshot(row)
    for field, value in payload.model_dump(exclude={"correction_reason"}).items():
        setattr(row, field, value)
    if row.status != WorkOrderStatus.COMPLETED:
        row.closed_at = datetime.now(UTC)
        row.completed_by_user_id = current.id
    row.status = WorkOrderStatus.COMPLETED
    # Editing the evidence invalidates previous verification without erasing its audit event.
    row.verified_at = row.verified_by_user_id = None
    row.verification_result = row.verification_note = None
    record_event(db, current.tenant_id, current.id, "work_order", row.id, "outcome_recorded",
                 before, {**snapshot(row), "correction_reason": payload.correction_reason})
    db.commit()
    db.refresh(row)
    return row


def verify(db, current, identifier, payload):
    row = locked(db, current.tenant_id, identifier)
    if row.status != WorkOrderStatus.COMPLETED or row.outcome is None:
        raise HTTPException(409, "Record a completed maintenance outcome before verification")
    correction_allowed(row, current, payload.correction_reason, row.verified_at is not None)
    if payload.result == "passed" and row.post_maintenance_condition != "serviceable":
        raise HTTPException(422, "A passing verification requires a serviceable recorded condition")
    before = snapshot(row)
    row.verified_at, row.verified_by_user_id = datetime.now(UTC), current.id
    row.verification_result, row.verification_note = payload.result, payload.note
    if payload.result == "failed":
        row.follow_up_required = True
    record_event(db, current.tenant_id, current.id, "work_order", row.id, "repair_verified",
                 before, {**snapshot(row), "correction_reason": payload.correction_reason})
    db.commit()
    db.refresh(row)
    return row


def follow_up(db, current, identifier):
    row = locked(db, current.tenant_id, identifier)
    if row.status != WorkOrderStatus.COMPLETED or not row.follow_up_required:
        raise HTTPException(409, "A completed record requiring follow-up is needed")
    existing = db.scalar(select(WorkOrder).where(WorkOrder.tenant_id == current.tenant_id,
        WorkOrder.parent_work_order_id == row.id,
        WorkOrder.status.in_([WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS])))
    if existing:
        return existing
    child = WorkOrder(tenant_id=current.tenant_id, pump_id=row.pump_id, station_id=row.station_id,
        title=f"Follow-up: {row.title}"[:250], description=row.verification_note or row.completion_note,
        parent_work_order_id=row.id, created_by_user_id=current.id, priority=row.priority,
        due_at=row.follow_up_due_at, source_alert_id=row.source_alert_id,
        source_prediction_id=row.source_prediction_id)
    db.add(child)
    db.flush()
    record_event(db, current.tenant_id, current.id, "work_order", child.id, "follow_up_created",
                 new_value={"parent_reference": f"WO-{str(row.id)[:8].upper()}"})
    db.commit()
    db.refresh(child)
    return child


def history(db, tenant, identifier):
    if db.scalar(select(WorkOrder.id).where(WorkOrder.id == identifier, WorkOrder.tenant_id == tenant)) is None:
        raise HTTPException(404, "Work order not found")
    rows = db.execute(select(AuditEvent, User.email).outerjoin(User, and_(
        User.id == AuditEvent.actor_user_id, User.tenant_id == tenant)).where(
        AuditEvent.tenant_id == tenant, AuditEvent.entity_type == "work_order",
        AuditEvent.entity_id == identifier).order_by(AuditEvent.created_at.desc()).limit(100))
    return [{"id": e.id, "action": e.action, "actor": actor or "System", "at": e.created_at,
             "before": e.previous_value, "after": e.new_value} for e, actor in rows]
