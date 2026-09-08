# Flowgard Operations and Deployment Runbook

## Scope

Use this runbook for the current Next.js + FastAPI + PostgreSQL UAT deployment. The application is a synthetic-data demonstration, not a production telemetry platform.

## Local operation

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 api
```

Backend: http://localhost:8000
API docs: http://localhost:8000/docs
Readiness: http://localhost:8000/ready
Frontend: http://localhost:3000

Start the frontend in the sibling repository with `BACKEND_URL=http://localhost:8000 COOKIE_SECURE=false npm run dev`.

## Render services

Backend service:

- Repository: `lameckirungu/Flowguard_Backend`
- Branch: `feat/phases-8-10-uat-readiness`
- Docker command: `sh scripts/start-render.sh`
- Database: Render PostgreSQL `flowgard-db`
- Seed flag: `SEED_DEMO_DATA=true`
- Health path: `/ready`

Frontend service:

- Repository: `lameckirungu/flowguard-frontend`
- Branch: `main`
- Docker service, not a static site
- `BACKEND_URL=https://flowguard-backend-z2wy.onrender.com`
- `COOKIE_SECURE=true`
- `NODE_ENV=production`

Set backend CORS exactly to `https://flowgard-frontend.onrender.com` without a trailing slash.

## Startup sequence

`scripts/start-render.sh` runs Alembic migrations, then the platform admin, tenant/assets, UAT users, and operational-data seeders, then starts Uvicorn on `$PORT`. A failed seed prevents the API from opening; inspect deployment logs before retrying.

## Verification

1. Open `/ready` and confirm HTTP 200.
2. Open `/docs`.
3. Sign in at the frontend with each UAT role.
4. Confirm role-specific navigation and permissions.
5. Inspect dashboard, network map, pumps, alerts, work orders, schedule, model pages, settings, and admin.
6. Verify CSV exports use pump/station labels rather than UUID-only values.

## Recovery

- If a deployment fails, inspect the first Python traceback in Render logs.
- Do not run destructive database resets against the hosted UAT database.
- Re-run a deploy after correcting configuration or code; all UAT seeders are intended to be safe to repeat.
- Free Render services may cold-start and delay the first request.

## Security

Never commit `.env`, database URLs, JWT secrets, SMTP passwords, or copied Render credentials. SMTP is optional in UAT; without it, email delivery is unavailable.
