"""add phase 1 audit events"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8e1a6d4f210"
down_revision: str | None = "a932c1b32c07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("previous_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_event_tenant_id", "audit_event", ["tenant_id"])
    op.create_index("ix_audit_event_actor_user_id", "audit_event", ["actor_user_id"])
    op.create_index("ix_audit_event_entity_type", "audit_event", ["entity_type"])
    op.create_index("ix_audit_event_entity_id", "audit_event", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_event_entity_id", table_name="audit_event")
    op.drop_index("ix_audit_event_entity_type", table_name="audit_event")
    op.drop_index("ix_audit_event_actor_user_id", table_name="audit_event")
    op.drop_index("ix_audit_event_tenant_id", table_name="audit_event")
    op.drop_table("audit_event")
