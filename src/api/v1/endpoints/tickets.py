"""FastAPI route handlers for customer support ticket operations."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.schemas.ticket import TicketCreate, TicketResponse, TicketUpdate
from src.schemas.triage import TriageResultResponse, BatchTriageRequest, BatchTriageResultResponse
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


@router.post("/{ticket_id}/triage", response_model=TriageResultResponse, status_code=status.HTTP_200_OK)
async def triage_ticket(
    ticket_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TriageResultResponse:
    """Trigger Hybrid Autopilot RAG context retrieval and LLM triage on a ticket."""
    from src.services.triage_service import TriageService
    from src.services.rag_service import RAGService
    from src.services.llm_service import LLMService

    # Check if app state services exist, otherwise default instances will be used
    vector_svc = getattr(request.app.state, "vector_service", None)
    llm_svc = getattr(request.app.state, "llm_service", None)

    rag_svc = RAGService(llm_service=llm_svc)
    if vector_svc:
        rag_svc.ingestion_service.vector_service = vector_svc

    triage_svc = TriageService(rag_service=rag_svc, llm_service=llm_svc)

    try:
        return await triage_svc.process_ticket_triage(db=db, ticket_id=ticket_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ticket triage processing failed: {str(exc)}",
        ) from exc


@router.post("/batch-triage", response_model=BatchTriageResultResponse, status_code=status.HTTP_200_OK)
async def batch_triage_tickets(
    payload: BatchTriageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> BatchTriageResultResponse:
    """Trigger concurrent batch triage processing for multiple tickets with rate-limiting."""
    from src.services.batch_triage_service import BatchTriageService
    from src.services.triage_service import TriageService
    from src.services.rag_service import RAGService

    # Check if app state services exist, otherwise default instances will be used
    vector_svc = getattr(request.app.state, "vector_service", None)
    llm_svc = getattr(request.app.state, "llm_service", None)

    rag_svc = RAGService(llm_service=llm_svc)
    if vector_svc:
        rag_svc.ingestion_service.vector_service = vector_svc

    triage_svc = TriageService(rag_service=rag_svc, llm_service=llm_svc)
    session_factory = getattr(request.app.state, "session_factory", None)
    batch_svc = BatchTriageService(triage_service=triage_svc, session_factory=session_factory)

    try:
        # Detect SQLite test databases to serialize queries and prevent write-lock collisions
        is_sqlite = "sqlite" in str(db.bind.url) if db.bind else False
        max_concurrent = 1 if is_sqlite else 5
        return await batch_svc.process_batch_triage(
            db=db, ticket_ids=payload.ticket_ids, max_concurrent=max_concurrent
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch ticket triage failed: {str(exc)}",
        ) from exc

