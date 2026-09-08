# Flowguard Platform — Operations & Deployment Runbook

**Project Title:** Predictive Maintenance for Kenya Pipeline Company (KPC) Pump Infrastructure  
**Repository:** [Flowguard Backend & Streamlit Dashboard](https://github.com/Obunde/Flowguard_Backend)  
---

## 1. System Overview

Flowguard is a multi-tenant condition-based predictive maintenance platform designed specifically for fluid-transport pipeline infrastructure (booster & depot stations, centrifugal pumps across KPC's 1,342 km network corridor from Mombasa to Kisumu). 

The system replaces fixed-interval maintenance with real-time operational risk assessment, physics-based Health Deviation Index (HDI) modeling, high-precision Remaining Useful Life (RUL) regression, SHAP explainability attributions, and auto-generated work order scheduling.

```
                  ┌─────────────────────────────────────────┐
                  │       Streamlit Dashboard (8501)       │
                  │   (KPC Fleet Map, HDI, RUL, SHAP, WO)   │
                  └────────────────────┬────────────────────┘
                                       │ REST / JWT Auth
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │          FastAPI Backend (8000)         │
                  │    (13 Domain Modules, REST APIs)       │
                  └────────────────────┬────────────────────┘
                                       │ SQL / Psycopg 3
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │         PostgreSQL Database (5432)      │
                  │  (Multi-tenant DB, Anchored on KPC)     │
                  └─────────────────────────────────────────┘
```

---

## 2. Prerequisites & Environment Setup

### System Prerequisites
- **Python:** Version 3.11+ (Python 3.13 tested & supported)
- **Database:** PostgreSQL 14+ (or SQLite for lightweight local testing)
- **Package Manager:** `uv` (recommended) or `pip` / `venv`
- **Containerization:** Docker Engine 24+ & Docker Compose v2+

### Environment Configuration
1. Copy the template environment configuration file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` to set your local or production database parameters and secret keys:
   ```ini
   APP_NAME=flowgard
   ENVIRONMENT=development
   DEBUG=true
   DATABASE_URL=postgresql+psycopg://flowgard:flowgard@localhost:5432/flowgard
   TEST_DATABASE_URL=postgresql+psycopg://flowgard:flowgard@localhost:5432/flowgard_test
   JWT_SECRET_KEY=change-this-to-a-secure-random-secret-in-production
   JWT_ALGORITHM=HS256
   JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
   CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:8501
   API_BASE_URL=http://localhost:8000
   ```

> ⚠️ **Security Requirement:** Never commit `.env` or any production secret key to version control. `.env` is explicitly ignored via `.gitignore`.

---

## 3. Installation & Database Provisioning

### Option A: Using Local Virtual Environment (`pip` & `venv`)
```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install backend and dashboard dependencies
pip install -r requirements.txt -r requirements-dashboard.txt

# 3. Run Alembic migrations to apply full database schema
# 4. Seed platform admin account and KPC anchor tenant reference data
python scripts/seed_platform_admin.py
python scripts/seed_kpc_tenant.py
```

### Option B: Using `uv` Package Manager
```bash
# 1. Synchronize virtual environment dependencies
uv sync

# 2. Execute Alembic schema migrations
uv run alembic upgrade head

# 3. Seed platform admin and KPC anchor tenant reference data
uv run python scripts/seed_platform_admin.py
uv run python scripts/seed_kpc_tenant.py
```

### Option C: Using Docker Compose (Full Stack Deployment)
```bash
# 1. Build and start PostgreSQL database, FastAPI API, and Streamlit Dashboard
docker compose up --build -d

# 2. Seed KPC anchor tenant data into the containerized database
docker compose --profile seed run --rm seed
```

---

## 4. Running the Platform Services

### Local Execution (Independent Processes)

1. **Start the FastAPI Backend Service:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   - **API Base Endpoint:** `http://localhost:8000`
   - **Health Check:** `http://localhost:8000/health`
   - **Interactive Swagger UI:** `http://localhost:8000/docs`
   - **ReDoc API Spec:** `http://localhost:8000/redoc`

2. **Start the Streamlit Operational Dashboard:**
   ```bash
   streamlit run streamlit_app/app.py --server.port 8501
   ```
   - **Dashboard Access:** `http://localhost:8501`
   - Default credentials for sign-in: `admin@kpc.co.ke` / `password123`

---

## 5. Deployment Options for Streamlit & FastAPI

### Cloud Deployment Option 1: Docker Compose Stack (Single VPS / EC2 / VM)
Deploying the complete stack on a Linux VM (AWS EC2, DigitalOcean Droplet, Azure VM):
```bash
# Clone repository
git clone https://github.com/Obunde/Flowguard_Backend.git
cd Flowguard_Backend

# Configure environment variables
cp .env.example .env

# Start background services
docker compose up -d --build

# Run tenant seed script
docker compose --profile seed run --rm seed
```
Access endpoints:
- API Backend: `http://<YOUR_SERVER_IP>:8000`
- Streamlit UI: `http://<YOUR_SERVER_IP>:8501`

---

### Cloud Deployment Option 2: Streamlit Community Cloud (Frontend) + Managed Backend
To deploy the interactive Streamlit dashboard on **Streamlit Community Cloud**:

1. Push your repository to GitHub (`Obunde/Flowguard_Backend`).
2. Log into [share.streamlit.io](https://share.streamlit.io/).
3. Click **New App** and select:
   - **Repository:** `Obunde/Flowguard_Backend`
   - **Branch:** `main` (or `feature/track-b-implementation`)
   - **Main file path:** `streamlit_app/app.py`
4. In **Advanced Settings**, configure secrets/environment variables:
   ```toml
   API_BASE_URL = "https://your-api-domain.com"
   ```
5. Click **Deploy**. Streamlit Cloud will install dependencies from `requirements-dashboard.txt` (or `requirements.txt`) and launch your application.

---

### Cloud Deployment Option 3: Render / Railway PaaS
- **FastAPI API Service:** Deploy as a Docker Web Service using `Dockerfile` (Port `8000`).
- **Streamlit Dashboard Service:** Deploy as a Docker Web Service using `Dockerfile.dashboard` (Port `8501`), setting `API_BASE_URL` to your FastAPI live URL.
- **PostgreSQL Database:** Provision a managed PostgreSQL instance and set `DATABASE_URL` accordingly.

---

## 6. Testing & Quality Assurance

### Automated Testing & Linting Checks
To run code formatting, static analysis (Ruff), and the complete 68-test suite:
```bash
./scripts/check.sh
```

### Manual Pytest Execution
```bash
# Run all unit and integration tests with verbose output
pytest -v

# Run tests with code coverage analysis
pytest --cov=app tests/
```

---

## 7. Architecture & API Module Reference Matrix

The Flowguard platform enforces strict multi-tenant scoping (`tenant_id`) and domain module segregation across Track A and Track B requirements:

| Module | Track | Primary Scope & Functional Responsibility | API Prefix / Service |
| :--- | :--- | :--- | :--- |
| `tenant` | Track A | Multi-tenant onboarding/branding/thresholds; platform-admin gated; creates tenant's first `admin` | `/api/v1/tenants` |
| `user` | Track A | Invite-only user onboarding, role-based access (admin, operator, engineer), JWT login, password reset | `/api/v1/users` |
| `station` | Track B | KPC pump station metadata across PS1 (Mombasa) to PS13 (Kisumu) | `/api/v1/stations` |
| `pump` | Track B | Centrifugal pump reference data, motor ratings, and lifecycle metadata | `/api/v1/pumps` |
| `etl` | Shared | Medallion data pipeline (Bronze raw ingest -> Silver telemetry -> Gold features) | Internal service |
| `feature_engineering` | Track A | Rolling-window feature vector construction & Gold-layer flattening | Internal service |
| `flowgard_engine` | Track B | Physics-based pressure residual model & Health Deviation Index (HDI) computation | `/api/v1/flowgard-engine` |
| `prediction` | Track B | XGBoost 7-day failure risk score & failure mode classification | `/api/v1/predictions` |
| `rul` | Track A | Remaining Useful Life (RUL) regression in days/hours with MC Dropout confidence bounds | `/api/v1/rul` |
| `explainability` | Track B | SHAP sub-assembly feature attributions (bearing, impeller, seal, motor) | `/api/v1/explainability` |
| `model_metrics` | Track A | Model evaluation metrics, accuracy, F1-score, confusion matrix tracking | `/api/v1/model-metrics` |
| `alert` | Track A | Dynamic threshold evaluation, real-time risk alert triggers & notifications | `/api/v1/alerts` |
| `work_order` | Track B | Maintenance work order creation, approval workflows, and status tracking | `/api/v1/work-orders` |
| `maintenance_schedule` | Track A | Prioritized RUL-ranked fleet maintenance calendar and schedule management | `/api/v1/maintenance-schedule` |

---

## 8. Operational Troubleshooting & Maintenance Procedures

### Database Migration Rollback
If a database schema migration needs to be reversed:
```bash
# Roll back 1 migration step
alembic downgrade -1
```

### Full Local Database Reset & Reseed
To reset local development data to a clean state:
```bash
python reset_db.py
alembic upgrade head
python scripts/seed_platform_admin.py
python scripts/seed_kpc_tenant.py
```

### Onboarding a Tenant and Its Users

1. Log in as the platform admin (`POST /api/v1/users/login`, default `platform.admin@flow.com` / `Admin@123`).
2. `POST /api/v1/tenants` with the tenant config plus `admin_email` / `admin_full_name`. This creates the tenant and its first `admin` user and emails that admin a first-time password (SMTP must be configured, or the call returns `503` with the tenant still created).
3. The tenant admin logs in with the emailed password → gets `reset_required: true` + a `reset_token` → `POST /api/v1/users/reset-password` to set a real password.
4. The tenant admin invites more users via `POST /api/v1/users` (`email`, `full_name`, `role`); each follows the same first-login reset flow.

### Handling CORS Cross-Origin Issues
If the Streamlit dashboard fails to make requests to the API backend due to CORS policies:
1. Ensure `CORS_ALLOW_ORIGINS` in `.env` includes `http://localhost:8501` (or your production frontend URL).
2. Restart the FastAPI uvicorn server or container.

### Pre-Commit Security Checklist
Before committing or pushing to GitHub:
1. Verify no `.env` file or secret credentials are stage-committed (`git status`).
2. Run unit tests (`pytest -v`).
3. Validate OpenAPI schema at `http://localhost:8000/docs`.
>>>>>>> origin/feat/feature_engineering
