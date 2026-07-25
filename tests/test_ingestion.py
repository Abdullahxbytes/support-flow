"""SupportFlow — Async Integration Test Suite for /api/v1/tickets.

Strategy
--------
* Runtime database: SQLite in-memory via aiosqlite (no external PostgreSQL needed).
* Dependency override: FastAPI's ``get_db`` is replaced by a test-scoped session
  that talks to the ephemeral SQLite DB, keeping every test run hermetically isolated.
* Transport: ``httpx.AsyncClient`` with ``ASGITransport`` so the full ASGI stack
  (middleware, lifespan, routers, dependency injection) is exercised end-to-end.
* Async framework: pytest-asyncio with ``asyncio_mode = "auto"`` declared via the
  module-level ``pytestmark``.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.main import app
from src.core.database import Base, get_db

# ── Test Database Configuration ───────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# ── Module-Level asyncio Mode ─────────────────────────────────────────────────

pytestmark = pytest.mark.asyncio


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="module")
async def test_engine():
    """Create an async in-memory SQLite engine and build all ORM tables once
    per test module.  The engine is disposed after all tests in the module run.
    """
    # Import models so that their tables are registered on Base.metadata
    import src.models.ticket  # noqa: F401

    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def test_session_factory(test_engine):
    """Return a module-scoped async session factory bound to the test engine."""
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture(scope="module")
async def async_client(test_session_factory):
    """Provide a fully-wired ``httpx.AsyncClient`` with the ASGI app and the
    ``get_db`` dependency overridden to use the test SQLite session factory.
    The override is scoped to this fixture's lifetime.
    """

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

    # Restore original dependencies after the test module completes
    app.dependency_overrides.clear()


# ── Shared Payload ────────────────────────────────────────────────────────────

VALID_TICKET_PAYLOAD: dict = {
    "title": "Login page throws 500 on OAuth redirect",
    "description": (
        "After clicking the Google OAuth button the user is redirected to /callback "
        "which returns HTTP 500.  Reproducible on Chrome 126 and Firefox 128."
    ),
    "customer_email": "alice@acme.io",
    "priority": "HIGH",
}

# Module-level holder so tests can share the created ticket ID without
# relying on execution order assumptions beyond what pytest guarantees.
_created_ticket_id: int | None = None


# ── Test Cases ────────────────────────────────────────────────────────────────


async def test_create_ticket_success(async_client: httpx.AsyncClient) -> None:
    """POST /api/v1/tickets — expect 201 CREATED and a well-formed response body."""
    global _created_ticket_id

    response = await async_client.post("/api/v1/tickets/", json=VALID_TICKET_PAYLOAD)

    assert response.status_code == 201, response.text

    body = response.json()
    assert body["id"] is not None
    assert isinstance(body["id"], int)
    assert body["title"] == VALID_TICKET_PAYLOAD["title"]
    assert body["customer_email"] == VALID_TICKET_PAYLOAD["customer_email"]
    assert body["priority"] == "HIGH"
    assert body["status"] == "OPEN"
    assert body["execution_track"] == "UNASSIGNED"
    assert "created_at" in body
    assert "updated_at" in body

    _created_ticket_id = body["id"]


async def test_create_ticket_validation_error(async_client: httpx.AsyncClient) -> None:
    """POST /api/v1/tickets with a missing required field — expect 422 UNPROCESSABLE ENTITY."""
    incomplete_payload = {
        # "title" intentionally omitted — required field
        "description": "Missing title should trigger validation error.",
        "customer_email": "bob@example.com",
    }

    response = await async_client.post("/api/v1/tickets/", json=incomplete_payload)

    assert response.status_code == 422, response.text

    body = response.json()
    assert "detail" in body
    # Pydantic v2 returns a list of error objects
    assert isinstance(body["detail"], list)
    field_names = [err["loc"][-1] for err in body["detail"]]
    assert "title" in field_names


async def test_get_ticket_by_id(async_client: httpx.AsyncClient) -> None:
    """GET /api/v1/tickets/{id} — expect 200 OK for the previously created ticket."""
    assert _created_ticket_id is not None, "Depends on test_create_ticket_success running first"

    response = await async_client.get(f"/api/v1/tickets/{_created_ticket_id}")

    assert response.status_code == 200, response.text

    body = response.json()
    assert body["id"] == _created_ticket_id
    assert body["title"] == VALID_TICKET_PAYLOAD["title"]
    assert body["customer_email"] == VALID_TICKET_PAYLOAD["customer_email"]


async def test_get_ticket_not_found(async_client: httpx.AsyncClient) -> None:
    """GET /api/v1/tickets/99999 — expect 404 NOT FOUND for a non-existent ticket."""
    response = await async_client.get("/api/v1/tickets/99999")

    assert response.status_code == 404, response.text

    body = response.json()
    assert "detail" in body
    assert body["detail"] == "Ticket not found"


async def test_update_ticket_state_transition(async_client: httpx.AsyncClient) -> None:
    """PATCH /api/v1/tickets/{id} — transition status → IN_PROGRESS, track → AUTOPILOT.

    Asserts 200 OK and that the mutated fields are reflected in the response.
    """
    assert _created_ticket_id is not None, "Depends on test_create_ticket_success running first"

    patch_payload = {
        "status": "IN_PROGRESS",
        "execution_track": "AUTOPILOT",
    }

    response = await async_client.patch(
        f"/api/v1/tickets/{_created_ticket_id}", json=patch_payload
    )

    assert response.status_code == 200, response.text

    body = response.json()
    assert body["id"] == _created_ticket_id
    assert body["status"] == "IN_PROGRESS"
    assert body["execution_track"] == "AUTOPILOT"
    # Unchanged fields must remain intact
    assert body["title"] == VALID_TICKET_PAYLOAD["title"]
    assert body["customer_email"] == VALID_TICKET_PAYLOAD["customer_email"]


async def test_list_tickets_pagination(async_client: httpx.AsyncClient) -> None:
    """GET /api/v1/tickets — expect 200 OK and a non-empty list with correct structure."""
    response = await async_client.get("/api/v1/tickets/", params={"skip": 0, "limit": 10})

    assert response.status_code == 200, response.text

    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1  # At least the ticket created in test_create_ticket_success

    first = body[0]
    for field in ("id", "title", "description", "customer_email", "status", "priority",
                  "execution_track", "created_at", "updated_at"):
        assert field in first, f"Expected field '{field}' missing from ticket response"


async def test_delete_ticket(async_client: httpx.AsyncClient) -> None:
    """DELETE /api/v1/tickets/{id} — expect 204 NO CONTENT and subsequent 404 on re-fetch."""
    assert _created_ticket_id is not None, "Depends on test_create_ticket_success running first"

    # Delete the ticket
    delete_response = await async_client.delete(f"/api/v1/tickets/{_created_ticket_id}")
    assert delete_response.status_code == 204, delete_response.text

    # Confirm the resource is gone
    get_response = await async_client.get(f"/api/v1/tickets/{_created_ticket_id}")
    assert get_response.status_code == 404, (
        f"Expected 404 after deletion but got {get_response.status_code}"
    )
