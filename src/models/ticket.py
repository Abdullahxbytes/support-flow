"""SQLAlchemy 2.0 database model for SupportFlow tickets."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class TicketStatus(str, PyEnum):
    """Lifecycle status of a support ticket."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    ESCALATED = "ESCALATED"


class TicketPriority(str, PyEnum):
    """Priority level of a support ticket."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ExecutionTrack(str, PyEnum):
    """Hybrid Autopilot execution routing track."""

    AUTOPILOT = "AUTOPILOT"
    AUTOMATED = "AUTOMATED"
    COPILOT = "COPILOT"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    UNASSIGNED = "UNASSIGNED"


class Ticket(Base):
    """Database model representing a customer support ticket."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus), default=TicketStatus.OPEN, nullable=False
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority), default=TicketPriority.MEDIUM, nullable=False
    )
    execution_track: Mapped[ExecutionTrack] = mapped_column(
        Enum(ExecutionTrack), default=ExecutionTrack.UNASSIGNED, nullable=False
    )

    ai_draft_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    rag_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
