"""Compatibility revision for databases created before the medallion graph.

The upstream migration was replaced by 344690fada1b. Keeping this no-op
revision allows databases stamped with the legacy revision to upgrade safely.
"""

revision = "fba5048a7fb1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
