"""SupportFlow — FastAPI Application Entry Point.

Uses an async lifespan context manager to handle startup/shutdown
lifecycle events (database pools, Redis connections, etc.).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.v1.router import api_router
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

    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    print("[SupportFlow] Shutting down gracefully...")


app = FastAPI(
    title="SupportFlow API",
    description="Autonomous cloud-hybrid B2B customer support triage platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Lightweight liveness probe for container orchestration."""
    return {"status": "ok"}
