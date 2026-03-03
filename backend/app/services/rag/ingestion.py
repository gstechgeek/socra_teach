from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import time
import uuid
from pathlib import Path

from app.core.config import settings
from app.services.rag.embedder import embed_texts
from app.services.rag.store import (
    get_all_chunk_texts,
    insert_chunks,
    upsert_document,
)

# ── Cached Docling converter (thread-safe singleton) ─────────────────────────

_converter_lock = threading.Lock()
_converter: object | None = None  # typed as object to avoid import at module level


def _get_converter() -> object:
    """Return a cached DocumentConverter instance.

    The converter loads ~1-2 GB of layout/OCR models on first instantiation.
    Caching avoids reloading these models for every document.
    """
    global _converter  # noqa: PLW0603
    if _converter is None:
        with _converter_lock:
            if _converter is None:
                from docling.document_converter import DocumentConverter  # noqa: I001  # type: ignore[import-untyped]

                _converter = DocumentConverter()
    return _converter


# ── Progress watchdog ────────────────────────────────────────────────────────

_PARSING_PROGRESS_MESSAGES: list[tuple[float, str]] = [
    (10, "Analyzing document layout…"),
    (30, "Extracting text and tables…"),
    (60, "Running OCR on image regions…"),
    (120, "Still processing (large document)…"),
    (240, "Almost done parsing…"),
]


def _run_progress_watchdog(
    doc_id: str,
    filename: str,
    done_event: threading.Event,
) -> None:
    """Update document status with time-based progress messages while parsing.

    Runs as a daemon thread alongside the Docling conversion. Stops when
    ``done_event`` is set by the caller.
    """
    start = time.monotonic()
    msg_idx = 0
    while not done_event.wait(timeout=5):
        elapsed = time.monotonic() - start
        while (
            msg_idx < len(_PARSING_PROGRESS_MESSAGES)
            and elapsed >= _PARSING_PROGRESS_MESSAGES[msg_idx][0]
        ):
            upsert_document(
                doc_id, filename, "processing", 0, _PARSING_PROGRESS_MESSAGES[msg_idx][1]
            )
            msg_idx += 1


# ── Chunking helpers ─────────────────────────────────────────────────────────


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


# ── Main ingestion pipeline ──────────────────────────────────────────────────


def _run_ingestion(doc_id: str, file_path: Path, filename: str) -> None:
    """Synchronous ingestion pipeline — run inside asyncio.to_thread().

    Steps:
      1. Mark document as processing.
      2. Parse with Docling DocumentConverter (cached, with timeout + progress).
      3. Chunk with HierarchicalChunker (fallback to sliding window if 0 chunks).
      4. Batch-embed all chunk texts.
      5. Insert rows into LanceDB chunks table.
      6. Rebuild BM25 index from all stored chunks.
      7. Mark document as done.

    On any exception the document is marked as error with the message.

    Args:
        doc_id: Document UUID.
        file_path: Path to the saved upload file.
        filename: Original filename (for metadata).
    """
    from app.services.rag.retriever import rebuild_bm25_index

    upsert_document(doc_id, filename, "processing", 0, "Initializing PDF parser…")

    try:
        # ── Parse (with timeout + progress watchdog) ──────────────────────────
        converter = _get_converter()
        parsing_done = threading.Event()
        watchdog = threading.Thread(
            target=_run_progress_watchdog,
            args=(doc_id, filename, parsing_done),
            daemon=True,
        )
        watchdog.start()

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(converter.convert, str(file_path))  # type: ignore[union-attr]
                try:
                    result = future.result(timeout=settings.ingestion_timeout)
                except concurrent.futures.TimeoutError:
                    future.cancel()
                    upsert_document(
                        doc_id,
                        filename,
                        "error",
                        0,
                        f"PDF parsing timed out after {settings.ingestion_timeout}s",
                    )
                    return
        finally:
            parsing_done.set()
            watchdog.join(timeout=2)

        # ── Chunk ─────────────────────────────────────────────────────────────
        upsert_document(doc_id, filename, "processing", 0, "Chunking document…")
        from docling.chunking import HierarchicalChunker  # type: ignore[import-untyped]

        raw_chunks = list(HierarchicalChunker().chunk(result.document))

        if not raw_chunks:
            # Fallback: extract raw text and use sliding window
            fallback_text = result.document.export_to_text()
            texts = _sliding_window_chunks(fallback_text)
            chunk_dicts = [
                {
                    "id": str(uuid.uuid4()),
                    "doc_id": doc_id,
                    "text": t,
                    "vector": [],  # filled after embed
                    "page": 0,
                    "section": "",
                    "content_type": "text",
                    "has_equations": "$" in t or "\\" in t,
                }
                for t in texts
            ]
        else:
            chunk_dicts = []
            for chunk in raw_chunks:
                text = chunk.text.strip()
                if not text:
                    continue

                # Extract page number from provenance metadata
                page = 0
                try:
                    page = chunk.meta.doc_items[0].prov[0].page_no
                except (AttributeError, IndexError):
                    pass

                # Extract section heading
                section = ""
                try:
                    headings = chunk.meta.headings
                    if headings:
                        section = headings[0]
                except AttributeError:
                    pass

                chunk_dicts.append(
                    {
                        "id": str(uuid.uuid4()),
                        "doc_id": doc_id,
                        "text": text,
                        "vector": [],  # filled after embed
                        "page": page,
                        "section": section,
                        "content_type": "text",
                        "has_equations": "$" in text or "\\" in text,
                    }
                )

        if not chunk_dicts:
            upsert_document(doc_id, filename, "error", 0, "No text extracted from document")
            return

        # ── Embed ─────────────────────────────────────────────────────────────
        n = len(chunk_dicts)
        upsert_document(
            doc_id, filename, "processing", 0, f"Embedding {n} chunk{'s' if n != 1 else ''}…"
        )
        texts_to_embed = [c["text"] for c in chunk_dicts]
        vectors = embed_texts(texts_to_embed)
        for chunk, vec in zip(chunk_dicts, vectors, strict=True):
            chunk["vector"] = vec

        # ── Store ─────────────────────────────────────────────────────────────
        upsert_document(doc_id, filename, "processing", 0, "Storing in database…")
        insert_chunks(chunk_dicts)

        # ── Rebuild BM25 ──────────────────────────────────────────────────────
        rebuild_bm25_index(get_all_chunk_texts())

        upsert_document(doc_id, filename, "done", len(chunk_dicts), "")

    except Exception as exc:  # noqa: BLE001
        upsert_document(doc_id, filename, "error", 0, str(exc))


async def ingest_document(doc_id: str, file_path: Path, filename: str) -> None:
    """Async entry point for document ingestion — runs pipeline in a thread.

    Called as a FastAPI BackgroundTask. Wraps the synchronous CPU-bound
    pipeline in asyncio.to_thread() so the event loop stays unblocked.

    Args:
        doc_id: Document UUID (already registered in the documents table).
        file_path: Path to the saved upload file.
        filename: Original filename for display purposes.
    """
    await asyncio.to_thread(_run_ingestion, doc_id, file_path, filename)
