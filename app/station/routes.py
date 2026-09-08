"""Station routes. Thin: translate HTTP <-> services, no business logic."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.core.db import get_db
from app.core.permissions import Permission
from app.core.tenancy import get_current_tenant_id
from app.station import services
from app.station.schemas import StationCreate, StationRead, StationUpdate

router = APIRouter(prefix="/api/v1/stations", tags=["stations"])


@router.post("", response_model=StationRead, status_code=status.HTTP_201_CREATED)
def create_station(
    payload: StationCreate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.MANAGE_ASSETS)),
) -> StationRead:
    return services.create_station(db, tenant_id, payload)


@router.get("", response_model=list[StationRead])
def list_stations(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> list[StationRead]:
    return services.list_stations(db, tenant_id)


@router.get("/{station_id}", response_model=StationRead)
def get_station(
    station_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> StationRead:
    station = services.get_station(db, tenant_id, station_id)
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
    return station


@router.patch("/{station_id}", response_model=StationRead)
def update_station(
    station_id: uuid.UUID,
    payload: StationUpdate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.MANAGE_ASSETS)),
) -> StationRead:
    station = services.update_station(db, tenant_id, station_id, payload)
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
    return station
