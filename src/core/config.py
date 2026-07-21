"""Centralized application configuration via pydantic-settings.

All environment variables are validated at startup. Missing or malformed
values will raise immediately rather than failing at runtime deep in
business logic.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """SupportFlow environment configuration.

    Values are loaded from a `.env` file at the project root and can be
    overridden by real environment variables (higher precedence).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────
    APP_NAME: str = "SupportFlow API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ── PostgreSQL ───────────────────────────────────────────────────
    DATABASE_URL: str

    # ── Redis ────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Groq Cloud API ───────────────────────────────────────────────
    GROQ_API_KEY: str

    # ── Qdrant Cloud ─────────────────────────────────────────────────
    QDRANT_URL: str
    QDRANT_API_KEY: str


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the validated settings.

    Using ``lru_cache`` ensures the `.env` file is read exactly once
    per process and the same ``Settings`` instance is reused everywhere.
    """
    return Settings()
