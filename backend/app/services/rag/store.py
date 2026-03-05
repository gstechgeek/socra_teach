from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import lancedb  # type: ignore[import-untyped]
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Table names ───────────────────────────────────────────────────────────────

_CHUNKS_TABLE = "chunks"
_DOCUMENTS_TABLE = "documents"

# ── PyArrow schemas ───────────────────────────────────────────────────────────

CHUNK_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("doc_id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), 256)),
        pa.field("page", pa.int32()),
        pa.field("section", pa.string()),
        pa.field("content_type", pa.string()),
        pa.field("has_equations", pa.bool_()),
    ]
)

DOCUMENT_SCHEMA = pa.schema(
    [
        pa.field("doc_id", pa.string()),
        pa.field("filename", pa.string()),
        pa.field("status", pa.string()),  # queued | processing | done | error
        pa.field("chunk_count", pa.int32()),
        pa.field("error", pa.string()),
    ]
)


# ── Database connection ───────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_db() -> Any:
    """Open (or create) the local LanceDB store. Cached for the process lifetime.

    Returns:
        A lancedb.DBConnection instance.
    """
    db_path = Path(settings.lancedb_path)
    db_path.mkdir(parents=True, exist_ok=True)
    logger.info("Connecting to LanceDB at %s", db_path)
    return lancedb.connect(str(db_path))


# ── Table accessors ───────────────────────────────────────────────────────────


def get_chunks_table() -> Any:
    """Open or create the chunks table.

    Returns:
        LanceDB Table for document chunks.
    """
    db = get_db()
    if _CHUNKS_TABLE in db.table_names():
        return db.open_table(_CHUNKS_TABLE)
    return db.create_table(_CHUNKS_TABLE, schema=CHUNK_SCHEMA)


def get_documents_table() -> Any:
    """Open or create the documents metadata table.

    Returns:
        LanceDB Table for document status records.
    """
    db = get_db()
    if _DOCUMENTS_TABLE in db.table_names():
        return db.open_table(_DOCUMENTS_TABLE)
    return db.create_table(_DOCUMENTS_TABLE, schema=DOCUMENT_SCHEMA)


# ── Write helpers ─────────────────────────────────────────────────────────────


def insert_chunks(rows: list[dict[str, Any]]) -> None:
    """Batch-insert chunk rows into the chunks table.

    Args:
        rows: List of dicts matching CHUNK_SCHEMA fields.
    """
    if not rows:
        return
    tbl = get_chunks_table()
    tbl.add(rows)
    logger.info("Inserted %d chunk(s) into LanceDB", len(rows))


def upsert_document(
    doc_id: str,
    filename: str,
    status: str,
    chunk_count: int,
    error: str,
) -> None:
    """Insert or replace a document metadata row.

    Deletes any existing row with the same doc_id before inserting,
    so this acts as an upsert.

    Args:
        doc_id: Document UUID.
        filename: Original uploaded filename.
        status: One of queued | processing | done | error.
        chunk_count: Number of chunks stored (0 during processing).
        error: Error message if status is "error", else empty string.
    """
    tbl = get_documents_table()
    try:
        tbl.delete(f'doc_id = "{doc_id}"')
    except Exception:  # noqa: BLE001
        pass  # table may be empty — delete is a no-op
    tbl.add(
        [
            {
                "doc_id": doc_id,
                "filename": filename,
                "status": status,
                "chunk_count": chunk_count,
                "error": error,
            }
        ]
    )


# ── Read helpers ──────────────────────────────────────────────────────────────


def vector_search(vector: list[float], top_k: int) -> list[dict[str, Any]]:
    """ANN vector search over the chunks table.

    Args:
        vector: Query embedding (256-dim float32).
        top_k: Maximum number of results to return.

    Returns:
        List of row dicts including _distance (cosine distance, lower = better).
    """
    tbl = get_chunks_table()
    results = tbl.search(vector).limit(top_k).to_list()
    return results  # type: ignore[return-value]


def fetch_chunks_by_ids(ids: list[str]) -> list[dict[str, Any]]:
    """Fetch specific chunk rows by their UUID ids.

    Args:
        ids: List of chunk UUID strings.

    Returns:
        List of matching row dicts (order not guaranteed).
    """
    if not ids:
        return []
    tbl = get_chunks_table()
    arrow_tbl = tbl.to_arrow()
    mask = pc.is_in(arrow_tbl["id"], value_set=pa.array(ids, type=pa.string()))
    return arrow_tbl.filter(mask).to_pylist()  # type: ignore[return-value]


def get_all_chunk_texts() -> list[tuple[str, str]]:
    """Return (id, text) tuples for every chunk — used to rebuild BM25 index.

    Returns:
        List of (chunk_id, text) tuples, empty if no chunks exist.
    """
    db = get_db()
    if _CHUNKS_TABLE not in db.table_names():
        return []
    tbl = get_chunks_table()
    arrow_tbl = tbl.to_arrow().select(["id", "text"])
    return [(r["id"], r["text"]) for r in arrow_tbl.to_pylist()]


def get_document(doc_id: str) -> dict[str, Any] | None:
    """Fetch a single document metadata row by doc_id.

    Args:
        doc_id: Document UUID.

    Returns:
        Row dict, or None if not found.
    """
    db = get_db()
    if _DOCUMENTS_TABLE not in db.table_names():
        return None
    tbl = get_documents_table()
    arrow_tbl = tbl.to_arrow()
    mask = pc.equal(arrow_tbl["doc_id"], doc_id)
    rows = arrow_tbl.filter(mask).to_pylist()
    return rows[0] if rows else None


def list_all_documents() -> list[dict[str, Any]]:
    """Return all document metadata rows.

    Returns:
        List of row dicts (may be empty if no documents have been uploaded).
    """
    db = get_db()
    if _DOCUMENTS_TABLE not in db.table_names():
        return []
    tbl = get_documents_table()
    return tbl.to_arrow().to_pylist()  # type: ignore[return-value]


# ── Async wrappers ────────────────────────────────────────────────────────────
# Convenience helpers that wrap sync functions in asyncio.to_thread.
# Use these from FastAPI route handlers and other async contexts.


def delete_document(doc_id: str) -> None:
    """Delete a document record and all its chunks from LanceDB.

    Args:
        doc_id: Document UUID to remove.
    """
    logger.info("Deleting document %s and its chunks", doc_id[:8])
    db = get_db()
    if _DOCUMENTS_TABLE in db.table_names():
        get_documents_table().delete(f'doc_id = "{doc_id}"')
    if _CHUNKS_TABLE in db.table_names():
        get_chunks_table().delete(f'doc_id = "{doc_id}"')


async def async_upsert_document(
    doc_id: str, filename: str, status: str, chunk_count: int, error: str
) -> None:
    """Async wrapper for upsert_document."""
    await asyncio.to_thread(upsert_document, doc_id, filename, status, chunk_count, error)
