# Flowgard Backend

FastAPI backend for the Flowgard multi-tenant predictive-maintenance UAT application. It provides tenant-scoped APIs for liquid-transport stations, pumps, telemetry, predictions, RUL, explainability, alerts, work orders, schedules, reporting, model governance, and authentication.

## Stack

- Python 3.11+ (Python 3.13 supported)
- FastAPI, Pydantic v2, SQLAlchemy 2, Alembic
- PostgreSQL (SQLite is used by selected tests)
- JWT access/refresh sessions with HTTP-only cookies handled by the frontend BFF

## Local start

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

The Compose stack exposes the API at http://localhost:8000. The Next.js frontend is in the sibling `flowgard-web` repository and runs at http://localhost:3000.

Useful checks:

```bash
curl http://localhost:8000/ready
open http://localhost:8000/docs
./scripts/check.sh
```

## Demo/UAT seed

For a repeatable UAT environment:

```bash
alembic upgrade head
SEED_DEMO_DATA=true sh scripts/start-render.sh
```

In Render, set `SEED_DEMO_DATA=true`; the checked-in startup script performs the migration and seed sequence before starting Uvicorn:

1. Platform administrator
2. KPC demonstration tenant and 13 stations/26 pumps
3. Admin, planner, technician, and viewer accounts
4. Synthetic predictions, HDI, RUL, explainability, alerts, work orders, schedules, and model metrics

The seeder is idempotent. UAT records are synthetic and must not be used for operational decisions.

## UAT credentials

| Role | Email | Password |
| --- | --- | --- |
| Tenant admin | admin@flowgard.com | Flowgard-UAT-2026! |
| Planner | planner@flowgard.com | Flowgard-UAT-2026! |
| Technician | technician@flowgard.com | Flowgard-UAT-2026! |
| Viewer | viewer@flowgard.com | Flowgard-UAT-2026! |

The platform administrator is `platform.admin@flow.com` with the configured `PLATFORM_ADMIN_PASSWORD`; it is intended for platform API onboarding, not tenant dashboard access.

## Render deployment

Deploy the `feat/phases-8-10-uat-readiness` branch as a Docker Web Service. Set the Docker command to:

```text
sh scripts/start-render.sh
```

Set `DATABASE_URL` from the Render PostgreSQL service, `SEED_DEMO_DATA=true`, a strong `JWT_SECRET_KEY`, and:

```text
CORS_ALLOW_ORIGINS=https://flowgard-frontend.onrender.com
```

The service must listen on Render's `$PORT`; the startup script handles this. Verify `/ready` and `/docs` after deployment.

## API surface

The canonical, generated endpoint reference is available at `/docs` and `/openapi.json`. Major prefixes are `/api/v1/auth`, `/api/v1/users`, `/api/v1/tenants`, `/api/v1/stations`, `/api/v1/pumps`, `/api/v1/operations`, `/api/v1/alerts`, `/api/v1/work-orders`, `/api/v1/maintenance-schedule`, `/api/v1/model-metrics`, and `/api/v1/reporting`.

## Documentation

- `RUNBOOK.md`: operations, local setup, Render deployment, and recovery
- `UAT_RUNBOOK.md`: grading/UAT acceptance checklist
- `app/etl/README.md`: ingestion pipeline notes
