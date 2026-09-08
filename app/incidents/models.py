import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TenantScopedMixin, UUIDPrimaryKeyMixin


class IncidentPolicy(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    __tablename__ = "incident_policy"
    __table_args__ = (UniqueConstraint("tenant_id", "revision"),)

    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    deadlines: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
