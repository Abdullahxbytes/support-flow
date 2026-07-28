"""Knowledge ingestion and semantic search service pipeline.

Orchestrates document chunking, embedding generation using FastEmbed (384-dim),
vector payload formatting, Qdrant Cloud indexing, and semantic similarity retrieval.
"""

import logging
import uuid
from typing import Optional

from fastembed import TextEmbedding
from qdrant_client import models

from src.schemas.knowledge import (
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    SearchResultItem,
    SearchResultResponse,
)
from src.services.chunker import DocumentChunker
from src.services.llm_service import LLMService
from src.services.vector_service import VectorService

logger = logging.getLogger(__name__)

# Singleton lazy-loaded FastEmbed model instance (384-dim)
_embedding_model: Optional[TextEmbedding] = None


def get_embedding_model() -> TextEmbedding:
    """Return singleton FastEmbed model instance producing 384-dim embeddings."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("[IngestionService] Loading FastEmbed model BAAI/bge-small-en-v1.5...")
        _embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _embedding_model


class IngestionService:
    """Service orchestrating document ingestion and semantic search."""

    DEFAULT_COLLECTION = "knowledge_base"

    def __init__(
        self,
        vector_service: Optional[VectorService] = None,
        llm_service: Optional[LLMService] = None,
    ) -> None:
        """Initialize pipeline with vector and LLM service dependencies."""
        self.vector_service = vector_service or VectorService()
        self.llm_service = llm_service or LLMService()
        self.chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)

    # ── Ingestion Pipeline ───────────────────────────────────────────

    async def ingest_document(
        self,
        payload: KnowledgeIngestRequest,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> KnowledgeIngestResponse:
        """Chunk a document, generate 384-dim embeddings, and upsert points to Qdrant.

        Parameters
        ----------
        payload:
            Validated ``KnowledgeIngestRequest`` containing document details.
        collection_name:
            Target Qdrant collection name (defaults to 'knowledge_base').

        Returns
        -------
        KnowledgeIngestResponse
            Ingestion summary with count of indexed vector chunks.
        """
        # Ensure collection exists in Qdrant Cloud
        await self.vector_service.ensure_collection_exists(
            collection_name=collection_name, vector_size=384
        )

        # 1. Chunk document
        chunks = self.chunker.chunk_text(
            text=payload.content, doc_type=payload.doc_type
        )
        if not chunks:
            logger.warning("[IngestionService] Document '%s' yielded 0 chunks.", payload.doc_id)
            return KnowledgeIngestResponse(
                doc_id=payload.doc_id,
                status="skipped",
                chunks_ingested=0,
                collection_name=collection_name,
                message="Document content yielded no processable chunks.",
            )

        # 2. Generate embeddings per chunk
        chunk_texts = [c.content for c in chunks]
        embedder = get_embedding_model()
        embeddings = list(embedder.embed(chunk_texts))

        # 3. Build Qdrant PointStruct list with rich metadata payloads
        points: list[models.PointStruct] = []
        for chunk, embedding in zip(chunks, embeddings):
            # Deterministic UUID per chunk for idempotency
            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"{payload.doc_id}_chunk_{chunk.chunk_index}",
                )
            )

            payload_data = {
                "doc_id": payload.doc_id,
                "title": payload.title,
                "category": payload.category,
                "doc_type": payload.doc_type,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "header_context": chunk.header_context,
            }

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=embedding.tolist(),
                    payload=payload_data,
                )
            )

        # 4. Asynchronously upsert to Qdrant Cloud
        await self.vector_service.upsert_points(
            collection_name=collection_name, points=points
        )

        logger.info(
            "[IngestionService] Ingested doc_id='%s' (%d chunks) into '%s'.",
            payload.doc_id,
            len(points),
            collection_name,
        )

        return KnowledgeIngestResponse(
            doc_id=payload.doc_id,
            status="ingested",
            chunks_ingested=len(points),
            collection_name=collection_name,
            message=f"Successfully indexed {len(points)} chunks into '{collection_name}'.",
        )

    # ── Semantic Search Pipeline ─────────────────────────────────────

    async def search_knowledge_base(
        self,
        raw_query: str,
        limit: int = 5,
        score_threshold: float = 0.70,
        normalize: bool = True,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> SearchResultResponse:
        """Perform semantic similarity search against indexed knowledge base chunks.

        Optionally normalizes customer query via LLM before embedding and querying Qdrant.

        Parameters
        ----------
        raw_query:
            Customer support ticket text or input question.
        limit:
            Top K vector matches to return.
        score_threshold:
            Minimum similarity threshold filter (0.0 to 1.0).
        normalize:
            If True, run query through Groq LLM query normalizer first.
        collection_name:
            Target Qdrant collection.

        Returns
        -------
        SearchResultResponse
            Matching knowledge chunks sorted by similarity score.
        """
        normalized_query: Optional[str] = None
        search_text = raw_query

        if normalize:
            try:
                normalized_query = await self.llm_service.normalize_query(raw_query)
                search_text = normalized_query
            except Exception as exc:
                logger.warning(
                    "[IngestionService] Query normalization failed, using raw query: %s", exc
                )

        # Generate query vector embedding
        embedder = get_embedding_model()
        query_vector = list(embedder.embed([search_text]))[0].tolist()

        # Query Qdrant Cloud
        scored_points = await self.vector_service.search_vectors(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
        )

        # Map Qdrant points to response schema items
        results: list[SearchResultItem] = []
        for pt in scored_points:
            p = pt.payload or {}
            results.append(
                SearchResultItem(
                    doc_id=str(p.get("doc_id", "")),
                    title=str(p.get("title", "")),
                    category=str(p.get("category", "")),
                    doc_type=str(p.get("doc_type", "")),
                    chunk_index=int(p.get("chunk_index", 0)),
                    content=str(p.get("content", "")),
                    score=round(float(pt.score), 4),
                    header_context=p.get("header_context"),
                )
            )

        return SearchResultResponse(
            raw_query=raw_query,
            normalized_query=normalized_query,
            total_results=len(results),
            results=results,
        )
