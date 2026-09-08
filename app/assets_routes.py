import uuid
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.permissions import Permission
from app.core.auth import require_permission
from app.core.tenancy import get_current_tenant_id
from app.pump.models import Pump
from app.station.models import Station
router = APIRouter(prefix="/api/v1/assets", tags=["assets"])
@router.get("")
def list_assets(db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(get_current_tenant_id)):
    stations = list(db.scalars(select(Station).where(Station.tenant_id == tenant_id, Station.is_active.is_(True)).order_by(Station.code)))
    pumps = list(db.scalars(select(Pump).where(Pump.tenant_id == tenant_id).order_by(Pump.tag_number)))
    return [{"asset_type":"station","asset_key":station.code,"name":station.name,"region":station.region,"status":"active" if station.is_active else "inactive","parent_key":None} for station in stations] + [{"asset_type":"pump","asset_key":pump.tag_number,"name":pump.tag_number,"region":next((s.region for s in stations if s.id == pump.station_id),None),"status":pump.status.value,"parent_key":next((s.code for s in stations if s.id == pump.station_id),None)} for pump in pumps]
@router.get("/summary")
def asset_summary(db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(get_current_tenant_id), _=Depends(require_permission(Permission.MANAGE_ASSETS))):
    stations = db.scalar(select(Station).where(Station.tenant_id == tenant_id).count()) if False else len(list(db.scalars(select(Station).where(Station.tenant_id == tenant_id))))
    pumps = len(list(db.scalars(select(Pump).where(Pump.tenant_id == tenant_id))))
    return {"stations": stations, "pumps": pumps, "hierarchy": "tenant/network/region/pipeline/segment/station/pump"}
