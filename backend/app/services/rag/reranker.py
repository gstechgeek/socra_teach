from __future__ import annotations

from app.services.rag.retriever import RetrievedChunk


async def rerank(
    query: str,
    chunks: list[RetrievedChunk],
    top_k: int = 3,
) -> list[RetrievedChunk]:
    """Re-rank retrieved chunks with a cross-encoder model.

    Uses cross-encoder/ms-marco-MiniLM-L-6-v2 (22 M params, CPU-only).
    The cross-encoder scores each (query, chunk) pair jointly, giving
    better relevance ranking than the bi-encoder retrieval stage.

    Args:
        query: Original query string.
        chunks: Candidate chunks from hybrid retrieval.
        top_k: Number of chunks to return after re-ranking.

    Returns:
        Re-ranked top-k chunks sorted by cross-encoder score, descending.
    """
    # TODO Phase 3:
    #   from sentence_transformers import CrossEncoder
    #   model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    #   pairs = [(query, c.text) for c in chunks]
    #   scores = model.predict(pairs)
    #   return sorted by score, return top_k
    raise NotImplementedError
