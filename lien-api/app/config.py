"""Application configuration.

All settings are environment-driven so the same image runs in dev and prod.
Local dev defaults to SQLite (zero infra). Production points DATABASE_URL at
Postgres (e.g. postgresql+asyncpg://user:pass@host/db).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "lien-api"
    environment: str = Field(default="development")

    # SQLite for local dev; override with a Postgres DSN in production.
    database_url: str = Field(default="sqlite+aiosqlite:///./lien_api.db")

    # Comma-separated API keys accepted by the service. Replace in production
    # with a real key store / OAuth2 introspection.
    api_keys: str = Field(default="dev-key-123")

    # Simple in-process rate limit (requests per window per key). For multi-node
    # deployments, back this with Redis instead (see CLAUDE.md).
    rate_limit_requests: int = Field(default=120)
    rate_limit_window_seconds: int = Field(default=60)

    # Hard cap on page size to prevent resource-exhaustion via pagination.
    max_page_size: int = Field(default=100)

    cors_allow_origins: str = Field(default="*")

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
