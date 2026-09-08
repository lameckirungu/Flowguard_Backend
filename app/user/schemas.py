"""Pydantic v2 request/response models for the user module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.user.models import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.VIEWER


class UserCreate(UserBase):
    """A tenant admin's invite for a new user. No password: the system
    generates a first-time one and emails it (see services.onboard_user)."""


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    is_active: bool
    must_reset_password: bool
    last_login_at: datetime | None = None


class ResetPasswordRequest(BaseModel):
    """First-login password change. `reset_token` is the one-shot token the
    login route returns when the account still holds its emailed password."""

    reset_token: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """Either a normal login (`access_token` set) or a first login that still
    needs a password change (`reset_required` true, `reset_token` set)."""

    token_type: str = "bearer"
    reset_required: bool = False
    access_token: str | None = None
    reset_token: str | None = None
