import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.audit.schemas import AuditEventRead
from app.core.auth import require_permission
from app.core.db import get_db
from app.core.permissions import Permission
from app.core.tenancy import get_current_tenant_id
from app.user.models import User

router = APIRouter(prefix="/api/v1/audit-events", tags=["audit"])

@router.get("", response_model=list[AuditEventRead])
def list_audit_events(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.MANAGE_USERS)),
) -> list[AuditEventRead]:
    rows = db.execute(
        select(AuditEvent, User.email)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(100)
    )
    return [AuditEventRead(
        id=event.id,
        entity_type=event.entity_type,
        entity_reference=(
            f"{event.entity_type.replace('_', ' ').title()} "
            f"{str(event.entity_id)[:8].upper()}"
        ),
        action=event.action,
        actor_email=email,
        previous_value=event.previous_value,
        new_value=event.new_value,
        created_at=event.created_at,
    ) for event, email in rows]
