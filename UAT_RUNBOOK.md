# Flowgard UAT Runbook

## Start

1. Copy `.env.example` to `.env` and set a unique `JWT_SECRET_KEY`.
2. Start the existing stack with `docker compose up --build`.
3. Run migrations through the existing `migrate` service.
4. Seed the platform administrator and demo tenant with `docker compose --profile seed run --rm seed`.
5. Start the Next.js frontend using its documented command and confirm its backend proxy points to port 8000.

## Readiness

- `GET /health` confirms that the process is running.
- `GET /ready` confirms that the API can reach PostgreSQL.
- Authenticated `GET /api/v1/pipeline/status` reports telemetry, feature, and prediction freshness for the active tenant.

## Closed-loop acceptance

1. Sign in as a seeded tenant administrator.
2. Confirm stations, pumps, and tenant-scoped users are visible.
3. Confirm Data Operations displays connector and pipeline status.
4. Ingest or simulate telemetry and confirm the latest telemetry timestamp advances.
5. Run the feature/prediction workflow and confirm model and input provenance are retained.
6. Inspect an incident, acknowledge it, and assign ownership.
7. Inspect the linked work order and assign it to a technician.
8. Record a controlled maintenance outcome with a completion note.
9. Verify the outcome and, if failed, create a follow-up work order.
10. Open Maintenance Outcomes and export the report. Confirm that the CSV contains pump and station labels, not only UUIDs.

## Role checks

- Viewer: read-only operations; mutation and restricted export requests are rejected.
- Technician: assigned maintenance execution and evidence capture only.
- Planner: assignment, escalation policy, scheduling, and follow-up management.
- Tenant administrator: tenant users and configuration.
- Platform administrator: tenant lifecycle and platform health, without implicit tenant operational access.

## Recovery

- Preserve the database volume before reset operations.
- Use reset and seed scripts only against the designated UAT tenant.
- Do not use demo credentials or default JWT secrets in a hosted environment.
