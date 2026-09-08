"""Repair verification result and report cohort index."""
import sqlalchemy as sa
from alembic import op

revision = "a107c6206701"
down_revision = "a107c6206700"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("work_order", sa.Column("verification_result", sa.String(20)))
    op.add_column("work_order", sa.Column("verification_note", sa.Text()))
    op.create_index("ix_work_order_tenant_completion", "work_order", ["tenant_id", "status", "closed_at"])


def downgrade():
    op.drop_index("ix_work_order_tenant_completion", table_name="work_order")
    op.drop_column("work_order", "verification_note")
    op.drop_column("work_order", "verification_result")
