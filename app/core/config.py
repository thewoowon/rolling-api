from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _to_sync_url(url: str) -> str:
    """Convert any postgres:// or postgresql:// URL to postgresql+psycopg://."""
    if not url:
        return url
    if "+" in url.split("://", 1)[0]:
        return url
    return url.replace("postgres://", "postgresql+psycopg://", 1).replace(
        "postgresql://", "postgresql+psycopg://", 1
    )


def _to_async_url(url: str) -> str:
    """Convert any postgres:// or postgresql:// URL to postgresql+asyncpg://."""
    if not url:
        return url
    # Strip any existing driver tag first so we can re-apply the async one.
    base = url.split("://", 1)
    scheme = base[0].split("+")[0]  # e.g. "postgresql"
    rest = base[1] if len(base) > 1 else ""
    return f"postgresql+asyncpg://{rest}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_NAME: str = "rolling-api"
    APP_DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = Field(
        default="postgresql+psycopg://rolling:rolling@localhost:5432/rolling"
    )
    DATABASE_URL_ASYNC: str | None = None

    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    PAYMENT_PROVIDER: str = "mock"
    PAYMENT_WEBHOOK_SECRET: str = "replace-me"
    SMS_PROVIDER: str = "mock"

    S3_BUCKET: str = ""
    S3_REGION: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_sync_url(cls, v: str) -> str:
        return _to_sync_url(v)

    @field_validator("DATABASE_URL_ASYNC", mode="before")
    @classmethod
    def normalize_async_url(cls, v: str | None) -> str | None:
        return _to_async_url(v) if v else None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
