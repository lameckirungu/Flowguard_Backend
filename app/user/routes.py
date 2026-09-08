"""User routes: login, first-login password reset, and tenant-scoped user
onboarding/management. Thin: translate HTTP <-> services."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.auth import create_access_token, create_reset_token, decode_reset_token, require_role
from app.core.db import get_db
from app.core.email import EmailNotConfiguredError
from app.core.tenancy import get_current_tenant_id
from app.user import services
from app.user.schemas import (
    LoginResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserCreate,
    UserRead,
    UserUpdate,
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _access_token_for(user) -> str:
    return create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, email=user.email, role=user.role.value
    )


@router.post("/login", response_model=LoginResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> LoginResponse:
    user = services.authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.must_reset_password:
        # No access token until the first-time password is changed.
        return LoginResponse(reset_required=True, reset_token=create_reset_token(user.id))
    return LoginResponse(access_token=_access_token_for(user))


@router.post("/reset-password", response_model=TokenResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user_id = decode_reset_token(payload.reset_token)
    user = services.reset_password(db, user_id, payload.new_password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return TokenResponse(access_token=_access_token_for(user))


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_role("admin")),
) -> UserRead:
    try:
        return services.onboard_user(db, tenant_id, payload)
    except EmailNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User created but the invite email could not be sent: SMTP is not configured",
        ) from exc


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> list[UserRead]:
    return services.list_users(db, tenant_id)


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> UserRead:
    user = services.get_user(db, tenant_id, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _=Depends(require_role("admin")),
) -> UserRead:
    user = services.update_user(db, tenant_id, user_id, payload)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
