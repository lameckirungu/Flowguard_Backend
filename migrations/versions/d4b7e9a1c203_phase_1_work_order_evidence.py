"""add work-order evidence and source links"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision: str = "d4b7e9a1c203"
down_revision: str | None = "c8e1a6d4f210"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column("work_order", sa.Column("source_alert_id", sa.Uuid(), nullable=True))
    op.add_column("work_order", sa.Column("source_prediction_id", sa.Uuid(), nullable=True))
    op.add_column("work_order", sa.Column("completion_note", sa.Text(), nullable=True))
    op.add_column("work_order", sa.Column("root_cause", sa.String(length=250), nullable=True))
    op.add_column("work_order", sa.Column("corrective_action", sa.Text(), nullable=True))
    op.add_column("work_order", sa.Column("downtime_minutes", sa.Integer(), nullable=True))
    op.add_column("work_order", sa.Column("follow_up_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_foreign_key("fk_work_order_source_alert", "work_order", "alert", ["source_alert_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_work_order_source_prediction", "work_order", "prediction_result", ["source_prediction_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_work_order_source_alert_id", "work_order", ["source_alert_id"])
    op.create_index("ix_work_order_source_prediction_id", "work_order", ["source_prediction_id"])

def downgrade() -> None:
    op.drop_index("ix_work_order_source_prediction_id", table_name="work_order")
    op.drop_index("ix_work_order_source_alert_id", table_name="work_order")
    op.drop_constraint("fk_work_order_source_prediction", "work_order", type_="foreignkey")
    op.drop_constraint("fk_work_order_source_alert", "work_order", type_="foreignkey")
    for col in ["follow_up_required", "downtime_minutes", "corrective_action", "root_cause", "completion_note", "source_prediction_id", "source_alert_id"]:
        op.drop_column("work_order", col)
