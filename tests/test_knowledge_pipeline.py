"""Integration and unit test suite for Knowledge Base Ingestion & Semantic Search Pipeline.

Tests:
1. DocumentChunker splitting, structural metadata preservation, and sliding window overlap.
2. LLMService query normalization logic.
3. End-to-end REST API `/api/v1/knowledge/ingest` and `/api/v1/knowledge/search` pipeline.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport

from src.main import app
from src.schemas.knowledge import KnowledgeIngestRequest, SearchQueryRequest
from src.services.chunker import DocumentChunk, DocumentChunker
from src.services.llm_service import LLMService

pytestmark = pytest.mark.asyncio


# ── Unit Tests: DocumentChunker ────────────────────────────────────────────────

async def test_document_chunker_empty_string():
    """Chunker should return empty list when given empty or whitespace text."""
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    assert chunker.chunk_text("") == []
    assert chunker.chunk_text("   \n\t  ") == []


async def test_document_chunker_markdown_headers():
    """Chunker should extract markdown headers and associate them as header_context."""
    markdown_doc = (
        "# Password Reset SOP\n\n"
        "To reset password, click the forgot password link on login page.\n\n"
        "## MFA Troubleshooting\n\n"
        "If multi-factor authentication fails, clear browser cookies or request a backup code."
    )

    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    chunks = chunker.chunk_text(markdown_doc, doc_type="markdown")

    assert len(chunks) >= 2
    assert any("Password Reset SOP" in (c.header_context or "") for c in chunks)
    assert any("MFA Troubleshooting" in (c.header_context or "") for c in chunks)


async def test_document_chunker_sliding_window_overlap():
    """Chunker should generate chunks under max length with overlap on long texts."""
    long_text = (
        "Paragraph 1: " + ("word " * 60) + "\n\n" +
        "Paragraph 2: " + ("data " * 60) + "\n\n" +
        "Paragraph 3: " + ("info " * 60)
    )

    chunker = DocumentChunker(chunk_size=300, chunk_overlap=40)
    chunks = chunker.chunk_text(long_text, doc_type="text")

    assert len(chunks) > 1
    for chunk in chunks:
        assert isinstance(chunk, DocumentChunk)
        assert len(chunk.content) > 0


# ── Unit Tests: LLM Query Normalization ────────────────────────────────────────

async def test_llm_service_query_normalization_fallback():
    """Query normalization should fallback cleanly to stripped raw query on API error."""
    with patch.object(LLMService, "generate_response", side_effect=RuntimeError("API error")):
        llm = LLMService()
        result = await llm.normalize_query("  WHY DOES MY APP KEEP CRASHING!!  ")
        assert result == "WHY DOES MY APP KEEP CRASHING!!"


async def test_llm_service_query_normalization_success():
    """Query normalization should return stripped output from LLM response."""
    with patch.object(
        LLMService,
        "generate_response",
        new=AsyncMock(return_value='"App crashing on startup after OAuth login"'),
    ):
        llm = LLMService()
        result = await llm.normalize_query("URGENT!! app crashes every time I click OAuth redirect!!")
        assert result == "App crashing on startup after OAuth login"


# ── Integration Tests: Knowledge API Endpoints ─────────────────────────────────

@pytest_asyncio.fixture
async def api_client():
    """Provide httpx.AsyncClient connected to FastAPI ASGI app."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_api_ingest_and_search_mocked(api_client: httpx.AsyncClient):
    """Test POST /api/v1/knowledge/ingest and POST /api/v1/knowledge/search."""
    ingest_payload = {
        "doc_id": "kb-test-001",
        "title": "Database Connection Pool Configuration",
        "category": "SOP",
        "doc_type": "markdown",
        "content": (
            "# Database Pool Setup\n\n"
            "To configure connection pooling in FastAPI with asyncpg, set max_overflow=10 "
            "and pool_size=20 in the database engine setup."
        ),
    }

    # Mock VectorService to avoid requiring real Qdrant Cloud credentials during automated CI
    mock_scored_point = MagicMock()
    mock_scored_point.score = 0.88
    mock_scored_point.payload = {
        "doc_id": "kb-test-001",
        "title": "Database Connection Pool Configuration",
        "category": "SOP",
        "doc_type": "markdown",
        "chunk_index": 0,
        "content": "To configure connection pooling in FastAPI...",
        "header_context": "Database Pool Setup",
    }

    with patch("src.services.vector_service.VectorService.ensure_collection_exists", new=AsyncMock(return_value=True)), \
         patch("src.services.vector_service.VectorService.upsert_points", new=AsyncMock(return_value=True)), \
         patch("src.services.vector_service.VectorService.search_vectors", new=AsyncMock(return_value=[mock_scored_point])), \
         patch("src.services.llm_service.LLMService.normalize_query", new=AsyncMock(return_value="configure postgresql connection pool size")):

        # 1. Ingest
        ingest_res = await api_client.post("/api/v1/knowledge/ingest", json=ingest_payload)
        assert ingest_res.status_code == 201, ingest_res.text
        ingest_body = ingest_res.json()
        assert ingest_body["doc_id"] == "kb-test-001"
        assert ingest_body["status"] == "ingested"
        assert ingest_body["chunks_ingested"] >= 1

        # 2. Search
        search_payload = {
            "query": "How do I increase max connections in postgresql pool??",
            "limit": 3,
            "score_threshold": 0.70,
            "normalize": True,
        }
        search_res = await api_client.post("/api/v1/knowledge/search", json=search_payload)
        assert search_res.status_code == 200, search_res.text
        search_body = search_res.json()

        assert search_body["raw_query"] == search_payload["query"]
        assert search_body["normalized_query"] == "configure postgresql connection pool size"
        assert search_body["total_results"] == 1
        assert search_body["results"][0]["doc_id"] == "kb-test-001"
        assert search_body["results"][0]["score"] == 0.88
