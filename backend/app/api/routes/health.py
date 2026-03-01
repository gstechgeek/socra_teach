from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TypedDict

import httpx
import lancedb  # type: ignore[import-untyped]
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings

router = APIRouter()


class ServiceStatus(TypedDict):
    """Status dict returned by each service checker."""

    status: str  # "ok" | "error" | "not_initialized"
    detail: str


async def _check_local_llm() -> ServiceStatus:
    """Check that the GGUF model file exists on disk."""
    try:
        model_file = Path(settings.model_path)
        if model_file.exists() and model_file.is_file():
            return {"status": "ok", "detail": model_file.name}
        return {"status": "error", "detail": f"Model file not found: {settings.model_path}"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


async def _check_openrouter() -> ServiceStatus:
    """Ping the OpenRouter /models endpoint to validate the API key."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{settings.openrouter_base_url}/models",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            )
        if resp.status_code == 200:
            return {"status": "ok", "detail": f"HTTP {resp.status_code}"}
        return {"status": "error", "detail": f"HTTP {resp.status_code}"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


async def _check_supabase() -> ServiceStatus:
    """Hit the Supabase auth health endpoint."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{settings.supabase_url}/auth/v1/health",
                headers={"apikey": settings.supabase_key},
            )
        if resp.status_code == 200:
            return {"status": "ok", "detail": f"HTTP {resp.status_code}"}
        return {"status": "error", "detail": f"HTTP {resp.status_code}"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


async def _check_lancedb() -> ServiceStatus:
    """Open the local LanceDB store and list tables (runs in thread pool)."""
    db_path = Path(settings.lancedb_path)
    if not db_path.exists():
        return {
            "status": "not_initialized",
            "detail": "data dir not found — Phase 3",
        }

    try:
        def _open() -> list[str]:
            db = lancedb.connect(str(db_path))
            return db.table_names()  # type: ignore[no-any-return]

        tables: list[str] = await asyncio.to_thread(_open)
        return {"status": "ok", "detail": f"{len(tables)} table(s)"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


@router.get("/health")
async def health() -> JSONResponse:
    """Return the live status of all runtime service dependencies.

    Returns HTTP 200 when all services are reachable (or not yet
    initialised, which is expected pre-Phase 3). Returns HTTP 503 if any
    service reports an error.
    """
    llm, openrouter, supabase, lancedb_status = await asyncio.gather(
        _check_local_llm(),
        _check_openrouter(),
        _check_supabase(),
        _check_lancedb(),
    )

    services: dict[str, ServiceStatus] = {
        "local_llm": llm,
        "openrouter": openrouter,
        "supabase": supabase,
        "lancedb": lancedb_status,
    }

    # "not_initialized" is expected before Phase 3 — not an error
    degraded = any(s["status"] == "error" for s in services.values())
    overall = "degraded" if degraded else "ok"

    return JSONResponse(
        content={"status": overall, "services": services},
        status_code=503 if degraded else 200,
    )
