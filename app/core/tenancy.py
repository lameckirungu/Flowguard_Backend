"""Tenant-resolution dependency.

This is the single choke point between "authenticated request" and "service
call" — every route that touches tenant-scoped data depends on
`get_current_tenant_id` (directly or via `get_current_tenant_context`)
instead of trusting a tenant_id from a query param or request body. Services
require `tenant_id` as an explicit argument (see any module's services.py),
so a route physically cannot query across tenants without deliberately
bypassing this dependency.
"""
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status

from app.core.auth import CurrentUser, get_current_user


def get_current_tenant_id(
    current_user: CurrentUser = Depends(get_current_user),
) -> uuid.UUID:
    """The tenant_id to filter every query by. Import this in routes.py,
    not `get_current_user` directly, when a route only cares about tenant
    scope and not the rest of the identity.

    The platform admin has no tenant, so any route depending on this is
    off-limits to them — they act only through the platform-scoped tenant
    management routes (see app/tenant/routes.py).
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is tenant-scoped and not available to the platform admin",
        )
    return current_user.tenant_id


@dataclass(frozen=True)
class TenantContext:
    """Bundles tenant_id with the acting user — pass this into services
    that need to know both who is making the call and which tenant it's
    scoped to (e.g. for audit fields).
    """

    tenant_id: uuid.UUID
    user: CurrentUser


def get_current_tenant_context(
    current_user: CurrentUser = Depends(get_current_user),
) -> TenantContext:
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is tenant-scoped and not available to the platform admin",
        )
    return TenantContext(tenant_id=current_user.tenant_id, user=current_user)
