"""platform admin role, nullable user.tenant_id, first-login password reset

Revision ID: a1b2c3d4e5f6
Revises: fba5048a7fb1
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "fba5048a7fb1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. New enum member for the cross-tenant platform admin.
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'PLATFORM_ADMIN'")

    # 2. The platform admin has no tenant.
    op.alter_column("user", "tenant_id", existing_type=sa.Uuid(), nullable=True)

    # 3. First-login forced password reset flag.
    op.add_column(
        "user",
        sa.Column(
            "must_reset_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("user", "must_reset_password", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_column("user", "must_reset_password")

    # Any platform-admin rows must go before tenant_id can be NOT NULL again.
    op.execute("DELETE FROM \"user\" WHERE role = 'PLATFORM_ADMIN'")
    op.alter_column("user", "tenant_id", existing_type=sa.Uuid(), nullable=False)

    if bind.dialect.name == "postgresql":
        # Postgres can't drop a single enum value; rebuild the type without it.
        op.execute("ALTER TYPE user_role RENAME TO user_role_old")
        op.execute(
            "CREATE TYPE user_role AS ENUM ('ADMIN', 'PLANNER', 'TECHNICIAN', 'VIEWER')"
        )
        op.execute(
            'ALTER TABLE "user" ALTER COLUMN role TYPE user_role '
            "USING role::text::user_role"
        )
        op.execute("DROP TYPE user_role_old")
