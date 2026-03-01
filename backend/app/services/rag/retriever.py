from __future__ import annotations

from dataclasses import dataclass, field


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


async def retrieve(
    query: str,
    top_k: int = 5,
    bm25_weight: float = 0.6,
    vector_weight: float = 0.4,
) -> list[RetrievedChunk]:
    """Hybrid BM25 + vector retrieval with reciprocal rank fusion.

    Weights BM25 higher than vector (0.6 / 0.4) because mathematical
    notation and theorem references are best matched by exact keyword
    search, not semantic similarity.

    Args:
        query: Natural-language or math-notation query string.
        top_k: Number of candidates to return before re-ranking.
        bm25_weight: Score weight for BM25 (keyword) component.
        vector_weight: Score weight for vector (semantic) component.

    Returns:
        Top-k chunks sorted by fused score, descending.
    """
    # TODO Phase 3:
    #   1. Run BM25 search over rank_bm25 index in memory
    #   2. Run vector ANN search over LanceDB table
    #   3. Fuse scores: fused = bm25_weight × bm25_score + vector_weight × cosine_score
    #   4. Sort descending and return top_k
    raise NotImplementedError
