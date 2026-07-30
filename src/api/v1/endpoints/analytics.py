"""FastAPI route handlers for system-wide triage metrics and analytics."""

import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.ticket import ExecutionTrack, Ticket
from src.schemas.analytics import TriageSummaryMetricsResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/triage-summary",
    response_model=TriageSummaryMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get system-wide triage metrics",
    description=(
        "Retrieves aggregate statistics on triaged tickets, including the automated "
        "resolution rate, average RAG confidence score, and category breakdown."
    ),
)
async def get_triage_summary(
    db: AsyncSession = Depends(get_db),
) -> TriageSummaryMetricsResponse:
    """Calculate and return system-wide triage metrics from database."""
    # 1. Fetch all triaged tickets from database
    statement = select(Ticket).where(
        Ticket.execution_track != ExecutionTrack.UNASSIGNED
    )
    result = await db.execute(statement)
    triaged_tickets = list(result.scalars().all())

    total_triaged = len(triaged_tickets)
    if total_triaged == 0:
        return TriageSummaryMetricsResponse(
            total_triaged_count=0,
            automated_resolution_rate=0.0,
            average_rag_confidence=0.0,
            category_breakdown={},
        )

    # 2. Calculate automated resolution rate
    automated_count = sum(
        1
        for t in triaged_tickets
        if t.execution_track in (ExecutionTrack.AUTOMATED, ExecutionTrack.AUTOPILOT)
    )
    resolution_rate = round((automated_count / total_triaged) * 100, 2)

    # 3. Calculate average RAG confidence score
    scores = [
        t.rag_confidence_score
        for t in triaged_tickets
        if t.rag_confidence_score is not None
    ]
    avg_confidence = (
        round(sum(scores) / len(scores), 4) if scores else 0.0
    )

    # 4. Compute category breakdown dynamically based on keywords in title & description
    categories: dict[str, int] = {}
    for ticket in triaged_tickets:
        text = f"{ticket.title} {ticket.description}".lower()
        if any(kw in text for kw in ["password", "login", "oauth", "auth", "mfa"]):
            cat = "Authentication"
        elif any(kw in text for kw in ["billing", "invoice", "payment", "card", "charge"]):
            cat = "Billing"
        elif any(kw in text for kw in ["database", "postgres", "pool", "cluster", "server"]):
            cat = "Infrastructure"
        else:
            cat = "General"

        categories[cat] = categories.get(cat, 0) + 1

    return TriageSummaryMetricsResponse(
        total_triaged_count=total_triaged,
        automated_resolution_rate=resolution_rate,
        average_rag_confidence=avg_confidence,
        category_breakdown=categories,
    )
