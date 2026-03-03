from __future__ import annotations

import asyncio
import logging
import math
import uuid
from datetime import UTC, date, datetime
from typing import Any

from fsrs import Card, Rating, Scheduler

from app.services.fsrs import store as fsrs_store
from app.services.fsrs.bkt import BKTState, bkt_update

logger = logging.getLogger(__name__)

_scheduler = Scheduler()


# ── Basic FSRS helpers ────────────────────────────────────────────────────────


def schedule_new_card() -> Card:
    """Create a new FSRS card with default initial state.

    Returns:
        A freshly initialised FSRS Card ready for its first review.
    """
    return Card()


def review_card(card: Card, rating: Rating) -> tuple[Card, datetime]:
    """Apply a review rating and return the updated card and next due date.

    Args:
        card: Current FSRS card state.
        rating: Review outcome — Again (1), Hard (2), Good (3), Easy (4).

    Returns:
        Tuple of (updated_card, next_due_datetime).
    """
    updated_card, _review_log = _scheduler.review_card(card, rating)
    return updated_card, updated_card.due


def cards_due(cards: list[Card]) -> list[Card]:
    """Filter a card list to those due for review now.

    Args:
        cards: All FSRS cards for the current user.

    Returns:
        Subset of cards whose due date is <= now, sorted by urgency.
    """
    now = datetime.now(UTC)
    due = [c for c in cards if c.due <= now]
    return sorted(due, key=lambda c: c.due)


# ── Card ↔ LanceDB row conversion ────────────────────────────────────────────


def card_from_row(row: dict[str, Any]) -> Card:
    """Reconstruct an fsrs.Card from a LanceDB row dict.

    Args:
        row: Row dict from the review_cards table.

    Returns:
        An fsrs.Card with state restored from the row.
    """
    stability = row.get("stability")
    if stability is not None and math.isnan(stability):
        stability = None

    difficulty = row.get("difficulty")
    if difficulty is not None and math.isnan(difficulty):
        difficulty = None

    return Card.from_dict(
        {
            "card_id": row.get("card_id", 0),
            "state": row["state"],
            "step": row["step"],
            "stability": stability,
            "difficulty": difficulty,
            "due": row["due"],
            "last_review": row["last_review"] or None,
        }
    )


def card_to_row_update(card: Card, existing_row: dict[str, Any]) -> dict[str, Any]:
    """Merge updated FSRS card state back into a row dict for LanceDB upsert.

    Preserves metadata fields (front, back, concept_id, etc.) from the
    existing row and overwrites FSRS scheduling fields.

    Args:
        card: Updated fsrs.Card after a review.
        existing_row: The row dict as read from LanceDB.

    Returns:
        A new dict ready for upsert_review_card.
    """
    d = card.to_dict()
    return {
        **existing_row,
        "state": d["state"],
        "step": d["step"],
        "stability": d["stability"] if d["stability"] is not None else float("nan"),
        "difficulty": d["difficulty"] if d["difficulty"] is not None else float("nan"),
        "due": d["due"],
        "last_review": d["last_review"] or "",
    }


# ── High-level persisted operations ──────────────────────────────────────────


async def review_card_persisted(
    card_id: str,
    rating: int,
    duration_ms: int = 0,
) -> dict[str, Any] | None:
    """Apply an FSRS review and persist all side effects.

    1. Load card row from LanceDB.
    2. Reconstruct fsrs.Card and apply the rating.
    3. Persist updated card back to LanceDB.
    4. Insert review log entry.
    5. Update BKT mastery for the card's concept.
    6. Update daily stats.

    Args:
        card_id: Review card UUID.
        rating: FSRS rating (1=Again, 2=Hard, 3=Good, 4=Easy).
        duration_ms: Time spent reviewing the card in milliseconds.

    Returns:
        Updated card row dict, or None if card not found.
    """
    row = await fsrs_store.async_get_review_card(card_id)
    if row is None:
        return None

    fsrs_rating = Rating(rating)
    fsrs_card = card_from_row(row)
    state_before = row["state"]

    updated_card, _ = _scheduler.review_card(fsrs_card, fsrs_rating)
    updated_row = card_to_row_update(updated_card, row)

    # Increment reps and lapses
    updated_row["reps"] = row["reps"] + 1
    if rating == 1:
        updated_row["lapses"] = row["lapses"] + 1

    await fsrs_store.async_upsert_review_card(updated_row)

    # Review log
    log_entry = {
        "log_id": str(uuid.uuid4()),
        "card_id": card_id,
        "rating": rating,
        "review_datetime": datetime.now(UTC).isoformat(),
        "review_duration_ms": duration_ms,
        "state_before": state_before,
        "state_after": updated_row["state"],
    }
    await asyncio.to_thread(fsrs_store.insert_review_log, log_entry)

    # BKT update
    concept_id = row.get("concept_id", "")
    if concept_id:
        await _update_bkt_mastery(concept_id, correct=(rating >= 3))

    # Daily stats
    await _increment_daily_reviews()

    return updated_row


async def get_due_cards_list() -> list[dict[str, Any]]:
    """Return all cards due for review, sorted by urgency.

    Returns:
        List of card row dicts where due <= now.
    """
    now_iso = datetime.now(UTC).isoformat()
    return await fsrs_store.async_get_due_review_cards(now_iso)


# ── Internal helpers ─────────────────────────────────────────────────────────


async def _update_bkt_mastery(concept_id: str, *, correct: bool) -> None:
    """Update BKT mastery for a concept after a review."""
    mastery = await fsrs_store.async_get_concept_mastery(concept_id)
    if mastery is None:
        state = BKTState.default()
    else:
        state = BKTState(
            p_know=mastery["p_know"],
            p_slip=mastery["p_slip"],
            p_guess=mastery["p_guess"],
            p_transit=mastery["p_transit"],
        )

    new_state = bkt_update(state, correct=correct)
    total = (mastery["total_attempts"] if mastery else 0) + 1
    correct_count = (mastery["correct_attempts"] if mastery else 0) + (1 if correct else 0)

    await fsrs_store.async_upsert_concept_mastery(
        {
            "concept_id": concept_id,
            "p_know": new_state.p_know,
            "p_slip": new_state.p_slip,
            "p_guess": new_state.p_guess,
            "p_transit": new_state.p_transit,
            "total_attempts": total,
            "correct_attempts": correct_count,
            "last_updated": datetime.now(UTC).isoformat(),
        }
    )


async def _increment_daily_reviews() -> None:
    """Increment today's review count in daily_stats."""
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
    stats["reviews_completed"] = stats["reviews_completed"] + 1
    await fsrs_store.async_upsert_daily_stats(stats)
