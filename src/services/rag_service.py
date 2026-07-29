"""RAG Context Assembler Service.

Retrieves relevant knowledge base chunks from Qdrant Cloud, normalizes
customer support queries, and assembles structured context blocks for
the Groq LLM Autopilot Decision Engine.
"""

import logging
from typing import Optional

from src.schemas.knowledge import SearchResultItem, SearchResultResponse
from src.services.ingestion_service import IngestionService
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class RAGService:
    """Service encapsulating Retrieval-Augmented Generation (RAG) context assembly."""

    def __init__(
        self,
        ingestion_service: Optional[IngestionService] = None,
        llm_service: Optional[LLMService] = None,
    ) -> None:
        """Initialize RAG service dependencies."""
        self.ingestion_service = ingestion_service or IngestionService()
        self.llm_service = llm_service or LLMService()

    async def assemble_context(
        self,
        ticket_text: str,
        score_threshold: float = 0.70,
        top_k: int = 5,
    ) -> dict:
        """Normalize query, query Qdrant for semantic knowledge, and format LLM context.

        Parameters
        ----------
        ticket_text:
            Raw customer support ticket description or title + description.
        score_threshold:
            Minimum similarity threshold filter (default: 0.70).
        top_k:
            Upper bound on knowledge chunks to retrieve (default: 5).

        Returns
        -------
        dict
            Dictionary containing 'prompt_context', 'normalized_query',
            'retrieved_chunks', and 'has_relevant_knowledge'.
        """
        # 1. Normalize customer query via LLMService
        normalized_query = ticket_text.strip()
        try:
            normalized_query = await self.llm_service.normalize_query(ticket_text)
        except Exception as exc:
            logger.warning("[RAGService] Query normalization fallback: %s", exc)

        # 2. Retrieve vector search matches from Qdrant Cloud
        retrieved_chunks: list[SearchResultItem] = []
        try:
            search_response: SearchResultResponse = (
                await self.ingestion_service.search_knowledge_base(
                    raw_query=ticket_text,
                    limit=top_k,
                    score_threshold=score_threshold,
                    normalize=False,  # Already normalized above
                )
            )
            retrieved_chunks = search_response.results
        except Exception as exc:
            logger.error("[RAGService] Qdrant retrieval error: %s", exc)

        has_relevant_knowledge = len(retrieved_chunks) > 0

        # 3. Formulate structured prompt context block
        knowledge_block_lines = []
        if has_relevant_knowledge:
            for idx, chunk in enumerate(retrieved_chunks, start=1):
                header = f" [{chunk.header_context}]" if chunk.header_context else ""
                knowledge_block_lines.append(
                    f"--- Chunk #{idx} (Doc: {chunk.doc_id} | Title: {chunk.title}{header} | Similarity: {chunk.score:.2f}) ---\n"
                    f"{chunk.content}\n"
                )
            knowledge_block = "\n".join(knowledge_block_lines)
        else:
            knowledge_block = "NO RELEVANT KNOWLEDGE BASE ARTICLES FOUND."

        prompt_context = (
            f"=== CUSTOMER SUPPORT TICKET CONTEXT ===\n"
            f"RAW TICKET DESCRIPTION:\n{ticket_text}\n\n"
            f"NORMALIZED TECHNICAL INTENT:\n{normalized_query}\n\n"
            f"=== RETRIEVED KNOWLEDGE BASE CONTEXT ===\n"
            f"{knowledge_block}\n"
            f"========================================"
        )

        return {
            "prompt_context": prompt_context,
            "normalized_query": normalized_query,
            "retrieved_chunks": retrieved_chunks,
            "has_relevant_knowledge": has_relevant_knowledge,
        }
