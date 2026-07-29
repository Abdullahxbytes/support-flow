"""Async Integration & Unit Test Suite for Hybrid Autopilot Triage Engine.

Tests:
1. High-confidence RAG match -> AUTOMATED execution track, RESOLVED status.
2. Low-confidence or missing KB match -> HUMAN_REVIEW execution track, IN_PROGRESS status.
3. Database persistence verification for modified priority, AI response draft, confidence score, and tracks.
"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.database import Base, get_db
from src.main import app
from src.models.ticket import ExecutionTrack, TicketPriority, TicketStatus
from src.schemas.knowledge import SearchResultItem
from src.schemas.triage import AutopilotDecisionSchema

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
pytestmark = pytest.mark.asyncio


# ── Database Fixtures ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module")
async def test_engine():
    """Create async in-memory SQLite engine for triage testing."""
    import src.models.ticket  # noqa: F401

    engine = create_async_engine(
        TEST_DATABASE_URL, echo=False, future=True, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def test_session_factory(test_engine):
    """Return async session factory."""
    return async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )


@pytest_asyncio.fixture(scope="module")
async def async_client(test_session_factory):
    """Provide httpx.AsyncClient with get_db dependency overridden."""

    async def override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ── Test Cases ────────────────────────────────────────────────────────────────

async def test_triage_high_confidence_automated_resolution(async_client: httpx.AsyncClient):
    """Ticket with high-confidence KB match should be routed to AUTOMATED track and RESOLVED."""
    # 1. Create a support ticket
    create_payload = {
        "title": "Cannot reset password via email link",
        "description": "Clicking forgot password sends email but link expires instantly.",
        "customer_email": "user1@company.com",
        "priority": "MEDIUM",
    }
    create_res = await async_client.post("/api/v1/tickets/", json=create_payload)
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    # Mock RAG context assembly & Groq decision engine
    mock_rag_result = {
        "prompt_context": "=== RETRIEVED KB: Reset Link SOP ===",
        "normalized_query": "password reset email link expiration issue",
        "retrieved_chunks": [
            SearchResultItem(
                doc_id="sop-001",
                title="Password Reset SOP",
                category="SOP",
                doc_type="markdown",
                chunk_index=0,
                content="Clear browser cache and request a new link valid for 15 mins.",
                score=0.92,
            )
        ],
        "has_relevant_knowledge": True,
    }

    mock_decision = AutopilotDecisionSchema(
        suggested_response="Please clear your browser cache and request a new password reset link.",
        category="Authentication",
        recommended_priority=TicketPriority.LOW,
        execution_track=ExecutionTrack.AUTOMATED,
        confidence_score=0.92,
        reasoning="SOP directly matches password link expiration issue.",
    )

    with patch("src.services.rag_service.RAGService.assemble_context", new=AsyncMock(return_value=mock_rag_result)), \
         patch("src.services.llm_service.LLMService.generate_triage_decision", new=AsyncMock(return_value=mock_decision)):

        # 2. Trigger Triage Endpoint POST /api/v1/tickets/{id}/triage
        triage_res = await async_client.post(f"/api/v1/tickets/{ticket_id}/triage")
        assert triage_res.status_code == 200, triage_res.text
        body = triage_res.json()

        assert body["ticket"]["id"] == ticket_id
        assert body["ticket"]["status"] == "RESOLVED"
        assert body["ticket"]["execution_track"] in ("AUTOMATED", "AUTOPILOT")
        assert body["ticket"]["rag_confidence_score"] == 0.92
        assert "clear your browser cache" in body["ticket"]["ai_draft_response"]
        assert body["decision"]["confidence_score"] == 0.92

    # 3. Verify Database Persistence on GET /api/v1/tickets/{id}
    get_res = await async_client.get(f"/api/v1/tickets/{ticket_id}")
    assert get_res.status_code == 200
    db_ticket = get_res.json()
    assert db_ticket["status"] == "RESOLVED"
    assert db_ticket["execution_track"] in ("AUTOMATED", "AUTOPILOT")


async def test_triage_low_confidence_human_review(async_client: httpx.AsyncClient):
    """Ticket with low-confidence match should be routed to HUMAN_REVIEW and IN_PROGRESS."""
    # 1. Create a unknown/complex support ticket
    create_payload = {
        "title": "Quantum DB cluster partition failure during backup",
        "description": "Unknown error code 0x99FF in node cluster synchronization.",
        "customer_email": "devops@enterprise.com",
        "priority": "MEDIUM",
    }
    create_res = await async_client.post("/api/v1/tickets/", json=create_payload)
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    mock_rag_result = {
        "prompt_context": "NO RELEVANT KNOWLEDGE BASE ARTICLES FOUND.",
        "normalized_query": "quantum db cluster partition failure error 0x99FF",
        "retrieved_chunks": [],
        "has_relevant_knowledge": False,
    }

    mock_decision = AutopilotDecisionSchema(
        suggested_response="Drafting initial escalation report for L3 engineering team.",
        category="Database",
        recommended_priority=TicketPriority.HIGH,
        execution_track=ExecutionTrack.HUMAN_REVIEW,
        confidence_score=0.35,
        reasoning="No KB article available for error 0x99FF; requires manual engineering review.",
    )

    with patch("src.services.rag_service.RAGService.assemble_context", new=AsyncMock(return_value=mock_rag_result)), \
         patch("src.services.llm_service.LLMService.generate_triage_decision", new=AsyncMock(return_value=mock_decision)):

        triage_res = await async_client.post(f"/api/v1/tickets/{ticket_id}/triage")
        assert triage_res.status_code == 200, triage_res.text
        body = triage_res.json()

        assert body["ticket"]["id"] == ticket_id
        assert body["ticket"]["status"] == "IN_PROGRESS"
        assert body["ticket"]["execution_track"] in ("HUMAN_REVIEW", "COPILOT")
        assert body["ticket"]["priority"] == "HIGH"
        assert body["ticket"]["rag_confidence_score"] == 0.35

    # Verify Database Persistence
    get_res = await async_client.get(f"/api/v1/tickets/{ticket_id}")
    assert get_res.status_code == 200
    db_ticket = get_res.json()
    assert db_ticket["status"] == "IN_PROGRESS"
    assert db_ticket["execution_track"] in ("HUMAN_REVIEW", "COPILOT")
    assert db_ticket["priority"] == "HIGH"
