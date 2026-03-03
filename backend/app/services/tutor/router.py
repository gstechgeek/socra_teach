from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.services.rag.reranker import rerank
from app.services.rag.retriever import rebuild_bm25_index, retrieve
from app.services.tutor.socratic import build_socratic_prompt

# Maps logical tier names to OpenRouter model IDs configured in Settings.
_CLOUD_MODELS: dict[str, str] = {
    "dialogue": settings.cloud_model_dialogue,  # anthropic/claude-sonnet-4-5
    "reasoning": settings.cloud_model_reasoning,  # deepseek/deepseek-r1
    "fast": settings.cloud_model_fast,  # anthropic/claude-haiku-4-5
}

# The tutor always uses the dialogue tier (claude-sonnet-4-5) for consistency.
# The local 1B model is too constrained for quality Socratic tutoring on shared VRAM.
_TUTOR_TIER = "dialogue"

# Separate connect / read timeouts — long reads for reasoning tier streams.
_OPENROUTER_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


@dataclass(frozen=True, slots=True)
class StreamMeta:
    """Metadata emitted once at the start of a stream."""

    tier: str  # "local", "dialogue", "reasoning", "fast"
    model: str  # e.g. "llama-3.2-1b-instruct-q4_k_m" or "anthropic/claude-sonnet-4-5"


async def route_and_stream(
    messages: list[dict[str, str]],
) -> AsyncIterator[str | StreamMeta]:
    """Stream Socratic-framed tokens via the cloud dialogue tier.

    All tutor queries are routed to the dialogue tier (claude-sonnet-4-5)
    for consistent, high-quality Socratic responses. RAG context is
    retrieved and injected into the system prompt when documents have
    been ingested.

    Yields a ``StreamMeta`` object first, followed by token strings.

    Args:
        messages: OpenAI-format chat history.

    Yields:
        A single StreamMeta, then token strings.
    """
    # ── RAG retrieval ─────────────────────────────────────────────────────────
    query = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")

    context: str | None = None
    if query:
        candidates = await retrieve(query, top_k=10)
        if candidates:
            reranked = await rerank(query, candidates, top_k=3)
            if reranked:
                context = "\n\n".join(f"[Page {c.page} — {c.section}]\n{c.text}" for c in reranked)

    # ── Always use cloud dialogue tier ────────────────────────────────────────
    model = _CLOUD_MODELS[_TUTOR_TIER]
    yield StreamMeta(tier=_TUTOR_TIER, model=model)
    socratic = build_socratic_prompt(messages, cloud=True, context=context)
    async for token in _stream_openrouter(socratic, _TUTOR_TIER):
        yield token


async def _warm_bm25() -> None:
    """Rebuild the BM25 index from existing LanceDB chunks on server startup.

    Called from the FastAPI lifespan handler. No-op if no documents have
    been ingested yet (returns immediately with an empty index).
    """
    from app.services.rag.store import get_all_chunk_texts

    chunks = await asyncio.to_thread(get_all_chunk_texts)
    rebuild_bm25_index(chunks)


# ── Local inference (async wrapper) — retained for potential offline mode ─────


async def _stream_local_async(
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Wrap the synchronous local token generator in asyncio.to_thread.

    Runs llama.cpp inference in a thread pool so the FastAPI event loop
    is never blocked.

    Args:
        messages: Socratic-framed message list.

    Yields:
        Token strings.
    """
    from app.core.llm import stream_local

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def _produce() -> None:
        for token in stream_local(messages):
            loop.call_soon_threadsafe(queue.put_nowait, token)
        loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    # Launch producer in thread pool WITHOUT awaiting — lets consumer start immediately.
    producer_task = asyncio.ensure_future(loop.run_in_executor(None, _produce))

    while True:
        token = await queue.get()
        if token is None:
            break
        yield token

    await producer_task  # propagate any thread exception; ensures clean shutdown


# ── OpenRouter cloud inference ────────────────────────────────────────────────


async def _stream_openrouter(
    messages: list[dict[str, str]],
    tier: str,
) -> AsyncIterator[str]:
    """Stream tokens from an OpenRouter model via the OpenAI-compatible API.

    Uses raw httpx streaming — no openai SDK dependency.

    Args:
        messages: Socratic-framed message list.
        tier: One of "dialogue", "reasoning", "fast".

    Yields:
        Token strings from the SSE stream.
    """
    model = _CLOUD_MODELS[tier]
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "https://github.com/socra-teach",  # optional but good practice
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=_OPENROUTER_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{settings.openrouter_base_url}/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                chunk = json.loads(line[6:])
                content: str = chunk["choices"][0].get("delta", {}).get("content", "")
                if content:
                    yield content
