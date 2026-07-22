"""Pydantic v2 schemas for Ticket validation and serialization."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.ticket import ExecutionTrack, TicketPriority, TicketStatus


class TicketBase(BaseModel):
    """Shared fields for ticket validation schemas."""

    title: str = Field(..., max_length=255, description="Ticket title or subject")
    description: str = Field(..., description="Detailed description of the customer issue")
    customer_email: str = Field(..., max_length=255, description="Customer contact email address")
    priority: TicketPriority = Field(
        default=TicketPriority.MEDIUM, description="Priority level of the ticket"
    )


class TicketCreate(TicketBase):
    """Payload schema for creating a new support ticket."""

    pass


class TicketUpdate(BaseModel):
    """Payload schema for updating existing ticket attributes (partial updates)."""

    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    execution_track: ExecutionTrack | None = None
    ai_draft_response: str | None = None
    rag_confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)


class TicketResponse(TicketBase):
    """Response schema returned to client applications and management dashboards."""

    id: int
    status: TicketStatus
    execution_track: ExecutionTrack
    ai_draft_response: str | None = None
    rag_confidence_score: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
