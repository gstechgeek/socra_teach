from __future__ import annotations

from datetime import datetime

from fsrs import Card, Rating, Scheduler

_scheduler = Scheduler()


def schedule_new_card() -> Card:
    """Create a new FSRS card with default initial state.

    Returns:
        A freshly initialised FSRS Card ready for its first review.
    """
    return Card()


def review_card(card: Card, rating: Rating) -> tuple[Card, datetime]:
    """Apply a review rating and return the updated card and next due date.

    FSRS models each memory with Difficulty, Stability, and Retrievability
    and uses a power-law forgetting curve to schedule the next review.
    Achieves 20–30 % fewer reviews than SM-2 for the same retention level.

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
        Subset of cards whose due date is ≤ now, sorted by urgency.
    """
    now = datetime.utcnow()
    due = [c for c in cards if c.due <= now]
    return sorted(due, key=lambda c: c.due)
