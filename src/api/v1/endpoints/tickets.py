"""FastAPI route handlers for customer support ticket operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.schemas.ticket import TicketCreate, TicketResponse, TicketUpdate
from src.services.ticket import TicketService

router = APIRouter()


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    ticket_in: TicketCreate,
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """Create a new customer support ticket."""
    return await TicketService.create_ticket(db, ticket_in)


@router.get("/", response_model=list[TicketResponse], status_code=status.HTTP_200_OK)
async def get_tickets(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[TicketResponse]:
    """Retrieve a paginated list of support tickets."""
    return await TicketService.get_tickets(db, skip=skip, limit=limit)


@router.get("/{ticket_id}", response_model=TicketResponse, status_code=status.HTTP_200_OK)
async def get_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """Fetch a specific support ticket by ID."""
    ticket = await TicketService.get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
        )
    return ticket


@router.patch("/{ticket_id}", response_model=TicketResponse, status_code=status.HTTP_200_OK)
async def update_ticket(
    ticket_id: int,
    ticket_in: TicketUpdate,
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """Update attributes of an existing support ticket."""
    ticket = await TicketService.get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
        )
    return await TicketService.update_ticket(db, ticket, ticket_in)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a support ticket by ID."""
    success = await TicketService.delete_ticket(db, ticket_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
        )
