"""SupportFlow — FastAPI Application Entry Point.

Uses an async lifespan context manager to handle startup/shutdown
lifecycle events (database pools, Redis connections, etc.).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    Startup:
        - Validate environment configuration (fail-fast on bad env).
        - Future: initialize DB engine, Redis pool, Qdrant client.
    Shutdown:
        - Future: dispose DB engine, close Redis pool.
    """
    settings = get_settings()
    app.state.settings = settings

    # ── Startup ──────────────────────────────────────────────────────
    print(f"[SupportFlow] Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"[SupportFlow] Debug mode: {settings.DEBUG}")
    # TODO (Session 3): Initialize async DB engine via database.py
    # TODO (Session 3): Initialize Redis connection pool

    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    print("[SupportFlow] Shutting down gracefully...")
    # TODO (Session 3): Dispose DB engine
    # TODO (Session 3): Close Redis pool


app = FastAPI(
    title="SupportFlow API",
    description="Autonomous cloud-hybrid B2B customer support triage platform.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Lightweight liveness probe for container orchestration."""
    return {"status": "ok"}
