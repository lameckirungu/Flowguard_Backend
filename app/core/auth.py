"""Auth dependency: JWT decode -> user -> tenant + role.

This is the only place that issues/decodes tokens or hashes passwords.
`get_current_user` is the dependency every protected route (indirectly, via
app/core/tenancy.py) depends on. It never queries the database itself — the
token payload alone carries id/tenant_id/email/role, keeping this module free
of a dependency on app/user (routes -> services -> models stays one-way).
"""
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings

# tokenUrl points at the user module's login route — see app/user/routes.py.
# This is metadata for OpenAPI docs only; auth.py does not import app.user.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login", auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """The decoded identity attached to a request. `tenant_id` is what
    app/core/tenancy.py hands to every service call.

    `tenant_id` is None for the platform admin, who is not scoped to any
    tenant — see app/user/models.py. Tenant-scoped routes depend on
    app/core/tenancy.get_current_tenant_id, which rejects that case.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    email: str
    role: str


def hash_password(plain_password: str) -> str:
    # bcrypt truncates at 72 bytes silently — reject longer input explicitly
    # rather than hashing a truncated password the user didn't type.
    encoded = plain_password.encode("utf-8")
    if len(encoded) > 72:
        raise ValueError("password must be at most 72 bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("ascii"))
    except ValueError:
        return False


def create_access_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
    email: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": "access",
        "exp": expire,
    }
    # Omitted entirely for the platform admin, who has no tenant.
    if tenant_id is not None:
        payload["tenant_id"] = str(tenant_id)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_reset_token(user_id: uuid.UUID) -> str:
    """One-shot token handed out at login when the user still has a first-time
    password to change. Accepted only by `decode_reset_token` (the
    reset-password route) — its `type` claim keeps it from being replayed as
    an access token."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_reset_token_expire_minutes)
    payload = {"sub": str(user_id), "type": "reset", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def decode_access_token(token: str) -> CurrentUser:
    payload = _decode(token)
    if payload.get("type") == "reset":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password reset required; use the reset-password endpoint",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        tenant_id_raw = payload.get("tenant_id")
        return CurrentUser(
            id=uuid.UUID(payload["sub"]),
            tenant_id=uuid.UUID(tenant_id_raw) if tenant_id_raw else None,
            email=payload["email"],
            role=payload["role"],
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def decode_reset_token(token: str) -> uuid.UUID:
    """Returns the user id embedded in a reset token, or 401 if the token is
    invalid, expired, or not a reset token."""
    payload = _decode(token)
    if payload.get("type") != "reset":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not a password-reset token",
        )
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
        ) from exc


def get_current_user(token: str | None = Depends(oauth2_scheme)) -> CurrentUser:
    """The base identity dependency. No token -> 401, so any route that
    depends on this (directly or via app/core/tenancy.py) cannot be called
    without tenant context.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(token)


def require_role(*allowed_roles: str):
    """Dependency factory for role-gated routes, e.g.:
    `Depends(require_role("admin", "planner"))`.
    """

    def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return _check
