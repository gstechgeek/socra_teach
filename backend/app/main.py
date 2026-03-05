from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, documents, health, progress
from app.core.config import settings

# ── Logging setup ────────────────────────────────────────────────────────────
# Configure the "app" logger so all app.services.rag.*, app.api.*, etc.
# loggers emit at INFO level with a consistent format.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan handler — runs setup on startup, teardown on shutdown.

    Rebuilds the in-memory BM25 index from any LanceDB chunks that were
    stored in a previous session. No-op if no documents have been ingested.
    """
    from app.services.tutor.router import _warm_bm25

    await _warm_bm25()
    yield


app = FastAPI(
    title="Socratic AI Tutor API",
    version="0.1.0",
    description="Local-first Socratic tutoring backend — Steam Deck OLED",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(progress.router, prefix="/api/progress", tags=["progress"])
