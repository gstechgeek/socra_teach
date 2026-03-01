from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.services.tutor.router import StreamMeta, route_and_stream

router = APIRouter()


class ChatRequest(BaseModel):
    """Incoming chat request payload."""

    messages: list[dict[str, str]]
    session_id: str | None = None


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> EventSourceResponse:
    """Stream a Socratic tutoring response via Server-Sent Events.

    Routes the query to either the local Llama model or an OpenRouter
    cloud tier based on complexity, then applies the Socratic prompt
    engine before streaming tokens back to the client.

    The stream emits three event types:
    - ``metadata``: tier and model info (emitted once, before tokens).
    - default (no event field): ``{"content": "...", "seq": N}`` token events.
    - ``done``: signals end of stream.

    Args:
        request: Chat history and optional session identifier.

    Returns:
        SSE stream of metadata, token, and done events.
    """

    async def generate() -> AsyncGenerator[dict[str, str], None]:
        seq = 0
        async for item in route_and_stream(request.messages):
            if isinstance(item, StreamMeta):
                yield {
                    "event": "metadata",
                    "data": json.dumps({"tier": item.tier, "model": item.model}),
                }
            else:
                yield {"data": json.dumps({"content": item, "seq": seq})}
                seq += 1
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(generate())
