from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/concepts")
async def get_concepts() -> dict[str, object]:
    """Return the concept graph with per-concept BKT mastery levels.

    Returns a directed acyclic graph where each concept node includes
    its p_know probability (from BKT) and prerequisite edges.

    Returns:
        Dict with "concepts" list and "edges" list of prerequisite pairs.
    """
    # TODO Phase 5: query concept_mastery table via Supabase
    raise NotImplementedError


@router.get("/cards/due")
async def get_due_cards() -> list[dict[str, object]]:
    """Return FSRS review cards that are due today, sorted by urgency.

    Returns:
        List of card dicts — each includes FSRS state fields
        (state, due, stability, difficulty, reps, lapses).
    """
    # TODO Phase 5: query review_cards via py-fsrs scheduler
    raise NotImplementedError


@router.post("/cards/{card_id}/review")
async def submit_review(card_id: str, rating: int) -> dict[str, object]:
    """Submit a review outcome for an FSRS flashcard.

    Args:
        card_id: The card identifier.
        rating: FSRS rating — 1=Again, 2=Hard, 3=Good, 4=Easy.

    Returns:
        Updated card state with next due date and new stability value.
    """
    # TODO Phase 5
    raise NotImplementedError


@router.get("/stats")
async def get_daily_stats() -> dict[str, object]:
    """Return today's learning stats (reviews, streak, session minutes).

    Returns:
        Dict with reviews_completed, streak_days, session_minutes.
    """
    # TODO Phase 5: query daily_stats table
    raise NotImplementedError
