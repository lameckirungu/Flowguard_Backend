"""Business logic for users.

Two deliberate exceptions to the "every query is tenant-scoped" rule in this
module:

* `authenticate_user` looks a user up by email alone — at login the client
  only has an email + password, not a tenant. Email is globally unique for
  exactly this reason (see app/user/models.py). The tenant_id on the
  returned user is what gets embedded in the JWT.
* `reset_password` looks a user up by id alone — the caller has already
  proven identity by presenting a valid one-shot reset token.

Everything else takes `tenant_id` as an explicit argument as usual.
"""
import secrets
import string
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import email as email_service
from app.core.auth import hash_password, verify_password
from app.user.models import User, UserRole
from app.user.schemas import UserCreate, UserUpdate

_TEMP_PW_ALPHABET = string.ascii_letters + string.digits


def generate_temp_password() -> str:
    """A random first-time password. Guaranteed to contain a lower- and
    upper-case letter, a digit and a symbol so it clears common policies the
    user's real password will also have to meet."""
    core = "".join(secrets.choice(_TEMP_PW_ALPHABET) for _ in range(12))
    return (
        secrets.choice(string.ascii_lowercase)
        + secrets.choice(string.ascii_uppercase)
        + secrets.choice(string.digits)
        + secrets.choice("!@#$%^&*")
        + core
    )


def _send_onboarding_email(*, to: str, full_name: str, temp_password: str, context: str) -> None:
    email_service.send_email(
        to=to,
        subject="Your Flowgard account is ready",
        body=(
            f"Hi {full_name},\n\n"
            f"{context}\n\n"
            f"Sign in with:\n"
            f"  Email:            {to}\n"
            f"  Temporary password: {temp_password}\n\n"
            f"You will be asked to set a new password the first time you sign in.\n"
        ),
    )


def onboard_user(
    db: Session,
    tenant_id: uuid.UUID,
    payload: UserCreate,
    *,
    context: str = "An account has been created for you on Flowgard.",
) -> User:
    """Create a tenant user with a generated first-time password and email it.

    The user is committed even if the email send then fails — the route
    surface converts a send failure into a 503 so the operator can retry the
    invite, but we don't want a flaky SMTP server to roll back a valid user.
    """
    temp_password = generate_temp_password()
    user = User(
        tenant_id=tenant_id,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        hashed_password=hash_password(temp_password),
        must_reset_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _send_onboarding_email(
        to=user.email, full_name=user.full_name, temp_password=temp_password, context=context
    )
    return user


def get_user(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
    return db.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant_id))


def list_users(db: Session, tenant_id: uuid.UUID) -> list[User]:
    return list(db.scalars(select(User).where(User.tenant_id == tenant_id).order_by(User.email)))


def update_user(
    db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, payload: UserUpdate
) -> User | None:
    user = get_user(db, tenant_id, user_id)
    if user is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Global-by-email lookup used only by the login route. See module
    docstring for why this doesn't take tenant_id. Returns the user even when
    `must_reset_password` is set — the route decides what to hand back.
    """
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, user_id: uuid.UUID, new_password: str) -> User | None:
    """Set a new password and clear the first-login flag. Identity is assumed
    already proven by a valid reset token (see app/user/routes.py)."""
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    user.hashed_password = hash_password(new_password)
    user.must_reset_password = False
    db.commit()
    db.refresh(user)
    return user


def get_platform_admin_by_email(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User).where(User.email == email, User.role == UserRole.PLATFORM_ADMIN)
    )
