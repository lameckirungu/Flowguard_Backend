"""Tenant configuration: fluid type, alert thresholds, branding.

The `tenant` table is the one deliberate exception to TenantScopedMixin —
it doesn't have a tenant_id because it *is* the tenant that every other
scoped table's tenant_id points at.
"""
from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenant"
    __table_args__ = {'schema': 'master'}

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)

    # Case-study driven config: what fluid this tenant's network transports,
    # and the default thresholds used to derive the Health Deviation Index /
    # alerts before per-pump overrides apply (see app/flowgard_engine, app/alert).
    fluid_type: Mapped[str] = mapped_column(String(50), nullable=False, default="crude_oil")
    pressure_threshold_kpa: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    vibration_threshold_mm_s: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )

    branding_display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    branding_primary_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    branding_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tenant id={self.id} slug={self.slug!r}>"