# Flowgard UAT Runbook

## Environment

The hosted UAT consists of a Render FastAPI backend, Render PostgreSQL database, and Next.js frontend. All seeded analytics are synthetic and intended only for grading and workflow demonstration.

## Seeded accounts

- `admin@flowgard.com` — tenant administration and operational control
- `planner@flowgard.com` — maintenance planning and scheduling
- `technician@flowgard.com` — assigned maintenance execution
- `viewer@flowgard.com` — read-only operations

Password for each: `Flowgard-UAT-2026!`

## Acceptance checklist

1. Open the frontend login page and sign in as tenant admin.
2. Confirm dashboard cards contain stations, pumps, risk, RUL, and model data.
3. Open the network map and pump fleet; inspect a pump detail view.
4. Review alerts and acknowledge one as an authorized role.
5. Review work orders, assign/complete an eligible order, and confirm the close action.
6. Review the maintenance schedule and planner actions.
7. Review model performance and governance pages.
8. Open Settings as admin and confirm tenant configuration loads.
9. Open User management as admin and verify role listings.
10. Log out, immediately sign in as another role, and confirm the sidebar/actions change without refreshing.
11. Export work-order or maintenance-outcome CSV and confirm human-readable pump/station names.

## Expected boundaries

- Viewer is read-only.
- Technician sees execution-oriented actions and assigned work.
- Planner sees planning, scheduling, and assignment actions.
- Tenant admin sees tenant settings and user management.
- Platform admin is for cross-tenant API onboarding and does not inherit tenant operational access.
- SMTP email and live SCADA/model execution are not enabled by default.

## Troubleshooting

- `GET /ready` must return 200 before testing the frontend.
- If the dashboard is empty, confirm the backend deployed the latest UAT feature branch and logs contain `Seeded UAT operational records`.
- If login fails with an invalid response, inspect the backend service URL and Render logs.
- If the first request is slow, wait for the free Render service to wake up and retry.
