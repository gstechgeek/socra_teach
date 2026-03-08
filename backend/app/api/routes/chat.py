from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.services.tutor.router import StreamMeta, StreamSources, route_and_stream

logger = logging.getLogger(__name__)

router = APIRouter()


class SelectionContext(BaseModel):
    """Image selection from the PDF viewer."""

    image_base64: str
    page: int | None = None


class ChatRequest(BaseModel):
    """Incoming chat request payload."""

    messages: list[dict[str, str]]
    session_id: str | None = None
    selection_context: SelectionContext | None = None


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

    After the stream completes, card generation fires in the background.

    Args:
        request: Chat history and optional session identifier.

    Returns:
        SSE stream of metadata, token, and done events.
    """

    async def generate() -> AsyncGenerator[dict[str, str], None]:
        seq = 0
        response_chunks: list[str] = []
        error_occurred = False
        try:
            selection: dict[str, object] | None = None
            if request.selection_context:
                selection = {
                    "image_base64": request.selection_context.image_base64,
                    "page": request.selection_context.page,
                }
            async for item in route_and_stream(request.messages, selection=selection):
                if isinstance(item, StreamMeta):
                    yield {
                        "event": "metadata",
                        "data": json.dumps({"tier": item.tier, "model": item.model}),
                    }
                elif isinstance(item, StreamSources):
                    yield {
                        "event": "sources",
                        "data": json.dumps([
                            {"doc_id": s.doc_id, "page": s.page, "section": s.section}
                            for s in item.sources
                        ]),
                    }
                else:
                    response_chunks.append(item)
                    yield {"data": json.dumps({"content": item, "seq": seq})}
                    seq += 1
        except Exception:
            logger.exception("Stream interrupted")
            error_occurred = True
            yield {
                "event": "error",
                "data": json.dumps({"message": "Stream interrupted — response may be incomplete."}),
            }
        finally:
            yield {"event": "done", "data": "{}"}

        # Fire card generation in background if we got a meaningful response
        full_response = "".join(response_chunks)
        if not error_occurred and len(full_response) >= 50:
            session_id = request.session_id or "default"
            source_message_id = str(uuid.uuid4())
            last_msgs = (
                request.messages[-2:] if len(request.messages) >= 2 else request.messages
            )
            exchange = list(last_msgs)
            exchange.append({"role": "assistant", "content": full_response})
            asyncio.create_task(
                _generate_cards_background(exchange, source_message_id, session_id)
            )

    return EventSourceResponse(generate())


async def _generate_cards_background(
    messages: list[dict[str, str]],
    source_message_id: str,
    session_id: str,
) -> None:
    """Extract and store flashcards from a chat exchange. Never raises."""
    try:
        from app.services.fsrs.card_generator import (
            extract_cards_from_conversation,
            process_and_store_cards,
        )

        extracted = await extract_cards_from_conversation(messages)
        if extracted:
            card_ids = await process_and_store_cards(extracted, source_message_id, session_id)
            logger.info("Generated %d cards from chat exchange", len(card_ids))
    except Exception:
        logger.exception("Background card generation failed")
