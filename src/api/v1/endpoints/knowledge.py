"""FastAPI route handlers for Knowledge Base ingestion and semantic search operations."""

import logging
from fastapi import APIRouter, HTTPException, Request, status

from src.schemas.knowledge import (
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    SearchQueryRequest,
    SearchResultResponse,
)
from src.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/ingest",
    response_model=KnowledgeIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a knowledge base document",
    description=(
        "Splits document into semantic chunks, generates 384-dim embeddings, "
        "and asynchronously indexes vectors into Qdrant Cloud."
    ),
)
async def ingest_knowledge_document(
    payload: KnowledgeIngestRequest,
    request: Request,
) -> KnowledgeIngestResponse:
    """Ingest a knowledge base document into Qdrant vector database."""
    try:
        # Retrieve vector & llm services from app state if available
        vector_svc = getattr(request.app.state, "vector_service", None)
        llm_svc = getattr(request.app.state, "llm_service", None)

        pipeline = IngestionService(
            vector_service=vector_svc, llm_service=llm_svc
        )
        return await pipeline.ingest_document(payload=payload)
    except Exception as exc:
        logger.error("[KnowledgeEndpoint] Ingestion error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Knowledge document ingestion failed: {str(exc)}",
        ) from exc


@router.post(
    "/search",
    response_model=SearchResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic vector search",
    description=(
        "Normalizes customer query using Groq LLM, generates query embedding, "
        "and performs similarity search against Qdrant vector knowledge base."
    ),
)
async def search_knowledge_base(
    payload: SearchQueryRequest,
    request: Request,
) -> SearchResultResponse:
    """Perform semantic vector similarity search against knowledge base."""
    try:
        vector_svc = getattr(request.app.state, "vector_service", None)
        llm_svc = getattr(request.app.state, "llm_service", None)

        pipeline = IngestionService(
            vector_service=vector_svc, llm_service=llm_svc
        )
        return await pipeline.search_knowledge_base(
            raw_query=payload.query,
            limit=payload.limit,
            score_threshold=payload.score_threshold,
            normalize=payload.normalize,
        )
    except Exception as exc:
        logger.error("[KnowledgeEndpoint] Search error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic knowledge search failed: {str(exc)}",
        ) from exc
