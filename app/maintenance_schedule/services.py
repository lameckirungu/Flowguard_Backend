"""Business logic for the maintenance schedule.

CRUD is implemented. RUL-ranked prioritisation (deriving `priority_rank`
and `scheduled_date` from RUL estimates across a tenant's fleet) is not
implemented yet.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.maintenance_schedule.models import ScheduledMaintenance, ScheduleStatus
from app.maintenance_schedule.schemas import ScheduledMaintenanceCreate, ScheduledMaintenanceUpdate
from app.rul.services import get_latest_rul_estimate, run_rul_estimate


def create_scheduled_maintenance(
    db: Session, tenant_id: uuid.UUID, payload: ScheduledMaintenanceCreate
) -> ScheduledMaintenance:
    entry = ScheduledMaintenance(tenant_id=tenant_id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_scheduled_maintenance(
    db: Session, tenant_id: uuid.UUID, entry_id: uuid.UUID
) -> ScheduledMaintenance | None:
    return db.scalar(
        select(ScheduledMaintenance).where(
            ScheduledMaintenance.id == entry_id, ScheduledMaintenance.tenant_id == tenant_id
        )
    )


def list_scheduled_maintenance(
    db: Session,
    tenant_id: uuid.UUID,
    status_filter: ScheduleStatus | None = None,
    pump_id: uuid.UUID | None = None,
) -> list[ScheduledMaintenance]:
    stmt = select(ScheduledMaintenance).where(ScheduledMaintenance.tenant_id == tenant_id)
    if status_filter is not None:
        stmt = stmt.where(ScheduledMaintenance.status == status_filter)
    if pump_id is not None:
        stmt = stmt.where(ScheduledMaintenance.pump_id == pump_id)
    return list(db.scalars(stmt.order_by(ScheduledMaintenance.scheduled_date)))


def update_scheduled_maintenance(
    db: Session, tenant_id: uuid.UUID, entry_id: uuid.UUID, payload: ScheduledMaintenanceUpdate
) -> ScheduledMaintenance | None:
    entry = get_scheduled_maintenance(db, tenant_id, entry_id)
    if entry is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


def rank_schedule_by_rul(db: Session, tenant_id: uuid.UUID) -> list[ScheduledMaintenance]:
    """Re-derive `priority_rank` for a tenant's schedule from the latest RUL
    estimates (app.rul). Lower RUL (urgency) gets lower priority_rank number (1 = highest priority).
    """
    schedules = list_scheduled_maintenance(db, tenant_id)
    if not schedules:
        return []

    # Map each schedule to its target pump's latest RUL days
    ranked_tuples = []
    for sched in schedules:
        rul_rec = get_latest_rul_estimate(db, tenant_id, sched.pump_id)
        if rul_rec is None or rul_rec.remaining_useful_life_days is None:
            rul_rec = run_rul_estimate(db, tenant_id, sched.pump_id)
        rul_days = float(rul_rec.remaining_useful_life_days) if rul_rec.remaining_useful_life_days is not None else 999.0
        ranked_tuples.append((rul_days, sched))

    # Sort by remaining useful life ascending (lowest RUL days = most urgent)
    ranked_tuples.sort(key=lambda t: t[0])

    updated_schedules = []
    for rank_idx, (_, sched) in enumerate(ranked_tuples, start=1):
        sched.priority_rank = rank_idx
        updated_schedules.append(sched)

    db.commit()
    for item in updated_schedules:
        db.refresh(item)

    return updated_schedules
