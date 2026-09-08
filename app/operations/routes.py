import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.core.config import settings
from app.core.db import get_db
from app.core.permissions import Permission
from app.core.tenancy import get_current_tenant_id
from app.operations import actions, services
from app.operations.action_schemas import ActionResult, DigestRequest
from app.operations.schemas import Capabilities, DashboardSummary, ModelSummary, PumpHealth

router = APIRouter(prefix="/api/v1", tags=["operations"])


@router.get("/capabilities", response_model=Capabilities)
def capabilities() -> Capabilities:
    return Capabilities(
        smtp_digest=bool(settings.smtp_host and settings.smtp_from_email),
        live_telemetry=settings.data_mode == "operational",
        data_mode=settings.data_mode,
    )


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> DashboardSummary:
    return services.dashboard(db, tenant_id)


@router.get("/pump-health", response_model=list[PumpHealth])
def pump_health(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> list[PumpHealth]:
    return services.list_pump_health(db, tenant_id)


@router.get("/pump-health/{pump_id}", response_model=PumpHealth)
def pump_health_detail(
    pump_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> PumpHealth:
    result = next(
        (pump for pump in services.list_pump_health(db, tenant_id) if pump.id == pump_id), None
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Pump health record not found")
    return result


@router.get("/model-metrics/latest-summary", response_model=ModelSummary)
def latest_model_summary(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> ModelSummary:
    return services.model_summary(db, tenant_id)


@router.post("/alerts/auto-generate", response_model=ActionResult)
def auto_generate_alerts(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.MANAGE_ALERTS)),
) -> ActionResult:
    created = actions.auto_generate_alerts(db, tenant_id)
    return ActionResult(created=created, message=f"Created {created} alerts")


@router.post("/maintenance-schedule/auto-generate", response_model=ActionResult)
def auto_generate_schedule(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.MANAGE_SCHEDULE)),
) -> ActionResult:
    created = actions.auto_generate_schedule(db, tenant_id)
    return ActionResult(created=created, message=f"Created {created} schedule entries")


@router.post("/alerts/digest", response_model=ActionResult)
def send_digest(
    payload: DigestRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.MANAGE_ALERTS)),
) -> ActionResult:
    try:
        actions.send_alert_digest(db, tenant_id, str(payload.recipient))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return ActionResult(message=f"Digest sent to {payload.recipient}")


@router.get("/exports/work-orders.csv")
def export_work_orders(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_permission(Permission.EXPORT_REPORTS)),
) -> Response:
    return Response(
        actions.work_orders_csv(db, tenant_id),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=flowgard-work-orders.csv"},
    )
