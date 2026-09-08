"""FastAPI app factory: router registration + middleware wiring.

This is the only place that imports every module's `routes` — modules never
import each other's routes. Adding a new module means adding one line here.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.alert.routes import router as alert_router
from app.assets_routes import router as assets_router
from app.incidents.routes import router as incidents_router
from app.reporting.routes import router as reporting_router
from app.audit.routes import router as audit_router
from app.auth_session.routes import router as auth_router
from app.core.config import settings
from app.core.middleware import add_middleware
from app.explainability.routes import router as explainability_router
from app.maintenance_schedule.routes import router as maintenance_schedule_router
from app.model_metrics.routes import router as model_metrics_router
from app.model_governance_routes import router as model_governance_router
from app.operations.routes import router as operations_router
from app.prediction.routes import router as prediction_router
from app.pump.routes import router as pump_router
from app.rul.routes import router as rul_router
from app.station.routes import router as station_router
from app.telemetry.routes import router as telemetry_router
from app.tenant.routes import router as tenant_router
from app.user.routes import router as user_router
from app.work_order.routes import router as work_order_router

# Modules with no HTTP surface by design (see their own module docstrings):
# app.etl (bronze/silver/gold/simulator), app.feature_engineering,
# app.flowgard_engine. Nothing to register here for them.

ALL_ROUTERS = (
    auth_router,
    audit_router,
    operations_router,
    tenant_router,
    telemetry_router,
    station_router,
    pump_router,
    user_router,
    work_order_router,
    prediction_router,
    rul_router,
    explainability_router,
    alert_router,
    assets_router,
    incidents_router,
    reporting_router,
    maintenance_schedule_router,
    model_metrics_router,
    model_governance_router,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Predictive maintenance platform for fluid-transport pipeline "
            "infrastructure (pumps/pipelines)."
        ),
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    add_middleware(app)

    for router in ALL_ROUTERS:
        app.include_router(router)

    @app.get("/health", tags=["health"])
    def health_check() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name, "environment": settings.environment}

    return app


app = create_app()
