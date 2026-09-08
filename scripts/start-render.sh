#!/bin/sh
set -eu

alembic upgrade head

if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  python scripts/seed_platform_admin.py
  python scripts/seed_kpc_tenant.py
  python scripts/seed_uat_users.py
  python scripts/seed_uat_data.py
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
