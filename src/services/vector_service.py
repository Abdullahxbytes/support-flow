"""Async Qdrant Cloud vector database service wrapper.

Provides collection management, embedding upsert, and payload-filtered
similarity search through the ``qdrant_client.AsyncQdrantClient``
interface.
"""

import logging
from typing import Optional

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from src.core.config import get_settings

logger = logging.getLogger(__name__)


class VectorService:
    """Asynchronous Qdrant vector-store client for knowledge-base operations.

    Initializes a persistent gRPC/HTTP connection to Qdrant Cloud and
    exposes methods for collection lifecycle, vector upsert, and
    filtered nearest-neighbour search.
    """

    DEFAULT_VECTOR_SIZE = 384  # Matches all-MiniLM-L6-v2 embedding dimension
    DEFAULT_DISTANCE = models.Distance.COSINE

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            prefer_grpc=True,
        )
        logger.info(
            "[VectorService] Qdrant async client initialized — url=%s",
            settings.QDRANT_URL,
        )

    # ── Collection Management ────────────────────────────────────────

    async def ensure_collection_exists(
        self,
        collection_name: str,
        vector_size: int = DEFAULT_VECTOR_SIZE,
        distance: models.Distance = DEFAULT_DISTANCE,
    ) -> bool:
        """Create the target collection if it does not already exist.

        Parameters
        ----------
        collection_name:
            Logical name of the Qdrant collection.
        vector_size:
            Dimensionality of the embedding vectors stored in this
            collection (default ``384`` for all-MiniLM-L6-v2).
        distance:
            Similarity metric (default ``COSINE``).

        Returns
        -------
        bool
            ``True`` if the collection was created, ``False`` if it
            already existed.
        """
        try:
            collections = await self._client.get_collections()
            existing_names = [c.name for c in collections.collections]

            if collection_name in existing_names:
                logger.info(
                    "[VectorService] Collection '%s' already exists.", collection_name
                )
                return False

            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=distance,
                ),
            )
            logger.info(
                "[VectorService] Created collection '%s' — size=%d, distance=%s",
                collection_name,
                vector_size,
                distance.name,
            )
            return True

        except UnexpectedResponse as exc:
            logger.error(
                "[VectorService] Qdrant collection operation failed: %s", exc
            )
            raise RuntimeError(
                f"Qdrant collection error for '{collection_name}': {exc}"
            ) from exc

    # ── Point Operations ─────────────────────────────────────────────

    async def upsert_points(
        self,
        collection_name: str,
        points: list[models.PointStruct],
    ) -> bool:
        """Upsert vector points into a Qdrant collection asynchronously.

        Parameters
        ----------
        collection_name:
            Target Qdrant collection name.
        points:
            List of ``models.PointStruct`` containing point ID, vector, and payload.

        Returns
        -------
        bool
            True on successful upsert.
        """
        try:
            await self._client.upsert(
                collection_name=collection_name,
                points=points,
            )
            logger.info(
                "[VectorService] Successfully upserted %d points to '%s'.",
                len(points),
                collection_name,
            )
            return True
        except Exception as exc:
            logger.error(
                "[VectorService] Failed to upsert points into '%s': %s",
                collection_name,
                exc,
            )
            raise RuntimeError(
                f"Qdrant upsert failure for collection '{collection_name}': {exc}"
            ) from exc

    async def search_vectors(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 5,
        score_threshold: Optional[float] = 0.70,
        filter_params: Optional[models.Filter] = None,
    ) -> list[models.ScoredPoint]:
        """Execute nearest-neighbour similarity search against a Qdrant collection.

        Parameters
        ----------
        collection_name:
            Target Qdrant collection name.
        query_vector:
            Embedding vector representing the search query.
        limit:
            Maximum number of top results to return.
        score_threshold:
            Minimum similarity score threshold (0.0 to 1.0) to filter results.
        filter_params:
            Optional Qdrant payload search filter.

        Returns
        -------
        list[models.ScoredPoint]
            List of matching points with score and payload metadata.
        """
        try:
            results = await self._client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=filter_params,
            )
            logger.info(
                "[VectorService] Found %d matching vectors in '%s' (threshold=%s).",
                len(results),
                collection_name,
                score_threshold,
            )
            return results
        except Exception as exc:
            logger.error(
                "[VectorService] Search failed on collection '%s': %s",
                collection_name,
                exc,
            )
            raise RuntimeError(
                f"Qdrant search error for collection '{collection_name}': {exc}"
            ) from exc

    # ── Connectivity ─────────────────────────────────────────────────

    async def ping_connection(self) -> bool:
        """Verify live connectivity to the Qdrant Cloud cluster.

        Issues a lightweight ``get_collections`` RPC that confirms the
        client can authenticate and communicate with the cluster.

        Returns
        -------
        bool
            ``True`` when Qdrant Cloud responds successfully.
        """
        try:
            await self._client.get_collections()
            return True
        except Exception as exc:
            logger.warning("[VectorService] Qdrant ping failed: %s", exc)
            return False

    # ── Cleanup ──────────────────────────────────────────────────────

    async def close(self) -> None:
        """Gracefully close the underlying Qdrant client connection."""
        await self._client.close()
        logger.info("[VectorService] Qdrant client connection closed.")
