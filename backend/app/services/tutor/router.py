from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings
from app.services.tutor.socratic import build_socratic_prompt

# Maps logical tier names to OpenRouter model IDs configured in Settings.
_CLOUD_MODELS: dict[str, str] = {
    "dialogue": settings.cloud_model_dialogue,   # anthropic/claude-sonnet-4-5
    "reasoning": settings.cloud_model_reasoning,  # deepseek/deepseek-r1
    "fast": settings.cloud_model_fast,            # anthropic/claude-haiku-4-5
}


async def route_and_stream(
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Decide local vs. cloud tier and stream Socratic-framed tokens.

    Routing heuristic (Phase 1: always local; Phase 2: classifier-based):
    - Local  : simple recall, Socratic follow-ups, basic hints, offline
    - dialogue: multi-turn Socratic deepening, misconception diagnosis
    - reasoning: multi-step math proofs, STEM derivations, LaTeX-heavy answers
    - fast   : lightweight reformatting, quick confirmations

    Args:
        messages: OpenAI-format chat history.

    Yields:
        Token strings from whichever model handles the query.
    """
    if _route_local(messages):
        socratic = build_socratic_prompt(messages, cloud=False)
        async for token in _stream_local_async(socratic):
            yield token
    else:
        tier = _select_cloud_tier(messages)
        socratic = build_socratic_prompt(messages, cloud=True)
        async for token in _stream_openrouter(socratic, tier):
            yield token


# ── Routing decision ──────────────────────────────────────────────────────────

def _route_local(messages: list[dict[str, str]]) -> bool:
    """Return True if the query should be handled by the local model.

    Args:
        messages: Chat history used to estimate query complexity.

    Returns:
        True for local inference, False for cloud.
    """
    # Phase 1: always local.
    # Phase 2 TODO: replace with confidence-scoring intent classifier.
    return True


def _select_cloud_tier(messages: list[dict[str, str]]) -> str:
    """Select the OpenRouter model tier for this query.

    Args:
        messages: Chat history used to estimate complexity.

    Returns:
        One of: "dialogue", "reasoning", "fast".
    """
    # Phase 2 TODO: keyword/classifier-based tier selection.
    # Examples of signals to detect:
    #   "reasoning" → multi-step proof, matrix algebra, physics derivation
    #   "fast"      → yes/no confirmation, short reformatting
    #   "dialogue"  → everything else (default)
    return "dialogue"


# ── Local inference (async wrapper) ──────────────────────────────────────────

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

    await loop.run_in_executor(None, _produce)

    while True:
        token = await queue.get()
        if token is None:
            break
        yield token


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

    async with httpx.AsyncClient(timeout=60) as client:
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
