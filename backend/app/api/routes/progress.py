from __future__ import annotations

import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.fsrs import store as fsrs_store
from app.services.fsrs.bkt import mastery_level
from app.services.fsrs.scheduler import get_due_cards_list, review_card_persisted

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Response models ──────────────────────────────────────────────────────────


class ConceptNode(BaseModel):
    """A concept with its BKT mastery state."""

    concept_id: str
    name: str
    description: str
    p_know: float
    mastery: str
    total_attempts: int
    correct_attempts: int


class ConceptEdge(BaseModel):
    """A prerequisite edge between two concepts."""

    concept_id: str
    prerequisite_id: str


class ConceptGraphResponse(BaseModel):
    """The full concept graph with nodes and edges."""

    concepts: list[ConceptNode]
    edges: list[ConceptEdge]


class CardResponse(BaseModel):
    """A review card returned from the API."""

    card_id: str
    front: str
    back: str
    concept_id: str
    state: int
    due: str
    stability: float
    difficulty: float
    reps: int
    lapses: int
    created_at: str


class ReviewRequest(BaseModel):
    """Payload for submitting a card review."""

    rating: int = Field(ge=1, le=4)
    duration_ms: int = Field(default=0, ge=0)


class StatsResponse(BaseModel):
    """Today's stats plus recent history."""

    today: DailyStats
    history: list[DailyStats]


class DailyStats(BaseModel):
    """Stats for a single day."""

    date: str
    reviews_completed: int
    cards_created: int
    concepts_learned: int
    streak_days: int
    session_minutes: int


# Fix forward reference
StatsResponse.model_rebuild()


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/concepts")
async def get_concepts() -> ConceptGraphResponse:
    """Return the concept graph with per-concept BKT mastery levels."""
    concepts = await fsrs_store.async_get_all_concepts()
    mastery_records = await fsrs_store.async_get_all_concept_mastery()
    edges = await fsrs_store.async_get_all_prerequisites()

    mastery_map = {m["concept_id"]: m for m in mastery_records}

    nodes = []
    for c in concepts:
        m = mastery_map.get(c["concept_id"])
        p_know = m["p_know"] if m else 0.0
        from app.services.fsrs.bkt import BKTState

        level = mastery_level(BKTState(p_know=p_know))
        nodes.append(
            ConceptNode(
                concept_id=c["concept_id"],
                name=c["name"],
                description=c.get("description", ""),
                p_know=p_know,
                mastery=level,
                total_attempts=m["total_attempts"] if m else 0,
                correct_attempts=m["correct_attempts"] if m else 0,
            )
        )

    edge_list = [
        ConceptEdge(concept_id=e["concept_id"], prerequisite_id=e["prerequisite_id"]) for e in edges
    ]

    return ConceptGraphResponse(concepts=nodes, edges=edge_list)


@router.get("/cards/due")
async def get_due_cards() -> list[CardResponse]:
    """Return FSRS review cards that are due now, sorted by urgency."""
    cards = await get_due_cards_list()
    return [_card_dict_to_response(c) for c in cards]


@router.get("/cards")
async def get_all_cards() -> list[CardResponse]:
    """Return all review cards."""
    cards = await fsrs_store.async_get_all_review_cards()
    return [_card_dict_to_response(c) for c in cards]


@router.get("/cards/{card_id}")
async def get_card(card_id: str) -> CardResponse:
    """Return a single card by ID."""
    card = await fsrs_store.async_get_review_card(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return _card_dict_to_response(card)


@router.post("/cards/{card_id}/review")
async def submit_review(card_id: str, body: ReviewRequest) -> CardResponse:
    """Submit a review outcome for an FSRS flashcard.

    Args:
        card_id: The card identifier.
        body: Rating (1-4) and optional duration in ms.

    Returns:
        Updated card state with next due date.
    """
    try:
        updated = await review_card_persisted(card_id, body.rating, body.duration_ms)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return _card_dict_to_response(updated)


@router.get("/stats")
async def get_daily_stats() -> StatsResponse:
    """Return today's stats and last 30 days of history."""
    today_str = date.today().isoformat()
    today_stats = await fsrs_store.async_get_daily_stats(today_str)

    if today_stats is None:
        today_stats = {
            "date": today_str,
            "reviews_completed": 0,
            "cards_created": 0,
            "concepts_learned": 0,
            "streak_days": 0,
            "session_minutes": 0,
        }

    # Last 30 days
    start = (date.today() - timedelta(days=30)).isoformat()
    history = await fsrs_store.async_get_stats_range(start, today_str)

    return StatsResponse(
        today=DailyStats(**today_stats),
        history=[DailyStats(**h) for h in history],
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _card_dict_to_response(card: dict[str, object]) -> CardResponse:
    """Convert a LanceDB card row dict to a CardResponse."""
    import math

    stability = card.get("stability", 0.0)
    difficulty = card.get("difficulty", 0.0)

    return CardResponse(
        card_id=str(card["card_id"]),
        front=str(card["front"]),
        back=str(card["back"]),
        concept_id=str(card["concept_id"]),
        state=int(card["state"]),  # type: ignore[arg-type]
        due=str(card["due"]),
        stability=(
            0.0 if (isinstance(stability, float) and math.isnan(stability)) else float(stability)  # type: ignore[arg-type]
        ),
        difficulty=(
            0.0 if (isinstance(difficulty, float) and math.isnan(difficulty)) else float(difficulty)  # type: ignore[arg-type]
        ),
        reps=int(card.get("reps", 0)),  # type: ignore[arg-type]
        lapses=int(card.get("lapses", 0)),  # type: ignore[arg-type]
        created_at=str(card.get("created_at", "")),
    )
