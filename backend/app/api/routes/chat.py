from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.services.tutor.router import route_and_stream

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

    Args:
        request: Chat history and optional session identifier.

    Returns:
        SSE stream — each event is {"content": "<token>"};
        a final "done" event signals end of stream.
    """

    async def generate():  # type: ignore[return]
        async for token in route_and_stream(request.messages):
            yield {"data": json.dumps({"content": token})}
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(generate())
