import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.audit.models import AuditEvent


def record_event(
    db: Session,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    previous_value: dict | None = None,
    new_value: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        previous_value=previous_value,
        new_value=new_value,
        created_at=datetime.now(UTC),
    )
    db.add(event)
    return event
