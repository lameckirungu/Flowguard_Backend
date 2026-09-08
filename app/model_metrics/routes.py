"""Model metrics routes. Thin: translate HTTP <-> services."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.core.db import get_db
from app.core.permissions import Permission
from app.core.tenancy import get_current_tenant_id
from app.model_metrics import services
from app.model_metrics.schemas import ModelMetricCreate, ModelMetricRead

router = APIRouter(prefix="/api/v1/model-metrics", tags=["model_metrics"])


@router.post("", response_model=ModelMetricRead, status_code=status.HTTP_201_CREATED)
def record_metric(
    payload: ModelMetricCreate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.MANAGE_MODELS)),
) -> ModelMetricRead:
    return services.record_metric(db, tenant_id, payload)


@router.get("", response_model=list[ModelMetricRead])
def list_metrics(
    model_name: str | None = None,
    model_version: str | None = None,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> list[ModelMetricRead]:
    return services.list_metrics(db, tenant_id, model_name=model_name, model_version=model_version)
