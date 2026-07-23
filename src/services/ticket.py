"""Decoupled asynchronous CRUD service for managing customer support tickets."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ticket import Ticket
from src.schemas.ticket import TicketCreate, TicketUpdate


class TicketService:
    """Service layer encapsulating ticket persistence operations in PostgreSQL."""

    @classmethod
    async def create_ticket(cls, db: AsyncSession, ticket_in: TicketCreate) -> Ticket:
        """Convert Pydantic payload to Ticket ORM model, persist, and return created ticket."""
        db_ticket = Ticket(**ticket_in.model_dump())
        db.add(db_ticket)
        await db.commit()
        await db.refresh(db_ticket)
        return db_ticket

    @classmethod
    async def get_ticket_by_id(cls, db: AsyncSession, ticket_id: int) -> Ticket | None:
        """Retrieve a single ticket by its primary key ID."""
        statement = select(Ticket).where(Ticket.id == ticket_id)
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @classmethod
    async def get_tickets(
        cls, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> list[Ticket]:
        """Fetch a paginated list of tickets sorted by creation timestamp descending."""
        statement = (
            select(Ticket)
            .order_by(Ticket.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(statement)
        return list(result.scalars().all())

    @classmethod
    async def update_ticket(
        cls, db: AsyncSession, ticket: Ticket, ticket_in: TicketUpdate
    ) -> Ticket:
        """Apply non-null field updates dynamically to an existing ticket ORM object."""
        update_data = ticket_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(ticket, field, value)

        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @classmethod
    async def delete_ticket(cls, db: AsyncSession, ticket_id: int) -> bool:
        """Delete a ticket by ID and return boolean status indicating success."""
        ticket = await cls.get_ticket_by_id(db, ticket_id)
        if not ticket:
            return False

        await db.delete(ticket)
        await db.commit()
        return True
