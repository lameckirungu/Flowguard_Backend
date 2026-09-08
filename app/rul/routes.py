"""RUL routes. Thin: translate HTTP <-> services, no business logic."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.tenancy import get_current_tenant_id
from app.rul import services
from app.rul.schemas import RulEstimateRead

router = APIRouter(prefix="/api/v1/rul", tags=["rul"])


@router.get("", response_model=list[RulEstimateRead])
def list_rul_estimates(
    pump_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> list[RulEstimateRead]:
    return services.list_rul_estimates(db, tenant_id, pump_id=pump_id)


@router.get("/pumps/{pump_id}/latest", response_model=RulEstimateRead)
def get_latest_rul_estimate(
    pump_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> RulEstimateRead:
    result = services.get_latest_rul_estimate(db, tenant_id, pump_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No RUL estimate found")
    return result


@router.post("/pumps/{pump_id}/trigger", response_model=RulEstimateRead, status_code=status.HTTP_201_CREATED)
def trigger_rul_estimate(
    pump_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> RulEstimateRead:
    try:
        return services.run_rul_estimate(db, tenant_id, pump_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
