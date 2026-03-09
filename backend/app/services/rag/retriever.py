from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from app.services.rag.embedder import embed_texts
from app.services.rag.store import (
    fetch_chunks_by_ids,
    fetch_chunks_by_page,
    vector_search,
)

# Regex to extract page references from user queries.
# Matches: "page 112", "p. 112", "p.112", "p 112", "pg 112", "pg. 112"
_PAGE_REF_RE = re.compile(r"\b(?:page|p\.?|pg\.?)\s*(\d+)\b", re.IGNORECASE)

logger = logging.getLogger(__name__)

# ── BM25 in-memory index ──────────────────────────────────────────────────────
# Rebuilt from LanceDB on server startup and after each successful ingestion.
# Module-level state is intentional: shared across all requests in the process.

_bm25: BM25Okapi | None = None
_bm25_ids: list[str] = []
_bm25_pages: list[int] = []  # page number for each chunk (parallel to _bm25_ids)
_bm25_doc_ids: list[str] = []  # doc_id for each chunk (parallel to _bm25_ids)


def rebuild_bm25_index(chunks: list[tuple[str, str, int, str]]) -> None:
    """Rebuild the in-memory BM25 index from a list of (id, text, page, doc_id) tuples.

    Called on server startup (to restore index from existing LanceDB data)
    and after each successful document ingestion.

    Prepends ``page N`` to each chunk's tokens so BM25 naturally matches
    queries that reference specific page numbers.

    Args:
        chunks: List of (chunk_id, text, page, doc_id) tuples for all stored chunks.
    """
    global _bm25, _bm25_ids, _bm25_pages, _bm25_doc_ids
    if not chunks:
        _bm25 = None
        _bm25_ids = []
        _bm25_pages = []
        _bm25_doc_ids = []
        logger.info("BM25 index cleared (no chunks)")
        return
    _bm25_ids = [cid for cid, _, _, _ in chunks]
    _bm25_pages = [page for _, _, page, _ in chunks]
    _bm25_doc_ids = [doc_id for _, _, _, doc_id in chunks]
    # Prepend "page N" so BM25 matches queries like "page 112"
    tokenized = [
        ["page", str(page)] + text.lower().split()
        for _, text, page, _ in chunks
    ]
    _bm25 = BM25Okapi(tokenized)
    logger.info("BM25 index rebuilt with %d chunk(s)", len(chunks))


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
    doc_id: str | None = None,
) -> list[RetrievedChunk]:
    """Hybrid BM25 + vector retrieval with score fusion.

    Returns an empty list if no documents have been ingested yet (BM25 index
    is None). This is the graceful no-document path — callers should check
    for an empty result and skip context injection.

    Weights BM25 higher than vector (0.6 / 0.4) because mathematical
    notation and theorem references are best matched by exact keyword
    search, not semantic similarity.

    When ``doc_id`` is provided, results are filtered to only include chunks
    from that document. This scopes retrieval to the currently open textbook.

    Args:
        query: Natural-language or math-notation query string.
        top_k: Number of candidates to return before re-ranking.
        bm25_weight: Score weight for the BM25 (keyword) component.
        vector_weight: Score weight for the vector (semantic) component.
        doc_id: Optional document ID to scope retrieval to a single textbook.

    Returns:
        Top-k chunks sorted by fused score, descending.
        Empty list if no documents are ingested.
    """
    if _bm25 is None:
        logger.debug("Retrieval skipped — no BM25 index (no documents ingested)")
        return []

    logger.info("Retrieving top-%d for query: %.80s…", top_k, query)

    # ── Extract page references from the query ─────────────────────────────────
    mentioned_pages: set[int] = set()
    for m in _PAGE_REF_RE.finditer(query):
        mentioned_pages.add(int(m.group(1)))
    if mentioned_pages:
        logger.info("Query references page(s): %s", mentioned_pages)

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
    vec_norm: dict[str, float] = {row["id"]: max(0.0, 1.0 - row["_distance"]) for row in vec_rows}

    # ── Document-scoped filtering ──────────────────────────────────────────────
    # Build lookup maps from BM25 index parallel arrays.
    id_to_page: dict[str, int] = dict(zip(_bm25_ids, _bm25_pages, strict=False))
    id_to_doc: dict[str, str] = dict(zip(_bm25_ids, _bm25_doc_ids, strict=False))
    # Also populate from vector search results (may include chunks not in BM25 index)
    for row in vec_rows:
        id_to_doc[row["id"]] = row["doc_id"]

    # When a doc_id filter is active, remove scores for other documents.
    if doc_id:
        logger.info("Scoping retrieval to doc_id=%s", doc_id[:8])
        bm25_norm = {
            cid: score for cid, score in bm25_norm.items()
            if id_to_doc.get(cid) == doc_id
        }
        vec_norm = {
            cid: score for cid, score in vec_norm.items()
            if id_to_doc.get(cid) == doc_id
        }

    # ── Page-aware chunk injection ─────────────────────────────────────────────
    # If the query mentions specific pages, fetch all chunks from those pages
    # and inject them into the candidate set so they participate in fusion.
    if mentioned_pages:
        for page_num in mentioned_pages:
            page_rows = await asyncio.to_thread(fetch_chunks_by_page, page_num)
            for row in page_rows:
                # Skip chunks from other documents when scoped
                if doc_id and row.get("doc_id") != doc_id:
                    continue
                cid = row["id"]
                id_to_page[cid] = row["page"]
                id_to_doc[cid] = row.get("doc_id", "")
                if cid not in vec_norm:
                    vec_norm[cid] = 0.0
                if cid not in bm25_norm:
                    bm25_norm[cid] = 0.0

    # ── Fuse ──────────────────────────────────────────────────────────────────
    all_ids = set(bm25_norm) | set(vec_norm)
    page_boost = 0.3  # Additive boost for chunks from a mentioned page
    fused: dict[str, float] = {}
    for cid in all_ids:
        score = bm25_weight * bm25_norm.get(cid, 0.0) + vector_weight * vec_norm.get(cid, 0.0)
        if mentioned_pages and id_to_page.get(cid) in mentioned_pages:
            score += page_boost
        fused[cid] = score

    top_ids = sorted(fused, key=fused.__getitem__, reverse=True)[:top_k]
    rows = await asyncio.to_thread(fetch_chunks_by_ids, top_ids)
    logger.info("Retrieved %d chunk(s), top score=%.4f", len(rows), fused[top_ids[0]])

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
