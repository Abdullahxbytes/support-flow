"""Pydantic v2 schemas for knowledge base ingestion and semantic search."""

from typing import Optional
from pydantic import BaseModel, Field


class KnowledgeIngestRequest(BaseModel):
    """Payload schema for ingesting a document into the vector knowledge base."""

    doc_id: str = Field(
        ...,
        description="Unique identifier for the knowledge base document.",
        examples=["kb-faq-001"],
    )
    title: str = Field(
        ...,
        description="Human-readable document title.",
        examples=["Password Reset Procedures SOP"],
    )
    category: str = Field(
        ...,
        description="Functional category (e.g., FAQ, SOP, Policy, Ticket_Log).",
        examples=["SOP"],
    )
    doc_type: str = Field(
        default="markdown",
        description="Document format type (markdown, text, json).",
        examples=["markdown"],
    )
    content: str = Field(
        ...,
        min_length=10,
        description="Full text content of the knowledge base document.",
    )


class KnowledgeIngestResponse(BaseModel):
    """Response schema following document ingestion into Qdrant."""

    doc_id: str
    status: str = Field(..., examples=["ingested"])
    chunks_ingested: int
    collection_name: str
    message: str


class SearchQueryRequest(BaseModel):
    """Request payload for semantic vector search against knowledge base."""

    query: str = Field(
        ...,
        min_length=3,
        description="Raw support ticket text or search query string.",
        examples=["I cannot log into my account even after resetting password!"],
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of search results to return.",
    )
    score_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Minimum vector similarity score threshold (0.0 to 1.0).",
    )
    normalize: bool = Field(
        default=True,
        description="Whether to run Groq query normalization before searching.",
    )


class SearchResultItem(BaseModel):
    """Individual matching document chunk search result."""

    doc_id: str
    title: str
    category: str
    doc_type: str
    chunk_index: int
    content: str
    score: float
    header_context: Optional[str] = None


class SearchResultResponse(BaseModel):
    """Response schema containing semantic search results."""

    raw_query: str
    normalized_query: Optional[str] = None
    total_results: int
    results: list[SearchResultItem]
