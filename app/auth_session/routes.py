from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth_session import services
from app.auth_session.schemas import (
    LoginRequest,
    LogoutResponse,
    RefreshRequest,
    SessionResponse,
    SessionUser,
)
from app.core.auth import CurrentUser, get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.permissions import ROLE_PERMISSIONS
from app.user.schemas import UserRead

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _response(access: str, refresh: str, user) -> SessionResponse:
    return SessionResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=SessionUser(
            **UserRead.model_validate(user).model_dump(),
            permissions=sorted(
                permission.value for permission in ROLE_PERMISSIONS[user.role.value]
            ),
        ),
    )


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> SessionResponse:
    try:
        return _response(*services.login(db, payload.email, payload.password))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/refresh", response_model=SessionResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> SessionResponse:
    try:
        return _response(*services.rotate(db, payload.refresh_token))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/logout", response_model=LogoutResponse)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> LogoutResponse:
    return LogoutResponse(revoked=services.revoke(db, payload.refresh_token))


@router.get("/me", response_model=SessionUser)
def me(
    current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> SessionUser:
    user = services.user_by_id(db, current.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive")
    return SessionUser(
        **UserRead.model_validate(user).model_dump(),
        permissions=sorted(permission.value for permission in ROLE_PERMISSIONS[user.role.value]),
    )
