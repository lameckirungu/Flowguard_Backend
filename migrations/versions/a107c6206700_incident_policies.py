"""Incident ownership and revisioned response policies."""
import sqlalchemy as sa
from alembic import op

revision = "a107c6206700"
down_revision = "9b5d2f7c1e30"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("alert", sa.Column("assigned_to_user_id", sa.Uuid(), nullable=True))
    op.add_column("alert", sa.Column("resolution_note", sa.Text(), nullable=True))
    op.create_foreign_key("fk_alert_owner", "alert", "user", ["assigned_to_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_alert_assigned_to_user_id", "alert", ["assigned_to_user_id"])
    op.create_index("ix_alert_tenant_status_time", "alert", ["tenant_id", "status", "triggered_at"])
    op.create_table("incident_policy",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("deadlines", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL")),
        sa.UniqueConstraint("tenant_id", "revision"))
    op.create_index("ix_incident_policy_tenant_id", "incident_policy", ["tenant_id"])


def downgrade():
    op.drop_table("incident_policy")
    op.drop_index("ix_alert_tenant_status_time", table_name="alert")
    op.drop_index("ix_alert_assigned_to_user_id", table_name="alert")
    op.drop_constraint("fk_alert_owner", "alert", type_="foreignkey")
    op.drop_column("alert", "resolution_note")
    op.drop_column("alert", "assigned_to_user_id")
