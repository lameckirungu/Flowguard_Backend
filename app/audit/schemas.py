import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    id: uuid.UUID
    entity_type: str
    entity_reference: str
    action: str
    actor_email: str | None = None
    previous_value: dict | None = None
    new_value: dict | None = None
    created_at: datetime
