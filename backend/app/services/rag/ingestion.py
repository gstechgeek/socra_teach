from __future__ import annotations

import asyncio
import logging
import re
import uuid
from pathlib import Path

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pymupdf4llm  # type: ignore[import-untyped]

from app.services.rag.embedder import embed_texts
from app.services.rag.store import (
    get_all_chunk_texts,
    insert_chunks,
    upsert_document,
)

logger = logging.getLogger(__name__)

# Regex matching markdown headers h1–h4
_HEADER_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

# Invisible marker injected between pages so chunks can track page origin
_PAGE_MARKER_RE = re.compile(r"<!-- PAGE:(\d+) -->")


# ── PDF extraction ──────────────────────────────────────────────────────────


def _extract_markdown_pages(file_path: Path) -> list[tuple[int, str]]:
    """Extract markdown text from each page of a PDF using PyMuPDF.

    Tries ``pymupdf4llm`` first for rich markdown output (headers, bold,
    tables).  If pymupdf4llm fails to extract meaningful text from a page,
    falls back to raw ``fitz.Page.get_text()`` which is more robust with
    PDFs that have garbled font metadata or unusual encodings.

    Args:
        file_path: Path to the PDF file.

    Returns:
        List of ``(page_number, markdown_text)`` tuples.  Page numbers are
        1-indexed to match the existing chunk schema convention.
    """
    # ── Attempt 1: pymupdf4llm for markdown-formatted output ──────────
    md_pages: list[dict[str, object]] = pymupdf4llm.to_markdown(
        str(file_path),
        page_chunks=True,
    )
    result: list[tuple[int, str]] = []
    md_extracted: set[int] = set()  # 0-indexed pages that pymupdf4llm handled
    for page_dict in md_pages:
        metadata = page_dict.get("metadata", {})
        page_idx: int = int(metadata.get("page", 0))  # type: ignore[arg-type]
        text = str(page_dict.get("text", ""))
        if text.strip():
            md_extracted.add(page_idx)
            result.append((page_idx + 1, text))

    # ── Attempt 2: fitz fallback for pages pymupdf4llm missed ────────
    doc = fitz.open(str(file_path))
    fallback_count = 0
    for i in range(len(doc)):
        if i in md_extracted:
            continue
        text = doc[i].get_text().strip()
        if len(text) > 50:
            result.append((i + 1, text))
            fallback_count += 1
    doc.close()

    if fallback_count > 0:
        logger.info("pymupdf4llm missed %d pages; recovered via fitz fallback", fallback_count)

    # Sort by page number to maintain order
    result.sort(key=lambda t: t[0])
    return result


# ── Chunking helpers ────────────────────────────────────────────────────────


