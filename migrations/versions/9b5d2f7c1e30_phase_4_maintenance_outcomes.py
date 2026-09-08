from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision = "9b5d2f7c1e30"
down_revision = "8a4d1c9f2b11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade():
    for name, column in [("outcome", sa.String(40)), ("post_maintenance_condition", sa.String(40)), ("completed_by_user_id", sa.Uuid()), ("verified_at", sa.DateTime(timezone=True)), ("verified_by_user_id", sa.Uuid()), ("follow_up_due_at", sa.DateTime(timezone=True)), ("parent_work_order_id", sa.Uuid())]:
        op.add_column("work_order", sa.Column(name, column, nullable=True))
    op.create_foreign_key("fk_work_order_completed_by_user", "work_order", "user", ["completed_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_work_order_verified_by_user", "work_order", "user", ["verified_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_work_order_parent", "work_order", "work_order", ["parent_work_order_id"], ["id"], ondelete="SET NULL")

def downgrade():
    op.drop_constraint("fk_work_order_parent", "work_order", type_="foreignkey")
    op.drop_constraint("fk_work_order_verified_by_user", "work_order", type_="foreignkey")
    op.drop_constraint("fk_work_order_completed_by_user", "work_order", type_="foreignkey")
    for name in ["parent_work_order_id", "follow_up_due_at", "verified_by_user_id", "verified_at", "completed_by_user_id", "post_maintenance_condition", "outcome"]:
        op.drop_column("work_order", name)
