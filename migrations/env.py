"""Alembic environment.

Imports the same `settings` and `Base` the app uses (app/core/config.py,
app/core/base.py) — never a second hardcoded connection string, and
autogenerate diffs against the exact same metadata the app runs on.
"""
from logging.config import fileConfig

from alembic import context

# FIX 1: Added `text` to the sqlalchemy imports
from sqlalchemy import engine_from_config, pool, text

# Import every module's models so they register on Base.metadata before
# autogenerate runs. Add a line here whenever a new module gets models.py.
import app.alert.models  # noqa: F401,E402
import app.etl.bronze.models  # noqa: F401,E402
import app.etl.gold.models  # noqa: F401,E402
import app.etl.silver.models  # noqa: F401,E402
import app.explainability.models  # noqa: F401,E402
import app.flowgard_engine.models  # noqa: F401,E402
import app.maintenance_schedule.models  # noqa: F401,E402
import app.model_metrics.models  # noqa: F401,E402
import app.prediction.models  # noqa: F401,E402
import app.pump.models  # noqa: F401,E402
import app.rul.models  # noqa: F401,E402
import app.station.models  # noqa: F401,E402
import app.tenant.models  # noqa: F401,E402
import app.user.models  # noqa: F401,E402
import app.work_order.models  # noqa: F401,E402
from app.core.base import Base
from app.core.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# FIX: Escaping the '%' sign in the database password so Alembic doesn't crash
safe_db_url = str(settings.database_url).replace("%", "%%")
config.set_main_option("sqlalchemy.url", safe_db_url)


def include_name(name, type_, parent_names):
    if type_ == "schema":
        # Only track migrations for these specific Medallion schemas
        return name in ["master", "bronze", "silver", "gold"]
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=safe_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table_schema="master",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # FIX 2: Create schemas dynamically so the CI pipeline doesn't crash
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS master;"))
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS bronze;"))
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS silver;"))
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS gold;"))
        connection.commit()

        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            version_table_schema="master"
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()