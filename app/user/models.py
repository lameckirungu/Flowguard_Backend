"""Users: the platform admin plus per-tenant planners, technicians, admins.

Almost every user belongs to exactly one tenant. The one exception is the
`platform_admin` role, whose `tenant_id` is NULL — that account onboards and
manages tenants and is off-limits to every tenant-scoped route (enforced in
app/core/tenancy.py). Because of that exception this model declares its own
nullable `tenant_id` instead of inheriting TenantScopedMixin.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(enum.StrEnum):
    # Cross-tenant. Onboards/manages tenants; has no tenant_id.
    PLATFORM_ADMIN = "platform_admin"
    # Per-tenant. Onboards/manages users within its own tenant.
    ADMIN = "admin"
    PLANNER = "planner"
    TECHNICIAN = "technician"
    VIEWER = "viewer"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user"
    __table_args__ = (UniqueConstraint("email", name="uq_user_email"),)

    # NULL only for the platform admin. Every other user is tenant-scoped and
    # services still filter by tenant_id exactly as the TenantScopedMixin
    # tables do.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.VIEWER
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # True while an onboarded account still holds its emailed first-time
    # password. Login then issues only a reset token (see app/user/routes.py).
    must_reset_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r}>"
