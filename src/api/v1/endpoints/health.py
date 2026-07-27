"""AI subsystem health and connectivity diagnostic endpoints.

Provides a ``/health/ai`` route that concurrently verifies live API
connectivity with both the Groq LLM service and Qdrant Cloud vector
database — without blocking application startup.
"""

import asyncio
import logging
import time

from fastapi import APIRouter

from src.services.llm_service import LLMService
from src.services.vector_service import VectorService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health/ai", tags=["System"])
async def ai_health_check() -> dict:
    """Verify live connectivity with Groq and Qdrant Cloud.

    Performs parallel, non-blocking pings to both AI backends and
    returns per-service status along with round-trip latency.

    Returns
    -------
    dict
        ``overall``: ``"healthy"`` if **all** services respond,
        ``"degraded"`` if at least one fails.
        Per-service entries include ``status`` and ``latency_ms``.
    """
    results: dict = {}

    # ── Groq LLM Ping ───────────────────────────────────────────────
    async def _ping_groq() -> dict:
        try:
            llm = LLMService()
            start = time.perf_counter()
            ok = await llm.ping()
            latency = round((time.perf_counter() - start) * 1000, 2)
            return {
                "status": "connected" if ok else "unreachable",
                "latency_ms": latency,
            }
        except Exception as exc:
            logger.warning("[HealthCheck] Groq ping error: %s", exc)
            return {"status": "error", "detail": str(exc)}

    # ── Qdrant Cloud Ping ────────────────────────────────────────────
    async def _ping_qdrant() -> dict:
        try:
            vector = VectorService()
            start = time.perf_counter()
            ok = await vector.ping_connection()
            latency = round((time.perf_counter() - start) * 1000, 2)
            result = {
                "status": "connected" if ok else "unreachable",
                "latency_ms": latency,
            }
            await vector.close()
            return result
        except Exception as exc:
            logger.warning("[HealthCheck] Qdrant ping error: %s", exc)
            return {"status": "error", "detail": str(exc)}

    groq_result, qdrant_result = await asyncio.gather(
        _ping_groq(), _ping_qdrant()
    )

    results["groq_llm"] = groq_result
    results["qdrant_vector_db"] = qdrant_result

    all_connected = all(
        svc.get("status") == "connected" for svc in results.values()
    )
    results["overall"] = "healthy" if all_connected else "degraded"

    return results
