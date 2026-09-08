"""Shared pytest fixtures.

Tests run against a real Postgres database (`settings.test_database_url`)
so tenant_id FK/UUID behavior matches production. Tables are created once
per test session; each test gets a clean slate via a post-test truncate
rather than transaction rollback, since service functions call `db.commit()`
internally (a nested-SAVEPOINT scheme would fight that).
"""
import math
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Import every module's models so they register on Base.metadata — mirrors
# migrations/env.py. Add a line here whenever a new module gets models.py.
import app.alert.models  # noqa: F401,E402
import app.etl.bronze.models  # noqa: F401,E402
import app.etl.gold.models  # noqa: F401,E402
import app.etl.silver.models  # noqa: F401,E402
import app.explainability.models  # noqa: F401,E402
import app.flowgard_engine.models  # noqa: F401,E402
import app.maintenance_schedule.models  # noqa: F401,E402
import app.model_metrics.models  # noqa: F401,E402
import app.prediction.models  # noqa: F401,E402
import app.pump.models  # noqa: F401,E402
import app.rul.models  # noqa: F401,E402
import app.station.models  # noqa: F401,E402
import app.tenant.models  # noqa: F401,E402
import app.user.models  # noqa: F401,E402
import app.work_order.models  # noqa: F401,E402
from app.core.auth import create_access_token, hash_password
from app.core.base import Base
from app.core.config import settings
from app.core.db import get_db
from app.main import app as fastapi_app  # noqa: E402
from app.station.models import Station  # noqa: E402
from app.tenant.models import Tenant  # noqa: E402
from app.user.models import User, UserRole  # noqa: E402

TEST_DATABASE_URL = settings.test_database_url or settings.database_url

try:
    engine = create_engine(TEST_DATABASE_URL, future=True)
    with engine.connect() as conn:
        pass
except Exception:
    TEST_DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )


class SqliteStdDev:
    def __init__(self):
        self.values = []

    def step(self, value):
        if value is not None:
            self.values.append(float(value))

    def finalize(self):
        if len(self.values) <= 1:
            return 0.0
        mean = sum(self.values) / len(self.values)
        variance = sum((x - mean) ** 2 for x in self.values) / (len(self.values) - 1)
        return math.sqrt(variance)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in str(engine.url):
        dbapi_connection.create_aggregate("stddev", 1, SqliteStdDev)
        dbapi_connection.create_aggregate("stddev_samp", 1, SqliteStdDev)
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        for schema in ["master", "bronze", "silver", "gold"]:
            cursor.execute(f"ATTACH DATABASE ':memory:' AS {schema}")
        cursor.close()


TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(scope="session", autouse=True)
def _database():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())


@pytest.fixture(autouse=True)
def sent_emails(monkeypatch) -> list[dict]:
    """Capture onboarding emails instead of hitting SMTP. Autouse so no test
    can accidentally make a real send; return value is the list of messages
    (dicts with to/subject/body) for tests that want to assert on them."""
    captured: list[dict] = []

    def _capture(*, to: str, subject: str, body: str) -> None:
        captured.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr("app.core.email.send_email", _capture)
    return captured


@pytest.fixture()
def client(db_session: Session):
    def _get_db_override():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _get_db_override
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


def _make_tenant(db_session: Session, name: str) -> Tenant:
    tenant = Tenant(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture()
def tenant_a(db_session: Session) -> Tenant:
    return _make_tenant(db_session, "Tenant A")


@pytest.fixture()
def tenant_b(db_session: Session) -> Tenant:
    return _make_tenant(db_session, "Tenant B")


@pytest.fixture()
def station_a(db_session: Session, tenant_a: Tenant) -> Station:
    station = Station(tenant_id=tenant_a.id, code="PS1", name="PS1 Mombasa")
    db_session.add(station)
    db_session.commit()
    db_session.refresh(station)
    return station


@pytest.fixture()
def station_b(db_session: Session, tenant_b: Tenant) -> Station:
    station = Station(tenant_id=tenant_b.id, code="PS1", name="PS1 Mombasa")
    db_session.add(station)
    db_session.commit()
    db_session.refresh(station)
    return station


def make_user(
    db_session: Session,
    tenant: Tenant,
    role: UserRole = UserRole.ADMIN,
    *,
    must_reset_password: bool = False,
) -> User:
    user = User(
        tenant_id=tenant.id,
        email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("password123"),
        full_name="Test User",
        role=role,
        must_reset_password=must_reset_password,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def make_platform_admin(db_session: Session) -> User:
    user = User(
        tenant_id=None,
        email=f"platform-{uuid.uuid4().hex[:8]}@flow.com",
        hashed_password=hash_password("password123"),
        full_name="Platform Admin",
        role=UserRole.PLATFORM_ADMIN,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, email=user.email, role=user.role.value
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_a(db_session: Session, tenant_a: Tenant) -> User:
    return make_user(db_session, tenant_a)


@pytest.fixture()
def user_b(db_session: Session, tenant_b: Tenant) -> User:
    return make_user(db_session, tenant_b)


@pytest.fixture()
def platform_admin(db_session: Session) -> User:
    return make_platform_admin(db_session)


@pytest.fixture()
def platform_admin_headers(platform_admin: User) -> dict[str, str]:
    return auth_headers(platform_admin)


@pytest.fixture()
def headers_a(user_a: User) -> dict[str, str]:
    return auth_headers(user_a)


@pytest.fixture()
def headers_b(user_b: User) -> dict[str, str]:
    return auth_headers(user_b)
