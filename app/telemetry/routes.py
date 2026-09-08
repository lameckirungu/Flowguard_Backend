import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.core.db import get_db
from app.core.permissions import Permission
from app.core.tenancy import get_current_tenant_id
from app.telemetry import services
from app.telemetry.models import Connector, ConnectorStatus
from app.telemetry.schemas import (
    ConnectorCreate,
    ConnectorRead,
    IngestionSummary,
    TelemetryEnvelope,
    TelemetryIngestResponse,
)

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])


@router.get("/connectors", response_model=list[ConnectorRead])
def list_connectors(
    db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(get_current_tenant_id)
):
    return services.list_connectors(db, tenant_id)


@router.post("/connectors", response_model=ConnectorRead, status_code=status.HTTP_201_CREATED)
def create_connector(
    payload: ConnectorCreate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.MANAGE_TENANT)),
):
    return services.create_connector(
        db, tenant_id, payload.name, payload.connector_type, payload.configuration
    )


@router.post("/connectors/{connector_id}/enable", response_model=ConnectorRead)
def enable_connector(
    connector_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.MANAGE_TENANT)),
):
    connector = (
        db.query(Connector)
        .filter(Connector.id == connector_id, Connector.tenant_id == tenant_id)
        .first()
    )
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    connector.status = ConnectorStatus.HEALTHY
    db.commit()
    db.refresh(connector)
    return connector


@router.post("/{connector_id}/ingest", response_model=TelemetryIngestResponse)
def ingest(
    connector_id: uuid.UUID,
    payload: list[TelemetryEnvelope],
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.MANAGE_TENANT)),
):
    try:
        return services.ingest(db, tenant_id, connector_id, payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("/summary", response_model=list[IngestionSummary])
def get_summary(
    db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(get_current_tenant_id)
):
    return services.summary(db, tenant_id)
