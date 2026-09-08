"""Create the four tenant roles used by the repeatable UAT scenario."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.auth import hash_password
from app.core.db import SessionLocal
from app.tenant.models import Tenant
from app.user.models import User, UserRole

USERS = (("admin", "Flowgard Administrator", UserRole.ADMIN), ("planner", "Maintenance Planner", UserRole.PLANNER), ("technician", "Field Technician", UserRole.TECHNICIAN), ("viewer", "Operations Viewer", UserRole.VIEWER))

def main():
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == os.getenv("UAT_TENANT_SLUG", "kpc")))
        if tenant is None:
            raise RuntimeError("Seed the tenant before seeding UAT users")
        for suffix, name, role in USERS:
            email = os.getenv(f"SEED_{suffix.upper()}_EMAIL", f"{suffix}@flowgard.com")
            password = os.getenv(f"SEED_{suffix.upper()}_PASSWORD", "Flowgard-UAT-2026!")
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                db.add(User(tenant_id=tenant.id, email=email, full_name=name, role=role, hashed_password=hash_password(password), must_reset_password=False))
            else:
                user.tenant_id, user.full_name, user.role, user.is_active = tenant.id, name, role, True
                user.hashed_password, user.must_reset_password = hash_password(password), False
        db.commit()
        print("Seeded UAT admin, planner, technician, and viewer accounts")

if __name__ == "__main__":
    main()
