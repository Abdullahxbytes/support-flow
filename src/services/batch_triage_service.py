"""Batch Triage Service.

Orchestrates concurrent ticket triage using asyncio.Semaphore to enforce concurrency
limiting, preventing rate limit saturation on Groq while processing batches resiliently.
Uses a session factory to ensure each concurrent triage run has a dedicated database session.
"""

import asyncio
import logging
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.schemas.triage import (
    BatchTriageItemResult,
    BatchTriageResultResponse,
    TriageResultResponse,
)
from src.services.triage_service import TriageService

logger = logging.getLogger(__name__)


class BatchTriageService:
    """Service encapsulating batch ticket triage with concurrency controls."""

    def __init__(
        self,
        triage_service: Optional[TriageService] = None,
        session_factory: Optional[Callable[[], AsyncSession]] = None,
    ) -> None:
        """Initialize BatchTriageService with TriageService and session factory."""
        self.triage_service = triage_service or TriageService()
        self.session_factory = session_factory or AsyncSessionLocal

    async def process_batch_triage(
        self,
        db: AsyncSession,
        ticket_ids: list[int],
        max_concurrent: int = 5,
    ) -> BatchTriageResultResponse:
        """Process a list of tickets concurrently with a concurrency limit.

        Parameters
        ----------
        db:
            Async Database Session (unused here as dedicated sessions are spawned).
        ticket_ids:
            List of support ticket IDs to process.
        max_concurrent:
            Maximum concurrent operations.

        Returns
        -------
        BatchTriageResultResponse
            Summary of successful and failed triage operations.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _triage_with_semaphore(t_id: int) -> BatchTriageItemResult:
            async with semaphore:
                async with self.session_factory() as session:
                    try:
                        result: TriageResultResponse = (
                            await self.triage_service.process_ticket_triage(
                                db=session, ticket_id=t_id
                            )
                        )
                        return BatchTriageItemResult(
                            ticket_id=t_id,
                            status="success",
                            triage=result,
                            error_message=None,
                        )
                    except Exception as exc:
                        logger.error(
                            "[BatchTriageService] Failed to process ticket #%d: %s",
                            t_id,
                            exc,
                        )
                        return BatchTriageItemResult(
                            ticket_id=t_id,
                            status="error",
                            triage=None,
                            error_message=str(exc),
                        )

        # Execute concurrent triage processes
        tasks = [_triage_with_semaphore(t_id) for t_id in ticket_ids]
        results = await asyncio.gather(*tasks)

        success_count = sum(1 for r in results if r.status == "success")
        failure_count = len(results) - success_count

        return BatchTriageResultResponse(
            processed_count=len(ticket_ids),
            success_count=success_count,
            failure_count=failure_count,
            results=results,
        )
PostgreSQL_session_factory = AsyncSessionLocal
