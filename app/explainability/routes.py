"""Explainability routes. Thin: translate HTTP <-> services, no business logic."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.core.db import get_db
from app.core.permissions import Permission
from app.core.tenancy import get_current_tenant_id
from app.explainability import services
from app.explainability.schemas import FeatureAttributionRead

router = APIRouter(prefix="/api/v1/explainability", tags=["explainability"])


@router.get("", response_model=list[FeatureAttributionRead])
def list_feature_attributions(
    pump_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> list[FeatureAttributionRead]:
    return services.list_feature_attributions(db, tenant_id, pump_id=pump_id)


@router.get("/pumps/{pump_id}/latest", response_model=FeatureAttributionRead)
def get_latest_feature_attribution(
    pump_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> FeatureAttributionRead:
    result = services.get_latest_feature_attribution(db, tenant_id, pump_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No feature attribution found"
        )
    return result


@router.post(
    "/pumps/{pump_id}/trigger",
    response_model=FeatureAttributionRead,
    status_code=status.HTTP_201_CREATED,
)
def trigger_feature_attribution(
    pump_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.RUN_MODELS)),
) -> FeatureAttributionRead:
    try:
        return services.compute_feature_attribution(db, tenant_id, pump_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
