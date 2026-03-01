from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from app.services.rag.embedder import embed_texts
from app.services.rag.store import fetch_chunks_by_ids, vector_search

# ── BM25 in-memory index ──────────────────────────────────────────────────────
# Rebuilt from LanceDB on server startup and after each successful ingestion.
# Module-level state is intentional: shared across all requests in the process.

_bm25: BM25Okapi | None = None
_bm25_ids: list[str] = []


def rebuild_bm25_index(chunks: list[tuple[str, str]]) -> None:
    """Rebuild the in-memory BM25 index from a list of (id, text) tuples.

    Called on server startup (to restore index from existing LanceDB data)
    and after each successful document ingestion.

    Args:
        chunks: List of (chunk_id, text) tuples for all stored chunks.
    """
    global _bm25, _bm25_ids
    if not chunks:
        _bm25 = None
        _bm25_ids = []
        return
    _bm25_ids = [cid for cid, _ in chunks]
    tokenized = [text.lower().split() for _, text in chunks]
    _bm25 = BM25Okapi(tokenized)


# ── Data model ────────────────────────────────────────────────────────────────


@dataclass
class RetrievedChunk:
    """A single retrieved text chunk with source metadata.

    Attributes:
        text: The chunk text content.
        score: Fused retrieval score (BM25 × 0.6 + vector × 0.4).
        doc_id: Parent document identifier.
        page: Source page number.
        section: Section heading from the document hierarchy.
        content_type: Semantic type — one of:
            theorem | proof | definition | example | exercise | text.
        has_equations: True if the chunk contains LaTeX equation blocks.
    """

    text: str
    score: float
    doc_id: str
    page: int
    section: str
    content_type: str = "text"
    has_equations: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


# ── Retrieval ─────────────────────────────────────────────────────────────────


async def retrieve(
    query: str,
    top_k: int = 5,
    bm25_weight: float = 0.6,
    vector_weight: float = 0.4,
) -> list[RetrievedChunk]:
    """Hybrid BM25 + vector retrieval with score fusion.

    Returns an empty list if no documents have been ingested yet (BM25 index
    is None). This is the graceful no-document path — callers should check
    for an empty result and skip context injection.

    Weights BM25 higher than vector (0.6 / 0.4) because mathematical
    notation and theorem references are best matched by exact keyword
    search, not semantic similarity.

    Args:
        query: Natural-language or math-notation query string.
        top_k: Number of candidates to return before re-ranking.
        bm25_weight: Score weight for the BM25 (keyword) component.
        vector_weight: Score weight for the vector (semantic) component.

    Returns:
        Top-k chunks sorted by fused score, descending.
        Empty list if no documents are ingested.
    """
    if _bm25 is None:
        return []

    # ── BM25 scores ───────────────────────────────────────────────────────────
    bm25_raw = _bm25.get_scores(query.lower().split())
    bm25_max = float(bm25_raw.max()) if bm25_raw.max() > 0 else 1.0
    bm25_norm: dict[str, float] = {
        _bm25_ids[i]: float(s) / bm25_max for i, s in enumerate(bm25_raw)
    }

    # ── Vector scores ─────────────────────────────────────────────────────────
    query_vec = await asyncio.to_thread(embed_texts, [query])
    vec_rows = await asyncio.to_thread(vector_search, query_vec[0], top_k * 2)
    # LanceDB returns _distance (cosine distance, lower = better) → similarity
    vec_norm: dict[str, float] = {
        row["id"]: max(0.0, 1.0 - row["_distance"]) for row in vec_rows
    }

    # ── Fuse ──────────────────────────────────────────────────────────────────
    all_ids = set(bm25_norm) | set(vec_norm)
    fused: dict[str, float] = {
        cid: bm25_weight * bm25_norm.get(cid, 0.0) + vector_weight * vec_norm.get(cid, 0.0)
        for cid in all_ids
    }

    top_ids = sorted(fused, key=fused.__getitem__, reverse=True)[:top_k]
    rows = await asyncio.to_thread(fetch_chunks_by_ids, top_ids)

    return [
        RetrievedChunk(
            text=row["text"],
            score=fused[row["id"]],
            doc_id=row["doc_id"],
            page=row["page"],
            section=row["section"],
            content_type=row["content_type"],
            has_equations=row["has_equations"],
        )
        for row in rows
    ]
