from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.auth import require_permission
from app.core.db import get_db
from app.core.permissions import Permission
from app.pump.models import Pump
from app.reporting.csv import csv_response
from app.reporting.schemas import ResultFilters
from app.reporting.services import report
from app.station.models import Station

router = APIRouter(prefix="/api/v1/maintenance-results", tags=["maintenance-results"])


@router.get("")
def results(filters: ResultFilters = Depends(), db=Depends(get_db),
            current=Depends(require_permission(Permission.VIEW_OPERATIONS))):
    return report(db, current, filters)


@router.get("/options")
def options(db=Depends(get_db), current=Depends(require_permission(Permission.VIEW_OPERATIONS))):
    tenant = current.tenant_id
    return {"stations": [{"id": s.id, "label": f"{s.code} — {s.name}"} for s in db.scalars(
        select(Station).where(Station.tenant_id == tenant).order_by(Station.code))],
        "pumps": [{"id": p.id, "label": p.tag_number, "station_id": p.station_id} for p in db.scalars(
        select(Pump).where(Pump.tenant_id == tenant).order_by(Pump.tag_number))]}


@router.get("/export.csv")
def export(filters: ResultFilters = Depends(), db=Depends(get_db),
           current=Depends(require_permission(Permission.EXPORT_REPORTS))):
    result = report(db, current, filters, export=True)
    metadata = result["metadata"]
    station = db.scalar(select(Station).where(Station.id == filters.station_id,
                        Station.tenant_id == current.tenant_id)) if filters.station_id else None
    pump = db.scalar(select(Pump).where(Pump.id == filters.pump_id,
                     Pump.tenant_id == current.tenant_id)) if filters.pump_id else None
    extra = {"tenant_name": metadata["tenant_name"], "data_mode": metadata["data_mode"],
        "exported_by": current.email, "exported_at": metadata["generated_at"],
        "timezone": "UTC", "filter_start": filters.start, "filter_end": filters.end,
        "filter_station": station.code if station else ("Unknown station" if filters.station_id else "All"),
        "filter_asset": pump.tag_number if pump else ("Unknown asset" if filters.pump_id else "All"),
        "filter_outcome": filters.outcome or "All"}
    columns = ["reference", "pump_code", "station_code", "station_name", "title", "created_at",
        "closed_at", "outcome", "post_maintenance_condition", "completion_note", "root_cause",
        "corrective_action", "downtime_minutes", "follow_up_required", "verification_result",
        "verification_note", "verified_at", "model_version", "source_prediction", *extra.keys()]
    return csv_response("flowgard-maintenance-results.csv", columns,
                        [{**row, **extra} for row in result["items"]])
