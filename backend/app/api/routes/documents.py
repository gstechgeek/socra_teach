from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.services.rag.ingestion import ingest_document
from app.services.rag.store import (
    async_upsert_document,
    delete_document,
    get_document,
    list_all_documents,
)

router = APIRouter()

_UPLOAD_DIR = Path("../data/uploads")


@router.post("/upload")
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Accept a PDF/DOCX upload and queue it for RAG ingestion.

    Saves the file to data/uploads/, registers it as queued in LanceDB,
    then starts background ingestion (Docling → chunk → embed → store).

    Args:
        file: Uploaded document (PDF, DOCX, or HTML).
        background_tasks: FastAPI background task runner.

    Returns:
        Dict with doc_id and status "queued".
    """
    doc_id = str(uuid4())
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "upload").suffix or ".pdf"
    dest = _UPLOAD_DIR / f"{doc_id}{suffix}"

    content = await file.read()
    async with aiofiles.open(dest, "wb") as f:
        await f.write(content)

    await async_upsert_document(doc_id, file.filename or "", "queued", 0, "")
    background_tasks.add_task(ingest_document, doc_id, dest, file.filename or "")

    return {"doc_id": doc_id, "status": "queued"}


@router.get("/{doc_id}/file")
async def get_document_file(doc_id: str) -> FileResponse:
    """Serve the original uploaded file for the frontend PDF viewer.

    The file is available immediately after upload, even before ingestion
    completes. This enables the user to read the PDF while background
    processing runs.

    Args:
        doc_id: Document identifier returned by /upload.

    Returns:
        The raw uploaded file with appropriate media type.

    Raises:
        HTTPException 404: If the file is not found on disk.
    """
    matches = list(_UPLOAD_DIR.glob(f"{doc_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(matches[0], media_type="application/pdf")


@router.get("/{doc_id}/status")
async def document_status(doc_id: str) -> dict[str, str]:
    """Poll ingestion status for an uploaded document.

    Args:
        doc_id: Document identifier returned by /upload.

    Returns:
        Dict with keys: doc_id, status (queued|processing|done|error),
        chunk_count.

    Raises:
        HTTPException 404: If doc_id is not found.
    """
    doc = await asyncio.to_thread(get_document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    return {
        "doc_id": doc_id,
        "status": doc["status"],
        "chunk_count": str(doc["chunk_count"]),
        "error": doc.get("error", ""),
    }


@router.delete("/{doc_id}", status_code=204)
async def delete_document_route(doc_id: str) -> None:
    """Delete a document record, its chunks, and its uploaded file.

    Args:
        doc_id: Document identifier returned by /upload.

    Raises:
        HTTPException 404: If doc_id is not found.
    """
    doc = await asyncio.to_thread(get_document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")

    # Remove from LanceDB (doc record + all chunks)
    await asyncio.to_thread(delete_document, doc_id)

    # Remove the uploaded file from disk
    for f in _UPLOAD_DIR.glob(f"{doc_id}.*"):
        f.unlink(missing_ok=True)

    # Rebuild in-memory BM25 index without the deleted chunks
    from app.services.rag.retriever import rebuild_bm25_index
    from app.services.rag.store import get_all_chunk_texts

    chunks = await asyncio.to_thread(get_all_chunk_texts)
    rebuild_bm25_index(chunks)


@router.get("/")
async def list_documents() -> list[dict[str, str]]:
    """List all ingested documents.

    Returns:
        List of document metadata dicts with doc_id, filename, and status.
    """
    docs = await asyncio.to_thread(list_all_documents)
    return [
        {
            "doc_id": d["doc_id"],
            "filename": d["filename"],
            "status": d["status"],
            "chunk_count": str(d.get("chunk_count", 0)),
            "error": d.get("error", ""),
        }
        for d in docs
    ]
