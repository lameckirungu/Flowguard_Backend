from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision = "7f2c1a9e4b10"
down_revision = "d4b7e9a1c203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade():
    op.create_table("connector", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("tenant_id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("connector_type", sa.String(40), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("configuration", sa.JSON(), nullable=False), sa.Column("last_success_at", sa.DateTime(timezone=True)), sa.Column("last_failure_at", sa.DateTime(timezone=True)), sa.Column("last_error", sa.String(500)), sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"), sa.UniqueConstraint("tenant_id", "name"))
    op.create_table("telemetry_record", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("tenant_id", sa.Uuid(), nullable=False), sa.Column("connector_id", sa.Uuid(), nullable=False), sa.Column("asset_key", sa.String(120), nullable=False), sa.Column("measurement", sa.String(80), nullable=False), sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False), sa.Column("value", sa.Float()), sa.Column("unit", sa.String(30), nullable=False), sa.Column("source_event_id", sa.String(250), nullable=False), sa.Column("source_payload", sa.JSON(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("reason_code", sa.String(80)), sa.Column("reason_detail", sa.String(500)), sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["connector_id"], ["connector.id"], ondelete="CASCADE"), sa.UniqueConstraint("tenant_id", "connector_id", "source_event_id"))
    op.create_table("ingestion_checkpoint", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("tenant_id", sa.Uuid(), nullable=False), sa.Column("connector_id", sa.Uuid(), nullable=False, unique=True), sa.Column("last_source_event_id", sa.String(250)), sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("last_processed_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["connector_id"], ["connector.id"], ondelete="CASCADE"))

def downgrade():
    op.drop_table("ingestion_checkpoint")
    op.drop_table("telemetry_record")
    op.drop_table("connector")
