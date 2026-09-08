from pydantic import BaseModel, EmailStr

from app.user.schemas import UserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class SessionUser(UserRead):
    permissions: list[str]


class SessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: SessionUser


class LogoutResponse(BaseModel):
    revoked: bool