def _sliding_window_chunks(text: str, size: int = 1000, overlap: int = 200) -> list[str]:
    """Fallback chunker: fixed-size sliding window over raw text.

    Args:
        text: Plain text to split.
        size: Target chunk character length.
        overlap: Character overlap between adjacent chunks.

    Returns:
        List of text chunk strings.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return [c for c in chunks if c.strip()]


def _markdown_section_chunks(
    pages: list[tuple[int, str]],
    doc_id: str,
    max_chunk_size: int = 1500,
    overlap: int = 200,
) -> list[dict[str, object]]:
    """Split page markdown into semantic chunks based on markdown headers.

    Strategy:
      1. Merge all pages into one string with ``<!-- PAGE:N -->`` markers.
      2. Split on markdown headers (h1–h4) to produce semantic sections.
      3. Each section inherits the page number of its starting page marker.
      4. Sections exceeding *max_chunk_size* are sub-split via sliding window.
      5. Pages with no headers fall back to sliding window directly.

    Args:
        pages: Output of :func:`_extract_markdown_pages`.
        doc_id: Document UUID for chunk metadata.
        max_chunk_size: Max characters per chunk before sub-splitting.
        overlap: Overlap chars for sliding-window sub-splits.

    Returns:
        List of chunk dicts compatible with ``CHUNK_SCHEMA``.
    """
    # ── Stage A: merge pages with markers ────────────────────────────────
    parts: list[str] = []
    for page_num, text in pages:
        parts.append(f"<!-- PAGE:{page_num} -->")
        parts.append(text)
    full_text = "\n".join(parts)

    # ── Stage B: split on headers ────────────────────────────────────────
    header_positions = list(_HEADER_RE.finditer(full_text))

    # (heading_text, body, position_in_full_text)
    sections: list[tuple[str, str, int]] = []
    if header_positions:
        # Text before the first header (preamble)
        preamble = full_text[: header_positions[0].start()].strip()
        if preamble:
            sections.append(("", preamble, 0))
        # Each header + body until the next header
        for i, match in enumerate(header_positions):
            heading = match.group(2).strip()
            start = match.start()
            next_start = header_positions[i + 1].start() if i + 1 < len(header_positions) else None
            end = next_start if next_start is not None else len(full_text)
            body = full_text[start:end].strip()
            sections.append((heading, body, start))
    else:
        # No headers at all — treat entire text as one section
        sections.append(("", full_text, 0))

    # ── Stage C: build chunk dicts with size enforcement ─────────────────
    chunk_dicts: list[dict[str, object]] = []

    for heading, body, pos in sections:
        # Find the nearest PAGE marker at or before this section's position
        page = _find_page_at_position(full_text, pos, pages)

        # Remove page markers from final text
        clean_text = _PAGE_MARKER_RE.sub("", body).strip()
        if not clean_text:
            continue

        if len(clean_text) <= max_chunk_size:
            chunk_dicts.append(_make_chunk(doc_id, clean_text, page, heading))
        else:
            # Sub-split oversized sections
            sub_chunks = _sliding_window_chunks(clean_text, size=max_chunk_size, overlap=overlap)
            for sub in sub_chunks:
                chunk_dicts.append(_make_chunk(doc_id, sub, page, heading))

    return chunk_dicts


def _find_page_at_position(full_text: str, pos: int, pages: list[tuple[int, str]]) -> int:
    """Find the page number for a section starting at *pos* in *full_text*.

    Scans backwards from *pos* to find the nearest ``<!-- PAGE:N -->`` marker.
    Falls back to the first page in *pages* if no marker is found.
    """
    # Find all PAGE markers up to (and including) pos
    last_page = 0
    for match in _PAGE_MARKER_RE.finditer(full_text):
        if match.start() <= pos:
            last_page = int(match.group(1))
        else:
            break
    if last_page > 0:
        return last_page
    return pages[0][0] if pages else 0


def _make_chunk(doc_id: str, text: str, page: int, section: str) -> dict[str, object]:
    """Construct a chunk dict compatible with ``CHUNK_SCHEMA``."""
    return {
        "id": str(uuid.uuid4()),
        "doc_id": doc_id,
        "text": text,
        "vector": [],  # filled after embed
        "page": page,
        "section": section,
        "content_type": "text",
        "has_equations": "$" in text or "\\" in text,
    }


# ── Main ingestion pipeline ────────────────────────────────────────────────


def _run_ingestion(doc_id: str, file_path: Path, filename: str) -> None:
    """Synchronous ingestion pipeline — run inside ``asyncio.to_thread()``.

    Steps:
      1. Mark document as processing.
      2. Extract markdown from each page via PyMuPDF.
      3. Split into semantic chunks based on markdown headers.
      4. Detect and warn about image-only pages.
      5. Batch-embed all chunk texts.
      6. Insert rows into LanceDB chunks table.
      7. Rebuild BM25 index from all stored chunks.
      8. Mark document as done.

    On any exception the document is marked as error with the message.

    Args:
        doc_id: Document UUID.
        file_path: Path to the saved upload file.
        filename: Original filename (for metadata).
    """
    from app.services.rag.retriever import rebuild_bm25_index

    logger.info("[%s] Starting ingestion for '%s'", doc_id[:8], filename)
    upsert_document(doc_id, filename, "processing", 0, "Extracting text from PDF…")

    try:
        # ── Extract ──────────────────────────────────────────────────────
        logger.info("[%s] Extracting text from PDF…", doc_id[:8])
        pages = _extract_markdown_pages(file_path)

        if not pages:
            logger.error("[%s] No text extracted from '%s'", doc_id[:8], filename)
            upsert_document(doc_id, filename, "error", 0, "No text extracted from document")
            return

        logger.info("[%s] Extracted %d page(s)", doc_id[:8], len(pages))

        # Warn about image-only pages (pages with very little text)
        doc = fitz.open(str(file_path))
        total_pages = len(doc)
        extracted_pages = {p for p, _ in pages}
        image_only: list[int] = []
        for i in range(total_pages):
            page_num = i + 1
            if page_num not in extracted_pages:
                image_only.append(page_num)
        doc.close()

        if image_only:
            logger.warning(
                "[%s] %d image-only page(s) skipped (no text layer): %s",
                doc_id[:8],
                len(image_only),
                image_only[:10],
            )

        # ── Chunk ────────────────────────────────────────────────────────
        logger.info("[%s] Chunking %d page(s)…", doc_id[:8], len(pages))
        upsert_document(doc_id, filename, "processing", 0, f"Chunking {len(pages)} pages…")
        chunk_dicts = _markdown_section_chunks(pages, doc_id)

        if not chunk_dicts:
            logger.error("[%s] Chunking produced 0 chunks for '%s'", doc_id[:8], filename)
            upsert_document(doc_id, filename, "error", 0, "No text extracted from document")
            return

        logger.info("[%s] Produced %d chunk(s)", doc_id[:8], len(chunk_dicts))

        # ── Embed ────────────────────────────────────────────────────────
        n = len(chunk_dicts)
        logger.info("[%s] Embedding %d chunk(s)…", doc_id[:8], n)
        upsert_document(
            doc_id, filename, "processing", 0, f"Embedding {n} chunk{'s' if n != 1 else ''}…"
        )
        texts_to_embed = [str(c["text"]) for c in chunk_dicts]
        vectors = embed_texts(texts_to_embed)
        for chunk, vec in zip(chunk_dicts, vectors, strict=True):
            chunk["vector"] = vec

        logger.info("[%s] Embedding complete", doc_id[:8])

        # ── Store ────────────────────────────────────────────────────────
        logger.info("[%s] Storing %d chunk(s) in LanceDB…", doc_id[:8], n)
        upsert_document(doc_id, filename, "processing", 0, "Storing in database…")
        insert_chunks(chunk_dicts)

        # ── Rebuild BM25 ─────────────────────────────────────────────────
        logger.info("[%s] Rebuilding BM25 index…", doc_id[:8])
        rebuild_bm25_index(get_all_chunk_texts())

        upsert_document(doc_id, filename, "done", len(chunk_dicts), "")
        logger.info("[%s] Ingestion complete — %d chunks stored", doc_id[:8], len(chunk_dicts))

    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] Ingestion failed for '%s'", doc_id[:8], filename)
        upsert_document(doc_id, filename, "error", 0, str(exc))


async def ingest_document(doc_id: str, file_path: Path, filename: str) -> None:
    """Async entry point for document ingestion — runs pipeline in a thread.

    Called as a FastAPI BackgroundTask. Wraps the synchronous CPU-bound
    pipeline in ``asyncio.to_thread()`` so the event loop stays unblocked.

    Args:
        doc_id: Document UUID (already registered in the documents table).
        file_path: Path to the saved upload file.
        filename: Original filename for display purposes.
    """
    await asyncio.to_thread(_run_ingestion, doc_id, file_path, filename)
