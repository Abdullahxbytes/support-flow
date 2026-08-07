"""SupportFlow — FastAPI Application Entry Point.

Uses an async lifespan context manager to handle startup/shutdown
lifecycle events (database pools, Redis connections, etc.).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.router import api_router
from src.api.websocket import router as ws_router
from src.core.config import get_settings
from src.core.ws_manager import ConnectionManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    Startup:
        - Validate environment configuration (fail-fast on bad env).
        - Initialize Groq LLM and Qdrant vector clients.
    Shutdown:
        - Gracefully close Qdrant client connection.
    """
    settings = get_settings()
    app.state.settings = settings

    # ── Startup ──────────────────────────────────────────────────────
    print(f"[SupportFlow] Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"[SupportFlow] Debug mode: {settings.DEBUG}")

    # Module 2 — AI service client initialization
    from src.services.llm_service import LLMService
    from src.services.vector_service import VectorService

    app.state.llm_service = LLMService()
    app.state.vector_service = VectorService()
    print("[SupportFlow] Groq LLM and Qdrant vector clients initialized.")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    if hasattr(app.state, "vector_service"):
        await app.state.vector_service.close()
    if hasattr(app.state, "llm_service"):
        await app.state.llm_service.close()
    print("[SupportFlow] Shutting down gracefully...")


tags_metadata = [
    {
        "name": "Tickets",
        "description": "Operations on support tickets, including single and concurrent batch auto-triage.",
    },
    {
        "name": "Knowledge Base",
        "description": "Admin loading and semantic vector search over FAQs, SOPs, and policies.",
    },
    {
        "name": "Analytics",
        "description": "System-wide triage metrics, RAG confidence, and auto-resolution rates.",
    },
    {
        "name": "System",
        "description": "Health checks and connectivity diagnostics for internal microservices.",
    },
]

app = FastAPI(
    title="SupportFlow API",
    description=(
        "Autonomous cloud-hybrid B2B customer support triage platform.\n\n"
        "Leverages async retrieval-augmented generation (RAG) using Qdrant Cloud "
        "and high-performance structured LLM completion using Groq API."
    ),
    version="0.3.0-module3",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global WebSocket connection manager singleton
ws_manager = ConnectionManager()
app.state.ws_manager = ws_manager

app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/ws")


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Lightweight liveness probe for container orchestration."""
    return {"status": "ok"}
