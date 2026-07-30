"""Pydantic v2 schemas for SupportFlow analytics reporting."""

from pydantic import BaseModel, Field


class TriageSummaryMetricsResponse(BaseModel):
    """Response payload containing system-wide triage and RAG metrics."""

    total_triaged_count: int = Field(
        ...,
        description="Total count of tickets that have been processed through triage.",
    )
    automated_resolution_rate: float = Field(
        ...,
        description="Percentage of triaged tickets routed to AUTOMATED/RESOLVED track (0.0 to 100.0).",
    )
    average_rag_confidence: float = Field(
        ...,
        description="Average semantic search/RAG confidence score across processed tickets (0.0 to 1.0).",
    )
    category_breakdown: dict[str, int] = Field(
        ...,
        description="Distribution count of triaged tickets grouped by AI-assigned categories.",
    )
