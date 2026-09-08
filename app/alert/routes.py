"""Alert routes. Thin: translate HTTP <-> services, no business logic."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.alert import services
from app.alert.models import AlertStatus
from app.alert.schemas import AlertCreate, AlertRead, AlertUpdate
from app.core.db import get_db
from app.core.tenancy import get_current_tenant_id

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.post("", response_model=AlertRead, status_code=status.HTTP_201_CREATED)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> AlertRead:
    return services.create_alert(db, tenant_id, payload)


@router.get("", response_model=list[AlertRead])
def list_alerts(
    status_filter: AlertStatus | None = None,
    pump_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> list[AlertRead]:
    return services.list_alerts(db, tenant_id, status_filter=status_filter, pump_id=pump_id)


@router.get("/{alert_id}", response_model=AlertRead)
def get_alert(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> AlertRead:
    alert = services.get_alert(db, tenant_id, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.patch("/{alert_id}", response_model=AlertRead)
def update_alert(
    alert_id: uuid.UUID,
    payload: AlertUpdate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> AlertRead:
    alert = services.update_alert(db, tenant_id, alert_id, payload)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.post("/pumps/{pump_id}/evaluate", response_model=list[AlertRead])
def evaluate_alert_thresholds(
    pump_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> list[AlertRead]:
    try:
        return services.evaluate_thresholds(db, tenant_id, pump_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
