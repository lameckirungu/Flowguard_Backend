import csv
import io
import smtplib
import uuid
from datetime import UTC, date, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alert.models import Alert, AlertSeverity, AlertStatus
from app.core.config import settings
from app.maintenance_schedule.models import ScheduledMaintenance, ScheduleStatus
from app.operations.services import list_pump_health
from app.pump.models import Pump
from app.station.models import Station
from app.work_order.models import WorkOrder, WorkOrderStatus


def auto_generate_alerts(db: Session, tenant_id: uuid.UUID) -> int:
    created = 0
    for pump in list_pump_health(db, tenant_id):
        if pump.risk_probability <= 0.15:
            continue
        existing = db.scalar(
            select(Alert).where(
                Alert.tenant_id == tenant_id,
                Alert.pump_id == pump.id,
                Alert.status != AlertStatus.RESOLVED,
            )
        )
        if existing:
            continue
        severity = AlertSeverity.CRITICAL if pump.risk_probability > 0.5 else AlertSeverity.WARNING
        db.add(
            Alert(
                tenant_id=tenant_id,
                pump_id=pump.id,
                station_id=pump.station_id,
                severity=severity,
                status=AlertStatus.TRIGGERED,
                message=f"{pump.pump_id} failure risk is {pump.risk_probability * 100:.1f}%",
                triggered_at=datetime.now(UTC),
                source="prediction_automation",
            )
        )
        created += 1
    db.commit()
    return created


def auto_generate_schedule(db: Session, tenant_id: uuid.UUID) -> int:
    work_orders = list(
        db.scalars(
            select(WorkOrder)
            .where(WorkOrder.tenant_id == tenant_id, WorkOrder.status == WorkOrderStatus.OPEN)
            .order_by(WorkOrder.due_at.asc().nullslast())
        )
    )
    created = 0
    for rank, work_order in enumerate(work_orders, start=1):
        existing = db.scalar(
            select(ScheduledMaintenance).where(
                ScheduledMaintenance.tenant_id == tenant_id,
                ScheduledMaintenance.work_order_id == work_order.id,
                ScheduledMaintenance.status != ScheduleStatus.CANCELLED,
            )
        )
        if existing:
            continue
        scheduled_date = (
            work_order.due_at.date()
            if work_order.due_at
            else date.today() + timedelta(days=min(rank, 7))
        )
        db.add(
            ScheduledMaintenance(
                tenant_id=tenant_id,
                pump_id=work_order.pump_id,
                station_id=work_order.station_id,
                work_order_id=work_order.id,
                scheduled_date=scheduled_date,
                priority_rank=rank,
                status=ScheduleStatus.PLANNED,
                created_from="work_order_automation",
            )
        )
        created += 1
    db.commit()
    return created


def send_alert_digest(db: Session, tenant_id: uuid.UUID, recipient: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("SMTP is not configured")
    alerts = list(
        db.scalars(
            select(Alert)
            .where(Alert.tenant_id == tenant_id, Alert.status != AlertStatus.RESOLVED)
            .order_by(Alert.triggered_at.desc())
        )
    )
    message = EmailMessage()
    message["Subject"] = f"Flowgard active-alert digest ({len(alerts)})"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        "Flowgard active alerts\n\n"
        + "\n".join(f"[{alert.severity.value.upper()}] {alert.message}" for alert in alerts)
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def work_orders_csv(db: Session, tenant_id: uuid.UUID) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "work_order_reference", "pump_code", "station_code", "station_name",
            "title", "priority", "status", "source", "due_at", "created_at", "closed_at",
        ]
    )
    statement = (
        select(WorkOrder, Pump, Station)
        .join(Pump, Pump.id == WorkOrder.pump_id)
        .join(Station, Station.id == WorkOrder.station_id)
        .where(WorkOrder.tenant_id == tenant_id)
        .order_by(WorkOrder.created_at.desc())
    )
    for sequence, (item, pump, station) in enumerate(db.execute(statement), start=1):
        writer.writerow(
            [
                f"WO-{item.created_at.year if item.created_at else 'XXXX'}-{sequence:04d}",
                pump.tag_number,
                station.code,
                station.name,
                item.title,
                item.priority,
                item.status.value,
                item.source.value,
                item.due_at.isoformat() if item.due_at else "",
                item.created_at.isoformat() if item.created_at else "",
                item.closed_at.isoformat() if item.closed_at else "",
            ]
        )
    return output.getvalue()
