from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision = "8a4d1c9f2b11"
down_revision = "7f2c1a9e4b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade():
    for name, column in [("feature_version", sa.String(50)), ("input_watermark", sa.DateTime(timezone=True)), ("data_quality", sa.String(30)), ("confidence", sa.Numeric(5, 4)), ("rul_hours", sa.Numeric(10, 2)), ("rul_low_hours", sa.Numeric(10, 2)), ("rul_high_hours", sa.Numeric(10, 2))]:
        op.add_column("prediction_result", sa.Column(name, column, nullable=(name != "data_quality"), server_default=("insufficient_evidence" if name == "data_quality" else None)))

def downgrade():
    for name in ["rul_high_hours", "rul_low_hours", "rul_hours", "confidence", "data_quality", "input_watermark", "feature_version"]:
        op.drop_column("prediction_result", name)
