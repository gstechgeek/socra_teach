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


@dataclass(frozen=True, slots=True)
class SourceRef:
    """A single citation source from RAG retrieval."""

    doc_id: str
    page: int
    section: str


@dataclass(frozen=True, slots=True)
class StreamSources:
    """Citation sources emitted once before tokens begin."""

    sources: list[SourceRef]


async def route_and_stream(
    messages: list[dict[str, str]],
    selection: dict[str, object] | None = None,
) -> AsyncIterator[str | StreamMeta | StreamSources]:
    """Stream Socratic-framed tokens via the cloud dialogue tier.

    All tutor queries are routed to the dialogue tier (claude-sonnet-4-5)
    for consistent, high-quality Socratic responses. RAG context is
    retrieved and injected into the system prompt when documents have
    been ingested.

    When ``selection`` is provided (a captured rectangle from the PDF viewer),
    the last user message is converted to multimodal format with the image
    so the cloud model can see the selected diagram or text.

    Yields ``StreamMeta``, then ``StreamSources`` (if RAG context found),
    then token strings.

    Args:
        messages: OpenAI-format chat history.
        selection: Optional dict with ``image_base64`` (str) and ``page`` (int | None).

    Yields:
        StreamMeta, optional StreamSources, then token strings.
    """
    # ── RAG retrieval ─────────────────────────────────────────────────────────
    query = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")

    context: str | None = None
    sources: list[SourceRef] = []
    if query:
        candidates = await retrieve(query, top_k=10)
        if candidates:
            reranked = await rerank(query, candidates, top_k=3)
            if reranked:
                context = "\n\n".join(f"[Page {c.page} — {c.section}]\n{c.text}" for c in reranked)
                # Deduplicate sources by (doc_id, page)
                seen: set[tuple[str, int]] = set()
                for c in reranked:
                    key = (c.doc_id, c.page)
                    if key not in seen:
                        seen.add(key)
                        sources.append(SourceRef(doc_id=c.doc_id, page=c.page, section=c.section))

    # ── Always use cloud dialogue tier ────────────────────────────────────────
    model = _CLOUD_MODELS[_TUTOR_TIER]
    yield StreamMeta(tier=_TUTOR_TIER, model=model)
    if sources:
        yield StreamSources(sources=sources)
    socratic = build_socratic_prompt(messages, cloud=True, context=context)

    # If a PDF selection was captured, convert the last user message to
    # multimodal format (OpenAI vision API) so the cloud model can see it.
    api_messages: list[dict[str, object]] = [dict(m) for m in socratic]
    if selection:
        api_messages = _inject_selection_image(api_messages, selection)

    async for token in _stream_openrouter(api_messages, _TUTOR_TIER):
        yield token


def _inject_selection_image(
    messages: list[dict[str, object]],
    selection: dict[str, object],
) -> list[dict[str, object]]:
    """Convert the last user message to multimodal format with the selection image.

    Finds the last user message and replaces its ``content`` string with
    a list of content parts (text + image_url) following the OpenAI vision
    API format supported by OpenRouter.

    Args:
        messages: Socratic-framed message list (may contain str content).
        selection: Dict with ``image_base64`` and optional ``page``.

    Returns:
        A new message list with the last user message converted to multimodal.
    """
    image_b64 = str(selection.get("image_base64", ""))
    page = selection.get("page")
    if not image_b64:
        return messages

    result: list[dict[str, object]] = []
    last_user_idx = -1
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            last_user_idx = i

    for i, msg in enumerate(messages):
        if i == last_user_idx:
            text_content = str(msg.get("content", ""))
            page_note = f" (selected from page {page})" if page else ""
            content_parts: list[dict[str, object]] = [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                },
                {
                    "type": "text",
                    "text": (
                        f"The student selected the above area from their textbook"
                        f"{page_note}. Their question: {text_content}"
                    ),
                },
            ]
            result.append({"role": "user", "content": content_parts})
        else:
            result.append(msg)

    return result


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
    messages: list[dict[str, object]],
    tier: str,
) -> AsyncIterator[str]:
    """Stream tokens from an OpenRouter model via the OpenAI-compatible API.

    Uses raw httpx streaming — no openai SDK dependency.

    Args:
        messages: Socratic-framed message list (may contain multimodal content).
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
                choices = chunk.get("choices")
                if not choices:
                    continue
                content: str = choices[0].get("delta", {}).get("content", "")
                if content:
                    yield content
