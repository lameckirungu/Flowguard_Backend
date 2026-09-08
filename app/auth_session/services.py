import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_session.models import RefreshSession
from app.core.auth import create_access_token
from app.core.config import settings
from app.user.models import User
from app.user.services import authenticate_user


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue(db: Session, user: User) -> tuple[str, str, RefreshSession]:
    refresh_token = secrets.token_urlsafe(48)
    refresh_session = RefreshSession(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=_hash(refresh_token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    db.add(refresh_session)
    db.commit()
    db.refresh(refresh_session)
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role.value,
    )
    return access_token, refresh_token, refresh_session


def login(db: Session, email: str, password: str) -> tuple[str, str, User]:
    user = authenticate_user(db, email, password)
    if user is None:
        raise ValueError("Incorrect email or password")
    access, refresh, _ = _issue(db, user)
    return access, refresh, user


def rotate(db: Session, token: str) -> tuple[str, str, User]:
    now = datetime.now(UTC)
    current = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == _hash(token)))
    if current is None or not current.is_active or current.revoked_at is not None:
        raise ValueError("Invalid refresh token")
    expires_at = current.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        current.is_active = False
        current.revoked_at = now
        db.commit()
        raise ValueError("Refresh token expired")
    user = db.scalar(select(User).where(User.id == current.user_id, User.is_active.is_(True)))
    if user is None:
        raise ValueError("User is inactive")
    current.is_active = False
    current.revoked_at = now
    access, refresh, replacement = _issue(db, user)
    current.replaced_by_id = replacement.id
    db.commit()
    return access, refresh, user


def revoke(db: Session, token: str) -> bool:
    current = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == _hash(token)))
    if current is None or current.revoked_at is not None:
        return False
    current.is_active = False
    current.revoked_at = datetime.now(UTC)
    db.commit()
    return True


def user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
