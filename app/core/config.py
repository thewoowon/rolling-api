from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _normalize_pg_url(url: str, *, async_driver: bool) -> str:
    """Railway / Heroku-style env compatibility.

    They expose `postgres://` and `postgresql://` URLs without a driver tag,
    but SQLAlchemy needs an explicit driver:
      - sync  → `postgresql+psycopg://...`
      - async → `postgresql+asyncpg://...`
    If the URL already specifies a driver (`postgresql+psycopg`, etc.), it's
    returned unchanged.
    """
    if not url:
        return url
    if "+" in url.split("://", 1)[0]:
        return url  # caller-specified driver
    if url.startswith("postgres://"):
        scheme = "postgresql+asyncpg://" if async_driver else "postgresql+psycopg://"
        return url.replace("postgres://", scheme, 1)
    if url.startswith("postgresql://"):
        scheme = "postgresql+asyncpg://" if async_driver else "postgresql+psycopg://"
        return url.replace("postgresql://", scheme, 1)
    return url


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
    # If unset, derived from DATABASE_URL with asyncpg driver.
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

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def _normalize_urls(self) -> "Settings":
        # 1) Always normalize the sync URL to the psycopg driver.
        self.DATABASE_URL = _normalize_pg_url(self.DATABASE_URL, async_driver=False)
        # 2) If async URL not provided, derive it from sync URL with asyncpg driver.
        if not self.DATABASE_URL_ASYNC:
            self.DATABASE_URL_ASYNC = _normalize_pg_url(
                self.DATABASE_URL.replace("+psycopg", ""), async_driver=True
            )
        else:
            self.DATABASE_URL_ASYNC = _normalize_pg_url(
                self.DATABASE_URL_ASYNC, async_driver=True
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
