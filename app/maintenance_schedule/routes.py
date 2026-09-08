"""Maintenance schedule routes. Thin: translate HTTP <-> services."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.tenancy import get_current_tenant_id
from app.maintenance_schedule import services
from app.maintenance_schedule.models import ScheduleStatus
from app.maintenance_schedule.schemas import (
    ScheduledMaintenanceCreate,
    ScheduledMaintenanceRead,
    ScheduledMaintenanceUpdate,
)

router = APIRouter(prefix="/api/v1/maintenance-schedule", tags=["maintenance_schedule"])


@router.post("", response_model=ScheduledMaintenanceRead, status_code=status.HTTP_201_CREATED)
def create_scheduled_maintenance(
    payload: ScheduledMaintenanceCreate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> ScheduledMaintenanceRead:
    return services.create_scheduled_maintenance(db, tenant_id, payload)


@router.get("", response_model=list[ScheduledMaintenanceRead])
def list_scheduled_maintenance(
    status_filter: ScheduleStatus | None = None,
    pump_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> list[ScheduledMaintenanceRead]:
    return services.list_scheduled_maintenance(
        db, tenant_id, status_filter=status_filter, pump_id=pump_id
    )


@router.get("/{entry_id}", response_model=ScheduledMaintenanceRead)
def get_scheduled_maintenance(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> ScheduledMaintenanceRead:
    entry = services.get_scheduled_maintenance(db, tenant_id, entry_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule entry not found"
        )
    return entry


@router.patch("/{entry_id}", response_model=ScheduledMaintenanceRead)
def update_scheduled_maintenance(
    entry_id: uuid.UUID,
    payload: ScheduledMaintenanceUpdate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> ScheduledMaintenanceRead:
    entry = services.update_scheduled_maintenance(db, tenant_id, entry_id, payload)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule entry not found"
        )
    return entry


@router.post("/rank", response_model=list[ScheduledMaintenanceRead])
def rank_schedule_by_rul(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> list[ScheduledMaintenanceRead]:
    return services.rank_schedule_by_rul(db, tenant_id)
