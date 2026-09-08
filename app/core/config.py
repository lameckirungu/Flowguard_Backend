"""Single source of truth for all environment/configuration values.

Every setting the app needs is declared here and nowhere else. No module
outside this file should call `os.environ` / `os.getenv` directly — import
`settings` from here instead. This keeps configuration auditable in one
place and makes it trivial to see the full surface of external inputs the
app depends on.
"""
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "flowgard"
    environment: str = "development"
    debug: bool = False

    # app/core/db.py builds the single engine/session factory from this value.
    # migrations/env.py imports `settings` and reuses it too — never a second
    # hardcoded connection string.
    database_url: str

    # Used only by tests/conftest.py, kept separate from database_url so the
    # test suite never touches real data.
    test_database_url: str | None = None

    # JWT auth (app/core/auth.py)
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7
    # Short-lived token handed out at login when a user still has a
    # first-time password to change — accepted only by the reset-password
    # route, never by a normal protected endpoint.
    jwt_reset_token_expire_minutes: int = 30

    # Platform-admin bootstrap (scripts/seed_platform_admin.py). The seeded
    # account is the only user not created through an onboarding invite, so
    # its credentials live here rather than being emailed.
    platform_admin_email: str = "platform.admin@flow.com"
    platform_admin_password: str = "Admin@123"
    platform_admin_full_name: str = "Platform Administrator"

    # Outbound SMTP (app/core/email.py) — used only to deliver onboarding
    # credentials for new tenants/users. Leave smtp_host empty to disable
    # sending (onboarding routes will then 503).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@flowgard.local"
    smtp_use_tls: bool = True

    # NoDecode: read as a plain string from .env (comma-separated) instead
    # of pydantic-settings' default JSON decoding for list-typed fields —
    # the `_split_csv` validator below turns it into a list.
    cors_allow_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # ETL (app/etl/)
    weather_api_base_url: str = "https://api.open-meteo.com/v1"
    simulator_interval_seconds: int = 5
    data_mode: str = "demo_snapshot"
    telemetry_freshness_seconds: int = 900

    @property
    def smtp_from_email(self) -> str:
        """Backward-compatible name used by the operations email actions."""
        return self.smtp_from

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        value = str(value)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        return value

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.environment.lower() in {"production", "staging"}:
            if len(self.jwt_secret_key) < 32 or self.jwt_secret_key in {"dev-secret-change-me", "change-me"}:
                raise ValueError("JWT_SECRET_KEY must be a unique value of at least 32 characters outside development")
            if any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_allow_origins):
                raise ValueError("CORS_ALLOW_ORIGINS cannot contain local development origins outside development")
            if self.debug:
                raise ValueError("DEBUG must be disabled outside development")
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Use `settings` below for normal imports;
    this exists mainly so tests can call `get_settings.cache_clear()`.
    """
    return Settings()


settings = get_settings()
