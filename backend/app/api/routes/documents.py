from __future__ import annotations

from fastapi import APIRouter, UploadFile

router = APIRouter()


@router.post("/upload")
async def upload_document(file: UploadFile) -> dict[str, str]:
    """Accept a PDF/DOCX upload and queue it for RAG ingestion.

    Phase 3 implementation will:
    1. Save the file to data/uploads/
    2. Parse with Docling (on-device) or pre-processed MinerU output
    3. Chunk with structure-aware recursive splitting (512-token target)
    4. Embed with nomic-embed-text-v1.5 and store in LanceDB

    Args:
        file: Uploaded document (PDF, DOCX, or HTML).

    Returns:
        Dict with doc_id for polling ingestion status.
    """
    # TODO Phase 3
    raise NotImplementedError


@router.get("/{doc_id}/status")
async def document_status(doc_id: str) -> dict[str, str]:
    """Poll ingestion status for an uploaded document.

    Args:
        doc_id: Document identifier returned by /upload.

    Returns:
        Dict with keys: doc_id, status (queued|processing|done|error),
        chunk_count.
    """
    # TODO Phase 3
    raise NotImplementedError


@router.get("/")
async def list_documents() -> list[dict[str, str]]:
    """List all ingested documents for the current user.

    Returns:
        List of document metadata dicts.
    """
    # TODO Phase 3
    raise NotImplementedError
