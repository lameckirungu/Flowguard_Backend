"""Tenant management routes.

Cross-tenant by nature (creating/listing tenants), so these are gated on the
PLATFORM_ADMIN role rather than by app.core.tenancy.get_current_tenant_id —
see the note in app/tenant/services.py. Routes only translate HTTP <->
services; no business logic lives here.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.db import get_db
from app.core.email import EmailNotConfiguredError
from app.tenant import services
from app.tenant.schemas import TenantCreate, TenantOnboardRead, TenantRead, TenantUpdate

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])

require_platform_admin = require_role("platform_admin")


@router.post("", response_model=TenantOnboardRead, status_code=status.HTTP_201_CREATED)
def onboard_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db),
    _=Depends(require_platform_admin),
) -> TenantOnboardRead:
    try:
        tenant, admin = services.onboard_tenant(db, payload)
    except EmailNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tenant created but the admin invite email could not be sent: "
            "SMTP is not configured",
        ) from exc
    return TenantOnboardRead(
        **TenantRead.model_validate(tenant).model_dump(),
        admin_user_id=admin.id,
        admin_email=admin.email,
    )


@router.get("", response_model=list[TenantRead])
def list_tenants(
    db: Session = Depends(get_db),
    _=Depends(require_platform_admin),
) -> list[TenantRead]:
    return services.list_tenants(db)


@router.get("/{tenant_id}", response_model=TenantRead)
def get_tenant(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(require_platform_admin),
) -> TenantRead:
    tenant = services.get_tenant(db, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


@router.patch("/{tenant_id}", response_model=TenantRead)
def update_tenant(
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_platform_admin),
) -> TenantRead:
    tenant = services.update_tenant(db, tenant_id, payload)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant
