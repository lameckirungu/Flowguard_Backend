"""Work order routes. Thin: translate HTTP <-> services, no business logic."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, require_permission
from app.core.db import get_db
from app.core.permissions import Permission
from app.core.tenancy import get_current_tenant_id
from app.work_order import services
from app.work_order import outcomes
from app.work_order.models import WorkOrderStatus
from app.work_order.schemas import WorkOrderCreate, WorkOrderOutcome, WorkOrderRead, WorkOrderUpdate, VerificationWrite

router = APIRouter(prefix="/api/v1/work-orders", tags=["work_orders"])



@router.post("", response_model=WorkOrderRead, status_code=status.HTTP_201_CREATED)
def create_work_order(
    payload: WorkOrderCreate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_WORK_ORDERS)),
) -> WorkOrderRead:
    return services.create_work_order(db, tenant_id, payload, created_by_user_id=current_user.id)


@router.get("", response_model=list[WorkOrderRead])
def list_work_orders(
    status_filter: WorkOrderStatus | None = None,
    pump_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> list[WorkOrderRead]:
    return services.list_work_orders(db, tenant_id, status_filter=status_filter, pump_id=pump_id)


@router.get("/{work_order_id}", response_model=WorkOrderRead)
def get_work_order(
    work_order_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> WorkOrderRead:
    work_order = services.get_work_order(db, tenant_id, work_order_id)
    if work_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    return work_order


@router.patch("/{work_order_id}", response_model=WorkOrderRead)
def update_work_order(
    work_order_id: uuid.UUID,
    payload: WorkOrderUpdate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_WORK_ORDERS)),
) -> WorkOrderRead:
    work_order = services.update_work_order(
        db, tenant_id, work_order_id, payload, actor_user_id=current_user.id
    )
    if work_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    return work_order


@router.post("/{work_order_id}/outcome", response_model=WorkOrderRead)
def record_outcome(work_order_id: uuid.UUID, payload: WorkOrderOutcome, db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(get_current_tenant_id), current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_WORK_ORDERS))) -> WorkOrderRead:
    return outcomes.record_outcome(db, current_user, work_order_id, payload)


@router.post("/{work_order_id}/verification", response_model=WorkOrderRead)
def verify(work_order_id: uuid.UUID, payload: VerificationWrite, db=Depends(get_db),
           current=Depends(require_permission(Permission.MANAGE_WORK_ORDERS))):
    return outcomes.verify(db, current, work_order_id, payload)


@router.post("/{work_order_id}/follow-up", response_model=WorkOrderRead)
def follow_up(work_order_id: uuid.UUID, db=Depends(get_db),
              current=Depends(require_permission(Permission.MANAGE_WORK_ORDERS))):
    return outcomes.follow_up(db, current, work_order_id)


@router.get("/{work_order_id}/history")
def history(work_order_id: uuid.UUID, db=Depends(get_db),
            current=Depends(require_permission(Permission.VIEW_OPERATIONS))):
    return outcomes.history(db, current.tenant_id, work_order_id)

@router.post(
    "/auto-generate/pumps/{pump_id}",
    response_model=WorkOrderRead | None,
    status_code=status.HTTP_201_CREATED,
)
def auto_generate_work_order(
    pump_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.MANAGE_WORK_ORDERS)),
) -> WorkOrderRead | None:
    try:
        wo = services.create_work_order_from_prediction(db, tenant_id, pump_id)
        if wo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Risk score threshold not met for auto work order generation",
            )
        return wo
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
