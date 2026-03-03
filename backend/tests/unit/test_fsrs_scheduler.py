from __future__ import annotations

import math

from fsrs import Card, Rating

from app.services.fsrs.scheduler import (
    card_from_row,
    card_to_row_update,
    cards_due,
    review_card,
    schedule_new_card,
)


class TestScheduleNewCard:
    """Tests for creating a fresh FSRS card."""

    def test_returns_card_instance(self) -> None:
        card = schedule_new_card()
        assert isinstance(card, Card)

    def test_new_card_is_new_state(self) -> None:
        card = schedule_new_card()
        d = card.to_dict()
        assert d["state"] in (0, 1)  # New/Learning state


class TestReviewCard:
    """Tests for applying a review to a card."""

    def test_review_good_returns_card(self) -> None:
        card = schedule_new_card()
        updated, due = review_card(card, Rating.Good)
        assert isinstance(updated, Card)

    def test_review_returns_due_date(self) -> None:
        card = schedule_new_card()
        _, due = review_card(card, Rating.Good)
        assert due is not None


class TestCardsDue:
    """Tests for filtering cards due for review."""

    def test_new_card_is_due(self) -> None:
        card = schedule_new_card()
        due = cards_due([card])
        assert len(due) == 1

    def test_reviewed_card_not_immediately_due(self) -> None:
        card = schedule_new_card()
        updated, _ = review_card(card, Rating.Easy)
        due = cards_due([updated])
        assert len(due) == 0


class TestCardRowConversion:
    """Tests for card_from_row and card_to_row_update roundtrips."""

    def _make_row(self) -> dict[str, object]:
        card = schedule_new_card()
        d = card.to_dict()
        return {
            "card_id": d.get("card_id", "test-123"),
            "front": "What is 2+2?",
            "back": "4",
            "concept_id": "arithmetic",
            "source_message_id": "msg-1",
            "session_id": "sess-1",
            "state": d["state"],
            "step": d.get("step", 0),
            "stability": d["stability"] if d["stability"] is not None else float("nan"),
            "difficulty": d["difficulty"] if d["difficulty"] is not None else float("nan"),
            "due": d["due"],
            "last_review": d.get("last_review") or "",
            "reps": 0,
            "lapses": 0,
            "created_at": "2025-01-01T00:00:00",
        }

    def test_roundtrip_new_card(self) -> None:
        row = self._make_row()
        card = card_from_row(row)
        assert isinstance(card, Card)

    def test_nan_stability_becomes_none(self) -> None:
        row = self._make_row()
        row["stability"] = float("nan")
        card = card_from_row(row)
        d = card.to_dict()
        assert d["stability"] is None

    def test_card_to_row_preserves_metadata(self) -> None:
        row = self._make_row()
        card = card_from_row(row)
        updated, _ = review_card(card, Rating.Good)
        new_row = card_to_row_update(updated, row)
        assert new_row["front"] == "What is 2+2?"
        assert new_row["back"] == "4"
        assert new_row["concept_id"] == "arithmetic"

    def test_card_to_row_updates_fsrs_state(self) -> None:
        row = self._make_row()
        card = card_from_row(row)
        updated, _ = review_card(card, Rating.Good)
        new_row = card_to_row_update(updated, row)
        assert "state" in new_row
        assert "due" in new_row

    def test_none_stability_becomes_nan_in_row(self) -> None:
        row = self._make_row()
        card = card_from_row(row)
        new_row = card_to_row_update(card, row)
        d = card.to_dict()
        if d["stability"] is None:
            assert math.isnan(new_row["stability"])
