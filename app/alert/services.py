"""Business logic for alerts.

`create_alert`/read functions are implemented (plain persistence, not
"logic"). Deciding *when* to raise an alert from a Diagnostic result
(pressure residual, risk score, RUL) is threshold-evaluation logic that
belongs to a future `evaluate_thresholds`-style function — not implemented
yet.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alert.models import Alert, AlertSeverity, AlertStatus
from app.alert.schemas import AlertCreate, AlertUpdate
from app.feature_engineering.services import build_feature_vector
from app.prediction.services import get_latest_prediction
from app.pump.models import Pump
from app.rul.services import get_latest_rul_estimate
from app.tenant.models import Tenant


def create_alert(db: Session, tenant_id: uuid.UUID, payload: AlertCreate) -> Alert:
    alert = Alert(tenant_id=tenant_id, **payload.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def get_alert(db: Session, tenant_id: uuid.UUID, alert_id: uuid.UUID) -> Alert | None:
    return db.scalar(select(Alert).where(Alert.id == alert_id, Alert.tenant_id == tenant_id))


def list_alerts(
    db: Session,
    tenant_id: uuid.UUID,
    status_filter: AlertStatus | None = None,
    pump_id: uuid.UUID | None = None,
) -> list[Alert]:
    stmt = select(Alert).where(Alert.tenant_id == tenant_id)
    if status_filter is not None:
        stmt = stmt.where(Alert.status == status_filter)
    if pump_id is not None:
        stmt = stmt.where(Alert.pump_id == pump_id)
    return list(db.scalars(stmt.order_by(Alert.triggered_at.desc())))


def update_alert(
    db: Session, tenant_id: uuid.UUID, alert_id: uuid.UUID, payload: AlertUpdate
) -> Alert | None:
    alert = get_alert(db, tenant_id, alert_id)
    if alert is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)
    db.commit()
    db.refresh(alert)
    return alert


def evaluate_thresholds(db: Session, tenant_id: uuid.UUID, pump_id: uuid.UUID) -> list[Alert]:
    """Compare the latest Flowgard/prediction/RUL results against the
    tenant's configured thresholds (app.tenant) and raise alerts as needed.
    """
    pump = db.scalar(select(Pump).where(Pump.id == pump_id, Pump.tenant_id == tenant_id))
    if pump is None:
        raise ValueError(f"Pump {pump_id} not found for tenant {tenant_id}")

    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    vib_threshold = float(tenant.vibration_threshold_mm_s) if tenant and tenant.vibration_threshold_mm_s else 4.5

    features = build_feature_vector(db, tenant_id, pump_id)
    prediction = get_latest_prediction(db, tenant_id, pump_id)
    rul = get_latest_rul_estimate(db, tenant_id, pump_id)

    new_alerts: list[Alert] = []

    vib = features.get("vibration_axial_rolling_avg", 1.5)
    hdi = features.get("health_deviation_index", 0.1)
    risk_score = float(prediction.risk_score_7d) if prediction and prediction.risk_score_7d is not None else 0.1

    if vib > vib_threshold or risk_score >= 0.85:
        alert = create_alert(
            db,
            tenant_id,
            AlertCreate(
                pump_id=pump_id,
                station_id=pump.station_id,
                severity=AlertSeverity.CRITICAL,
                message=f"Critical vibration ({vib} mm/s) or high risk score ({risk_score}) detected",
                triggered_at=datetime.now(UTC),
                source="THRESHOLD_EVALUATOR",
            ),
        )
        new_alerts.append(alert)
    elif hdi >= 0.6 or risk_score >= 0.70:
        alert = create_alert(
            db,
            tenant_id,
            AlertCreate(
                pump_id=pump_id,
                station_id=pump.station_id,
                severity=AlertSeverity.WARNING,
                message=f"Elevated Health Deviation Index ({hdi}) or 7-day risk ({risk_score})",
                triggered_at=datetime.now(UTC),
                source="THRESHOLD_EVALUATOR",
            ),
        )
        new_alerts.append(alert)

    if rul and rul.remaining_useful_life_days and float(rul.remaining_useful_life_days) < 14.0:
        alert = create_alert(
            db,
            tenant_id,
            AlertCreate(
                pump_id=pump_id,
                station_id=pump.station_id,
                severity=AlertSeverity.WARNING,
                message=f"Low Remaining Useful Life: {rul.remaining_useful_life_days} days remaining",
                triggered_at=datetime.now(UTC),
                source="RUL_EVALUATOR",
            ),
        )
        new_alerts.append(alert)

    return new_alerts
