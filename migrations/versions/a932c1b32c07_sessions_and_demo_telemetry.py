"""refresh sessions and source-unit demo telemetry

Revision ID: a932c1b32c07
Revises: fba5048a7fb1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a932c1b32c07"
down_revision: str | None = "fba5048a7fb1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sensor_reading", sa.Column("vibration_g", sa.Numeric(10, 4), nullable=True))
    op.create_table(
        "refresh_session",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["replaced_by_id"], ["refresh_session.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refresh_session_tenant_id", "refresh_session", ["tenant_id"])
    op.create_index("ix_refresh_session_user_id", "refresh_session", ["user_id"])
    op.create_index("ix_refresh_session_token_hash", "refresh_session", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_refresh_session_token_hash", table_name="refresh_session")
    op.drop_index("ix_refresh_session_user_id", table_name="refresh_session")
    op.drop_index("ix_refresh_session_tenant_id", table_name="refresh_session")
    op.drop_table("refresh_session")
    op.drop_column("sensor_reading", "vibration_g")
