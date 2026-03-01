from __future__ import annotations

import asyncio
from functools import lru_cache

from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]

from app.services.rag.retriever import RetrievedChunk


@lru_cache(maxsize=1)
def _get_cross_encoder() -> CrossEncoder:
    """Load and cache the ms-marco cross-encoder model.

    22 M parameters, CPU-only, ~85 MB RAM.
    Loaded lazily on first rerank() call.

    Returns:
        A ready-to-use CrossEncoder instance.
    """
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


async def rerank(
    query: str,
    chunks: list[RetrievedChunk],
    top_k: int = 3,
) -> list[RetrievedChunk]:
    """Re-rank retrieved chunks with a cross-encoder model.

    Uses cross-encoder/ms-marco-MiniLM-L-6-v2 (22 M params, CPU-only).
    The cross-encoder scores each (query, chunk) pair jointly, giving
    better relevance ranking than the bi-encoder retrieval stage.

    Returns an empty list if chunks is empty (no documents ingested or
    retrieval returned nothing).

    Args:
        query: Original query string.
        chunks: Candidate chunks from hybrid retrieval.
        top_k: Number of chunks to return after re-ranking.

    Returns:
        Re-ranked top-k chunks sorted by cross-encoder score, descending.
    """
    if not chunks:
        return []

    pairs = [(query, c.text) for c in chunks]
    scores = await asyncio.to_thread(_get_cross_encoder().predict, pairs)
    ranked = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
    return [c for _, c in ranked[:top_k]]
