from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, documents, health, progress
from app.core.config import settings

app = FastAPI(
    title="Socratic AI Tutor API",
    version="0.1.0",
    description="Local-first Socratic tutoring backend — Steam Deck OLED",
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
