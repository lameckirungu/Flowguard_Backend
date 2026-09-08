"""Smoke tests for the tenant module."""
from sqlalchemy.orm import Session

from app.tenant import services
from app.tenant.schemas import TenantCreate
from app.user.models import UserRole
from tests.conftest import auth_headers, make_user


def _tenant_payload(**overrides) -> TenantCreate:
    data = {
        "name": "Acme Pipelines",
        "slug": "acme-pipelines",
        "admin_email": "admin@acme.example.com",
        "admin_full_name": "Acme Admin",
    }
    data.update(overrides)
    return TenantCreate(**data)


def test_router_registered():
    from app.main import app

    assert any(path.startswith("/api/v1/tenants") for path in app.openapi()["paths"])


def test_list_tenants_requires_auth(client):
    response = client.get("/api/v1/tenants")
    assert response.status_code == 401


def test_list_tenants_forbidden_for_tenant_admin(client, tenant_a, db_session):
    admin = make_user(db_session, tenant_a, UserRole.ADMIN)
    response = client.get("/api/v1/tenants", headers=auth_headers(admin))
    assert response.status_code == 403


def test_onboard_tenant_creates_admin_and_emails_password(db_session: Session, sent_emails):
    tenant, admin = services.onboard_tenant(db_session, _tenant_payload())

    assert tenant.id is not None
    assert tenant.is_active is True
    assert admin.tenant_id == tenant.id
    assert admin.role == UserRole.ADMIN
    assert admin.must_reset_password is True

    assert len(sent_emails) == 1
    assert sent_emails[0]["to"] == "admin@acme.example.com"

    by_slug = services.get_tenant_by_slug(db_session, "acme-pipelines")
    assert by_slug is not None
    assert by_slug.id == tenant.id


def test_tenant_routes_crud(client, platform_admin_headers, tenant_a):
    # List tenants
    res = client.get("/api/v1/tenants", headers=platform_admin_headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Get single tenant
    res = client.get(f"/api/v1/tenants/{tenant_a.id}", headers=platform_admin_headers)
    assert res.status_code == 200
    assert res.json()["name"] == tenant_a.name

    # Update tenant
    res = client.patch(
        f"/api/v1/tenants/{tenant_a.id}",
        json={"name": "Updated Pipeline Corp"},
        headers=platform_admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Updated Pipeline Corp"

    # 404 test
    res = client.get("/api/v1/tenants/00000000-0000-0000-0000-000000000000", headers=platform_admin_headers)
    assert res.status_code == 404


def test_onboard_tenant_endpoint_requires_platform_admin(
    client, platform_admin_headers, sent_emails
):
    response = client.post(
        "/api/v1/tenants",
        headers=platform_admin_headers,
        json={
            "name": "Beta Pipelines",
            "slug": "beta-pipelines",
            "admin_email": "admin@beta.example.com",
            "admin_full_name": "Beta Admin",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["admin_email"] == "admin@beta.example.com"
    assert "admin_user_id" in body
    assert len(sent_emails) == 1
