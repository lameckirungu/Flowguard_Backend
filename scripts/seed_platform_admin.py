"""Seed the single platform-admin account.

This is the only user not created through an onboarding invite: it has no
tenant, and it is what a platform operator uses to onboard tenants (each of
which gets its own ADMIN, who in turn onboards that tenant's users).

Credentials come from settings (PLATFORM_ADMIN_EMAIL / PLATFORM_ADMIN_PASSWORD,
defaults platform.admin@flow.com / Admin@123). Idempotent: if the account
already exists it is left untouched.

Usage:
    python scripts/seed_platform_admin.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session  # noqa: E402

from app.core.auth import hash_password  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.user.models import User, UserRole  # noqa: E402


def seed(db: Session) -> User:
    existing = (
        db.query(User)
        .filter(User.email == settings.platform_admin_email)
        .one_or_none()
    )
    if existing is not None:
        print(f"platform admin {existing.email} already exists ({existing.id})")
        return existing

    admin = User(
        tenant_id=None,
        email=settings.platform_admin_email,
        full_name=settings.platform_admin_full_name,
        role=UserRole.PLATFORM_ADMIN,
        hashed_password=hash_password(settings.platform_admin_password),
        must_reset_password=False,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"created platform admin {admin.email} ({admin.id})")
    return admin


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
