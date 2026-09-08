from datetime import UTC, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import and_, case, func, select

from app.core.config import settings
from app.prediction.models import PredictionResult
from app.pump.models import Pump
from app.station.models import Station
from app.tenant.models import Tenant
from app.work_order.models import WorkOrder as W, WorkOrderStatus

LABELS = {"confirmed_failure", "degraded", "no_fault_found", "preventive_only", "inconclusive"}


def cohort(tenant_id, filters):
    start = datetime.combine(filters.start, time.min, UTC)
    end = datetime.combine(filters.end + timedelta(days=1), time.min, UTC)
    conditions = [W.tenant_id == tenant_id, W.status == WorkOrderStatus.COMPLETED,
                  W.closed_at >= start, W.closed_at < end]
    if filters.station_id:
        conditions.append(W.station_id == filters.station_id)
    if filters.pump_id:
        conditions.append(W.pump_id == filters.pump_id)
    if filters.outcome == "unlabelled":
        conditions.append(W.outcome.is_(None))
    elif filters.outcome:
        conditions.append(W.outcome == filters.outcome)
    return conditions


def result_rows(db, tenant_id, conditions, filters, export):
    query = select(W, Pump.tag_number, Station.code, Station.name, PredictionResult.model_version).outerjoin(
        Pump, and_(Pump.id == W.pump_id, Pump.tenant_id == tenant_id)).outerjoin(
        Station, and_(Station.id == W.station_id, Station.tenant_id == tenant_id)).outerjoin(
        PredictionResult, and_(PredictionResult.id == W.source_prediction_id,
                              PredictionResult.tenant_id == tenant_id)).where(*conditions).order_by(W.closed_at.desc(), W.id)
    if not export:
        query = query.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
    output = []
    for row, pump, code, station, model in db.execute(query):
        output.append({"id": row.id, "reference": f"WO-{str(row.id)[:8].upper()}",
            "pump_code": pump or "Unknown pump", "station_code": code or "",
            "station_name": station or "Unknown station", "title": row.title,
            "closed_at": row.closed_at, "created_at": row.created_at, "outcome": row.outcome,
            "post_maintenance_condition": row.post_maintenance_condition,
            "completion_note": row.completion_note, "root_cause": row.root_cause,
            "corrective_action": row.corrective_action, "downtime_minutes": row.downtime_minutes,
            "follow_up_required": row.follow_up_required, "verified_at": row.verified_at,
            "verification_result": row.verification_result, "verification_note": row.verification_note,
            "model_version": model,
            "source_prediction": f"PRED-{str(row.source_prediction_id)[:8].upper()}" if row.source_prediction_id else None})
    return output


def report(db, current, filters, *, export=False):
    tenant_id = current.tenant_id
    conditions = cohort(tenant_id, filters)
    count_if = lambda predicate: func.coalesce(func.sum(case((predicate, 1), else_=0)), 0)
    valid_duration = and_(W.created_at.is_not(None), W.closed_at >= W.created_at)
    valid_downtime = and_(W.downtime_minutes.is_not(None), W.downtime_minutes >= 0)
    labelled = W.outcome.in_(LABELS)
    aggregate = db.execute(select(
        func.count(W.id).label("completed"), count_if(labelled).label("labelled"),
        count_if(W.outcome.is_(None)).label("unlabelled"),
        count_if(and_(W.verified_at.is_not(None), W.verification_result == "passed")).label("verified"),
        count_if(and_(W.verified_at.is_not(None), W.verification_result == "failed")).label("failed_verification"),
        count_if(and_(W.verified_at.is_not(None), W.verification_result == "inconclusive")).label("inconclusive_verification"),
        count_if(W.follow_up_required.is_(True)).label("follow_up"),
        func.coalesce(func.sum(case((valid_downtime, W.downtime_minutes), else_=0)), 0).label("recorded_downtime_minutes"),
        count_if(valid_downtime).label("downtime_records"),
        count_if(valid_duration).label("duration_records")
    ).where(*conditions)).mappings().one()
    metrics = dict(aggregate)
    metrics["unverified"] = metrics["completed"] - metrics["verified"] - metrics["failed_verification"] - metrics["inconclusive_verification"]
    metrics["invalid_labels"] = metrics["completed"] - metrics["labelled"] - metrics["unlabelled"]
    metrics["missing_or_invalid_downtime"] = metrics["completed"] - metrics["downtime_records"]
    metrics["duration_exclusions"] = metrics["completed"] - metrics["duration_records"]
    # PostgreSQL computes the median over the complete filtered cohort, not the current page.
    seconds = func.extract("epoch", W.closed_at - W.created_at)
    median = db.scalar(select(func.percentile_cont(0.5).within_group(seconds)).where(*conditions, valid_duration))
    metrics["median_completion_hours"] = round(float(median) / 3600, 2) if median is not None else None
    if export and metrics["completed"] > 10000:
        raise HTTPException(422, "Export exceeds 10,000 records; narrow the date range or filters")
    tenant = db.get(Tenant, tenant_id)
    metadata = {"tenant_name": tenant.name, "data_mode": settings.data_mode,
        "generated_at": datetime.now(UTC), "exported_by": current.email, "timezone": "UTC",
        "start": filters.start, "end": filters.end,
        "basis": "Completed work with closed_at within the selected UTC dates; counts use the full filtered cohort",
        "limitations": "Recorded outcomes only. No avoided-failure, savings, model-accuracy or causal claims."}
    return {"metrics": metrics, "metadata": metadata,
            "items": result_rows(db, tenant_id, conditions, filters, export),
            "page": filters.page, "page_size": filters.page_size, "total": metrics["completed"]}
