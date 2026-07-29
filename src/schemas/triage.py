"""Pydantic v2 schemas for Autopilot decision engine and ticket triage results."""

from typing import Optional
from pydantic import BaseModel, Field

from src.models.ticket import ExecutionTrack, TicketPriority
from src.schemas.ticket import TicketResponse


class AutopilotDecisionSchema(BaseModel):
    """Structured decision output emitted by Groq LLM Autopilot Engine."""

    suggested_response: str = Field(
        ...,
        description="Drafted resolution or co-pilot response for the customer.",
    )
    category: str = Field(
        ...,
        description="Extracted functional issue category (e.g., Authentication, Billing, Infrastructure).",
    )
    recommended_priority: TicketPriority = Field(
        default=TicketPriority.MEDIUM,
        description="Assessed ticket priority (LOW, MEDIUM, HIGH, URGENT).",
    )
    execution_track: ExecutionTrack = Field(
        ...,
        description="Target execution track (AUTOMATED or HUMAN_REVIEW).",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Match certainty confidence score between 0.00 and 1.00.",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Brief architectural rationale behind the triage routing.",
    )


class TriageResultResponse(BaseModel):
    """Response payload returned following ticket triage execution."""

    ticket: TicketResponse
    decision: AutopilotDecisionSchema
    normalized_query: Optional[str] = None
    chunks_retrieved: int = 0
    message: str = "Ticket triage completed successfully."
