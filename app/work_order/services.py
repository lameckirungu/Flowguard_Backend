"""Business logic for work orders."""
import uuid
from datetime import UTC, datetime
from fastapi import HTTPException

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alert.models import Alert, AlertStatus
from app.audit.services import record_event
from app.prediction.services import get_latest_prediction, run_prediction
from app.pump.models import Pump
from app.work_order.models import WorkOrder, WorkOrderSource, WorkOrderStatus
from app.work_order.schemas import WorkOrderCreate, WorkOrderUpdate
from app.core.permissions import Permission, has_permission
from app.user.models import User


def create_work_order(
    db: Session,
    tenant_id: uuid.UUID,
    payload: WorkOrderCreate,
    created_by_user_id: uuid.UUID | None = None,
) -> WorkOrder:
    work_order = WorkOrder(
        tenant_id=tenant_id, created_by_user_id=created_by_user_id, **payload.model_dump()
    )
    db.add(work_order)
    db.flush()
    record_event(db, tenant_id, created_by_user_id, "work_order", work_order.id, "created")
    db.commit()
    db.refresh(work_order)
    return work_order


def get_work_order(
    db: Session, tenant_id: uuid.UUID, work_order_id: uuid.UUID
) -> WorkOrder | None:
    return db.scalar(
        select(WorkOrder).where(
            WorkOrder.id == work_order_id, WorkOrder.tenant_id == tenant_id
        )
    )


def list_work_orders(
    db: Session,
    tenant_id: uuid.UUID,
    status_filter: WorkOrderStatus | None = None,
    pump_id: uuid.UUID | None = None,
) -> list[WorkOrder]:
    stmt = select(WorkOrder).where(WorkOrder.tenant_id == tenant_id)
    if status_filter is not None:
        stmt = stmt.where(WorkOrder.status == status_filter)
    if pump_id is not None:
        stmt = stmt.where(WorkOrder.pump_id == pump_id)
    return list(db.scalars(stmt.order_by(WorkOrder.created_at.desc())))


def update_work_order(
    db: Session,
    tenant_id: uuid.UUID,
    work_order_id: uuid.UUID,
    payload: WorkOrderUpdate,
    actor_user_id: uuid.UUID | None = None,
) -> WorkOrder | None:
    work_order = db.scalar(select(WorkOrder).where(
        WorkOrder.id == work_order_id, WorkOrder.tenant_id == tenant_id).with_for_update())
    if work_order is None:
        return None
    changes = payload.model_dump(exclude_unset=True)
    if work_order.status in {WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED}:
        raise HTTPException(409, "Use the outcome correction workflow for completed work")
    if changes.get("status") == WorkOrderStatus.COMPLETED:
        raise HTTPException(422, "Use the structured outcome form to complete this work order")
    if "status" in changes and changes["status"] is None:
        raise HTTPException(422, "Status cannot be empty")
    owner_id = changes.get("assigned_to_user_id")
    if owner_id:
        owner = db.scalar(select(User).where(User.id == owner_id,
            User.tenant_id == tenant_id, User.is_active.is_(True)))
        if owner is None or not has_permission(owner.role.value, Permission.MANAGE_WORK_ORDERS):
            raise HTTPException(422, "Choose an active maintenance user in this organisation")
    previous = {key: getattr(work_order, key) for key in changes}
    for field, value in changes.items():
        setattr(work_order, field, value)
    if "status" in changes:
        if changes["status"] in {WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED}:
            work_order.closed_at = work_order.closed_at or datetime.now(UTC)
        elif changes["status"] in {WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS}:
            work_order.closed_at = None
    record_event(
        db,
        tenant_id,
        actor_user_id,
        "work_order",
        work_order.id,
        "updated",
        previous_value={key: str(value) for key, value in previous.items()},
        new_value={key: str(value) for key, value in changes.items()},
    )
    db.commit()
    db.refresh(work_order)
    return work_order


def create_work_order_from_prediction(
    db: Session, tenant_id: uuid.UUID, pump_id: uuid.UUID
) -> WorkOrder | None:
    """Auto-generate a maintenance work order if latest 7-day failure risk score >= 0.70."""
    pump = db.scalar(select(Pump).where(Pump.id == pump_id, Pump.tenant_id == tenant_id))
    if pump is None:
        raise ValueError(f"Pump {pump_id} not found for tenant {tenant_id}")

    prediction = get_latest_prediction(db, tenant_id, pump_id)
    if prediction is None:
        prediction = run_prediction(db, tenant_id, pump_id)

    risk_score = float(prediction.risk_score_7d) if prediction.risk_score_7d is not None else 0.0
    if risk_score < 0.70 and prediction.predicted_class == "normal":
        return None

    priority = "high" if risk_score >= 0.85 else "normal"
    fault_label = prediction.predicted_class or "mechanical_anomaly"
    formatted_label = fault_label.replace("_", " ").title()
    title = f"Condition-Based Maintenance: {formatted_label} (Risk: {risk_score * 100:.1f}%)"
    description = (
        f"Automated work order raised from prediction scoring. "
        f"7-day failure risk score: {risk_score:.2f}, fault class: {fault_label}."
    )

    source_alert = db.scalar(
        select(Alert)
        .where(
            Alert.tenant_id == tenant_id,
            Alert.pump_id == pump.id,
            Alert.status != AlertStatus.RESOLVED,
        )
        .order_by(Alert.triggered_at.desc())
    )
    wo_create = WorkOrderCreate(
        pump_id=pump.id,
        station_id=pump.station_id,
        title=title,
        description=description,
        source=WorkOrderSource.ALERT,
        source_prediction_id=prediction.id,
        source_alert_id=source_alert.id if source_alert else None,
        priority=priority,
    )
    return create_work_order(db, tenant_id, wo_create)
