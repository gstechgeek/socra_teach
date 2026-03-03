from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from app.core.config import settings
from app.services.fsrs import store as fsrs_store
from app.services.fsrs.bkt import BKTState
from app.services.fsrs.scheduler import schedule_new_card

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
You are a flashcard extraction engine for a Socratic tutoring system.
Given a tutoring conversation exchange, extract key concepts and flashcards.

Return ONLY valid JSON matching this schema (no markdown fences):
{
  "cards": [
    {
      "front": "Question text (use LaTeX $...$ for math)",
      "back": "Answer text",
      "concept_name": "lowercase_with_underscores",
      "concept_description": "One-sentence description",
      "prerequisites": ["prerequisite_concept_name"]
    }
  ]
}

Rules:
- Extract 1-3 cards per conversation exchange.
- Questions should test understanding, not just recall.
- Use LaTeX $...$ for all math notation.
- concept_name must be lowercase with underscores (e.g. "chain_rule").
- Only include cards for content discussed in THIS exchange.
- If the exchange is casual or has no educational content, return {"cards": []}.
"""


@dataclass
class ExtractedCard:
    """A flashcard extracted from a chat conversation by the LLM."""

    front: str
    back: str
    concept_name: str
    concept_description: str
    prerequisites: list[str] = field(default_factory=list)


async def extract_cards_from_conversation(
    messages: list[dict[str, str]],
) -> list[ExtractedCard]:
    """Call cloud LLM to extract flashcards and concepts from a chat exchange.

    Uses the fast tier (claude-haiku-4-5) for cost efficiency.

    Args:
        messages: The conversation exchange (last user + assistant pair).

    Returns:
        List of ExtractedCard instances. May be empty.
    """
    # Skip if assistant response is too short
    assistant_content = ""
    for m in reversed(messages):
        if m.get("role") == "assistant":
            assistant_content = m.get("content", "")
            break
    if len(assistant_content) < 50:
        return []

    extraction_messages = [
        {"role": "system", "content": _EXTRACTION_PROMPT},
        *messages,
        {"role": "user", "content": "Extract flashcards from the above exchange."},
    ]

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "https://github.com/socra-teach",
    }
    payload = {
        "model": settings.cloud_model_fast,
        "messages": extraction_messages,
        "stream": False,
        "max_tokens": 1024,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Strip markdown fences if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            parsed = json.loads(content)
            cards_data = parsed.get("cards", [])

            return [
                ExtractedCard(
                    front=c["front"],
                    back=c["back"],
                    concept_name=c["concept_name"],
                    concept_description=c.get("concept_description", ""),
                    prerequisites=c.get("prerequisites", []),
                )
                for c in cards_data
                if c.get("front") and c.get("back") and c.get("concept_name")
            ]
    except Exception:
        logger.exception("Failed to extract cards from conversation")
        return []


async def process_and_store_cards(
    extracted: list[ExtractedCard],
    source_message_id: str,
    session_id: str,
) -> list[str]:
    """Persist extracted cards and concepts to LanceDB.

    For each card:
    1. Find or create the concept.
    2. Insert prerequisite edges.
    3. Initialize BKT mastery if new concept.
    4. Create an FSRS Card and persist to review_cards table.
    5. Increment daily_stats.cards_created.

    Args:
        extracted: Cards from extract_cards_from_conversation.
        source_message_id: UUID of the assistant message.
        session_id: Chat session identifier.

    Returns:
        List of card_id strings for newly created cards.
    """
    card_ids: list[str] = []
    now_iso = datetime.now(UTC).isoformat()

    for ec in extracted:
        # Find or create concept
        concept_id = await _find_or_create_concept(
            ec.concept_name, ec.concept_description, session_id, now_iso
        )

        # Insert prerequisite edges
        for prereq_name in ec.prerequisites:
            prereq_id = await _find_or_create_concept(prereq_name, "", session_id, now_iso)
            edge_exists = _check_prerequisite_exists(concept_id, prereq_id)
            if not edge_exists:
                fsrs_store.insert_prerequisite_edge(
                    {
                        "edge_id": str(uuid.uuid4()),
                        "concept_id": concept_id,
                        "prerequisite_id": prereq_id,
                    }
                )

        # Create FSRS card
        fsrs_card = schedule_new_card()
        card_dict = fsrs_card.to_dict()
        card_id = str(uuid.uuid4())

        fsrs_store.upsert_review_card(
            {
                "card_id": card_id,
                "front": ec.front,
                "back": ec.back,
                "concept_id": concept_id,
                "source_message_id": source_message_id,
                "session_id": session_id,
                "state": card_dict["state"],
                "step": card_dict["step"],
                "stability": card_dict["stability"]
                if card_dict["stability"] is not None
                else float("nan"),
                "difficulty": card_dict["difficulty"]
                if card_dict["difficulty"] is not None
                else float("nan"),
                "due": card_dict["due"],
                "last_review": card_dict["last_review"] or "",
                "reps": 0,
                "lapses": 0,
                "created_at": now_iso,
            }
        )
        card_ids.append(card_id)

    # Update daily stats
    if card_ids:
        await _increment_daily_cards_created(len(card_ids))

    return card_ids


async def _find_or_create_concept(
    name: str, description: str, source_doc_id: str, now_iso: str
) -> str:
    """Find an existing concept by name or create a new one.

    Returns:
        The concept_id.
    """
    existing = fsrs_store.get_concept_by_name(name)
    if existing:
        return existing["concept_id"]

    concept_id = str(uuid.uuid4())
    fsrs_store.upsert_concept(
        {
            "concept_id": concept_id,
            "name": name,
            "description": description,
            "source_doc_id": source_doc_id,
            "created_at": now_iso,
        }
    )

    # Initialize BKT mastery
    fsrs_store.upsert_concept_mastery(
        {
            "concept_id": concept_id,
            "p_know": 0.0,
            "p_slip": BKTState.default().p_slip,
            "p_guess": BKTState.default().p_guess,
            "p_transit": BKTState.default().p_transit,
            "total_attempts": 0,
            "correct_attempts": 0,
            "last_updated": now_iso,
        }
    )

    return concept_id


def _check_prerequisite_exists(concept_id: str, prerequisite_id: str) -> bool:
    """Check if a prerequisite edge already exists."""
    edges = fsrs_store.get_all_prerequisites()
    return any(
        e["concept_id"] == concept_id and e["prerequisite_id"] == prerequisite_id for e in edges
    )


async def _increment_daily_cards_created(count: int) -> None:
    """Increment today's cards_created count in daily_stats."""
    from datetime import date

    today = date.today().isoformat()
    stats = await fsrs_store.async_get_daily_stats(today)
    if stats is None:
        stats = {
            "date": today,
            "reviews_completed": 0,
            "cards_created": 0,
            "concepts_learned": 0,
            "streak_days": 0,
            "session_minutes": 0,
        }
    stats["cards_created"] = stats["cards_created"] + count
    await fsrs_store.async_upsert_daily_stats(stats)
