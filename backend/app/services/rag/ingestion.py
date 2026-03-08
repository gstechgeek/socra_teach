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


# ── PDF extraction ──────────────────────────────────────────────────────────


def _build_page_label_map(doc: fitz.Document) -> dict[int, int]:
    """Build a mapping from 0-indexed PDF page to printed page number.

    Many textbooks embed page labels in the PDF (e.g., front matter uses
    roman numerals, then arabic numbering starts at 1 for chapter 1).
    PyMuPDF exposes these via ``page.get_label()``.

    Args:
        doc: An open PyMuPDF document.

    Returns:
        Dict mapping 0-indexed PDF page to integer printed page number.
        Only includes pages whose label is a valid positive integer.
    """
    label_map: dict[int, int] = {}
    for i in range(len(doc)):
        try:
            label = doc[i].get_label()
        except Exception:  # noqa: BLE001
            continue
        if label and label.isdigit():
            num = int(label)
            if num > 0:
                label_map[i] = num
    return label_map


def _resolve_page_number(
    page_idx: int,
    label_map: dict[int, int],
) -> int:
    """Convert a 0-indexed PDF page to the best page number for the user.

    Uses the PDF page label (printed page number) when available,
    otherwise falls back to 1-indexed PDF page.

    Args:
        page_idx: 0-indexed PDF page index.
        label_map: Output of :func:`_build_page_label_map`.

    Returns:
        The printed page number, or ``page_idx + 1`` as fallback.
    """
    return label_map.get(page_idx, page_idx + 1)


def _extract_markdown_pages(file_path: Path) -> list[tuple[int, str]]:
    """Extract markdown text from each page of a PDF using PyMuPDF.

    Tries ``pymupdf4llm`` first for rich markdown output (headers, bold,
    tables).  If pymupdf4llm fails to extract meaningful text from a page,
    falls back to raw ``fitz.Page.get_text()`` which is more robust with
    PDFs that have garbled font metadata or unusual encodings.

    Page numbers use the PDF's embedded page labels (printed page numbers)
    when available, so chunks are tagged with the numbers users actually
    see in their textbook rather than raw PDF page indices.

    Args:
        file_path: Path to the PDF file.

    Returns:
        List of ``(page_number, markdown_text)`` tuples.  Page numbers
        use printed labels when available, otherwise 1-indexed PDF page.
    """
    # ── Build page label map for printed page numbers ──────────────
    doc = fitz.open(str(file_path))
    label_map = _build_page_label_map(doc)
    if label_map:
        logger.info(
            "PDF has page labels — using printed page numbers (e.g., PDF page 0 → p.%d)",
            next(iter(label_map.values())),
        )

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
            result.append((_resolve_page_number(page_idx, label_map), text))

    # ── Attempt 2: fitz fallback for pages pymupdf4llm missed ────────
    fallback_count = 0
    for i in range(len(doc)):
        if i in md_extracted:
            continue
        text = doc[i].get_text().strip()
        if len(text) > 50:
            result.append((_resolve_page_number(i, label_map), text))
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


def _page_first_chunks(
    pages: list[tuple[int, str]],
    doc_id: str,
    max_chunk_size: int = 1500,
    overlap: int = 200,
) -> list[dict[str, object]]:
    """Split pages into chunks using a page-first strategy.

    Unlike the old header-first approach (which merged all pages into one
    string and split on headers — breaking page tracking when headers were
    sparse), this processes each page independently so every chunk gets
    the correct page number trivially.

    Strategy:
      1. Process each page individually — page number is always correct.
      2. Track the most recent markdown header as a running section name.
      3. Within each page, split on headers for semantic boundaries.
      4. Sub-split oversized page sections via sliding window.

    Args:
        pages: Output of :func:`_extract_markdown_pages`.
        doc_id: Document UUID for chunk metadata.
        max_chunk_size: Max characters per chunk before sub-splitting.
        overlap: Overlap chars for sliding-window sub-splits.

    Returns:
        List of chunk dicts compatible with ``CHUNK_SCHEMA``.
    """
    chunk_dicts: list[dict[str, object]] = []
    current_section = ""  # running section name inherited across pages

    for page_num, page_text in pages:
        text = page_text.strip()
        if not text:
            continue

        # Find headers on this page
        headers = list(_HEADER_RE.finditer(text))

        if not headers:
            # No headers on this page — use the running section name
            _add_page_chunks(
                chunk_dicts, doc_id, text, page_num, current_section,
                max_chunk_size, overlap,
            )
            continue

        # Split on headers within this page
        # Text before the first header (inherits running section)
        preamble = text[: headers[0].start()].strip()
        if preamble:
            _add_page_chunks(
                chunk_dicts, doc_id, preamble, page_num, current_section,
                max_chunk_size, overlap,
            )

        for i, match in enumerate(headers):
            current_section = match.group(2).strip()
            start = match.start()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            section_text = text[start:end].strip()
            if section_text:
                _add_page_chunks(
                    chunk_dicts, doc_id, section_text, page_num, current_section,
                    max_chunk_size, overlap,
                )

    return chunk_dicts


def _add_page_chunks(
    out: list[dict[str, object]],
    doc_id: str,
    text: str,
    page: int,
    section: str,
    max_chunk_size: int,
    overlap: int,
) -> None:
    """Append chunk(s) for a block of text from a single page.

    If the text fits within *max_chunk_size*, one chunk is created.
    Otherwise it is sub-split via sliding window.
    """
    if len(text) <= max_chunk_size:
        out.append(_make_chunk(doc_id, text, page, section))
    else:
        for sub in _sliding_window_chunks(text, size=max_chunk_size, overlap=overlap):
            if sub.strip():
                out.append(_make_chunk(doc_id, sub.strip(), page, section))


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
        chunk_dicts = _page_first_chunks(pages, doc_id)

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
