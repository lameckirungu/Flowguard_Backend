"""Smoke tests for the user module: registration, login, first-login reset,
tenant scoping."""
from sqlalchemy.orm import Session

from app.user import services
from app.user.models import UserRole
from app.user.schemas import UserCreate
from tests.conftest import auth_headers, make_user


def test_router_registered():
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/users/login" in paths
    assert "/api/v1/users/reset-password" in paths


def test_list_users_requires_auth(client):
    response = client.get("/api/v1/users")
    assert response.status_code == 401


def test_login_returns_access_token_for_normal_user(client, tenant_a, db_session):
    user = make_user(db_session, tenant_a)
    response = client.post(
        "/api/v1/users/login", data={"username": user.email, "password": "password123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reset_required"] is False
    assert body["access_token"]
    assert body["reset_token"] is None


def test_login_rejects_wrong_password(client, tenant_a, db_session):
    user = make_user(db_session, tenant_a)
    response = client.post(
        "/api/v1/users/login", data={"username": user.email, "password": "wrong"}
    )
    assert response.status_code == 401


def test_first_login_requires_password_reset(client, tenant_a, db_session):
    user = make_user(db_session, tenant_a, must_reset_password=True)

    login = client.post(
        "/api/v1/users/login", data={"username": user.email, "password": "password123"}
    )
    assert login.status_code == 200
    body = login.json()
    assert body["reset_required"] is True
    assert body["access_token"] is None
    reset_token = body["reset_token"]
    assert reset_token

    # The reset token is not usable as a normal access token.
    guarded = client.get("/api/v1/users", headers={"Authorization": f"Bearer {reset_token}"})
    assert guarded.status_code == 401

    reset = client.post(
        "/api/v1/users/reset-password",
        json={"reset_token": reset_token, "new_password": "BrandNew@123"},
    )
    assert reset.status_code == 200
    assert reset.json()["access_token"]

    # Old temp password no longer authenticates.
    assert client.post(
        "/api/v1/users/login", data={"username": user.email, "password": "password123"}
    ).status_code == 401

    # New password logs in cleanly, no reset required.
    relogin = client.post(
        "/api/v1/users/login", data={"username": user.email, "password": "BrandNew@123"}
    )
    assert relogin.status_code == 200
    assert relogin.json()["access_token"]
    assert relogin.json()["reset_required"] is False


def test_onboard_user_generates_password_and_emails_it(db_session: Session, tenant_a, sent_emails):
    user = services.onboard_user(
        db_session,
        tenant_a.id,
        UserCreate(email="tech@example.com", full_name="Tech One", role=UserRole.TECHNICIAN),
    )
    assert user.must_reset_password is True
    assert user.hashed_password
    assert len(sent_emails) == 1
    assert sent_emails[0]["to"] == "tech@example.com"


def test_create_user_endpoint_requires_tenant_admin(client, tenant_a, db_session, sent_emails):
    admin = make_user(db_session, tenant_a, UserRole.ADMIN)
    viewer = make_user(db_session, tenant_a, UserRole.VIEWER)

    payload = {"email": "new@example.com", "full_name": "New User", "role": "planner"}

    denied = client.post("/api/v1/users", headers=auth_headers(viewer), json=payload)
    assert denied.status_code == 403

    ok = client.post("/api/v1/users", headers=auth_headers(admin), json=payload)
    assert ok.status_code == 201
    assert ok.json()["must_reset_password"] is True
    assert len(sent_emails) == 1


def test_platform_admin_cannot_use_tenant_scoped_routes(client, platform_admin_headers):
    response = client.get("/api/v1/users", headers=platform_admin_headers)
    assert response.status_code == 403


def test_service_enforces_tenant_scope(db_session: Session, tenant_a, tenant_b):
    user_a = make_user(db_session, tenant_a)
    make_user(db_session, tenant_b)

    users_for_a = services.list_users(db_session, tenant_a.id)
    assert [u.id for u in users_for_a] == [user_a.id]
