from __future__ import annotations

import uuid as uuid_mod
from unittest.mock import patch

import pytest

from app.services.fsrs import store as fsrs_store


@pytest.fixture(autouse=True)
def _temp_lancedb(tmp_path):  # type: ignore[no-untyped-def]
    """Point LanceDB at a unique temp directory for each test."""
    import lancedb

    unique_dir = tmp_path / f"lance_{uuid_mod.uuid4().hex[:8]}"
    _db = lancedb.connect(str(unique_dir))
    with (
        patch("app.services.rag.store.get_db", return_value=_db),
        patch("app.services.fsrs.store.get_db", return_value=_db),
    ):
        yield


class TestReviewCards:
    """CRUD tests for review_cards table."""

    def _card(self, card_id: str = "c1") -> dict[str, object]:
        return {
            "card_id": card_id,
            "front": "Q?",
            "back": "A.",
            "concept_id": "con1",
            "source_message_id": "msg1",
            "session_id": "s1",
            "state": 0,
            "step": 0,
            "stability": float("nan"),
            "difficulty": float("nan"),
            "due": "2025-01-01T00:00:00",
            "last_review": "",
            "reps": 0,
            "lapses": 0,
            "created_at": "2025-01-01T00:00:00",
        }

    def test_upsert_and_get(self) -> None:
        fsrs_store.upsert_review_card(self._card())
        result = fsrs_store.get_review_card("c1")
        assert result is not None
        assert result["front"] == "Q?"

    def test_get_nonexistent_returns_none(self) -> None:
        assert fsrs_store.get_review_card("missing") is None

    def test_get_all(self) -> None:
        fsrs_store.upsert_review_card(self._card("c1"))
        fsrs_store.upsert_review_card(self._card("c2"))
        all_cards = fsrs_store.get_all_review_cards()
        assert len(all_cards) == 2

    def test_upsert_replaces(self) -> None:
        fsrs_store.upsert_review_card(self._card())
        updated = self._card()
        updated["front"] = "Updated?"
        fsrs_store.upsert_review_card(updated)
        result = fsrs_store.get_review_card("c1")
        assert result is not None
        assert result["front"] == "Updated?"
        assert len(fsrs_store.get_all_review_cards()) == 1

    def test_delete(self) -> None:
        fsrs_store.upsert_review_card(self._card())
        fsrs_store.delete_review_card("c1")
        assert fsrs_store.get_review_card("c1") is None

    def test_due_filter(self) -> None:
        card = self._card()
        card["due"] = "2025-01-01T00:00:00"
        fsrs_store.upsert_review_card(card)
        due = fsrs_store.get_due_review_cards("2025-06-01T00:00:00")
        assert len(due) == 1
        not_due = fsrs_store.get_due_review_cards("2024-01-01T00:00:00")
        assert len(not_due) == 0


class TestConcepts:
    """CRUD tests for concepts table."""

    def _concept(self, cid: str = "con1") -> dict[str, object]:
        return {
            "concept_id": cid,
            "name": "test_concept",
            "description": "A test concept",
            "source_doc_id": "doc1",
            "created_at": "2025-01-01T00:00:00",
        }

    def test_upsert_and_get(self) -> None:
        fsrs_store.upsert_concept(self._concept())
        result = fsrs_store.get_concept("con1")
        assert result is not None
        assert result["name"] == "test_concept"

    def test_get_by_name(self) -> None:
        fsrs_store.upsert_concept(self._concept())
        result = fsrs_store.get_concept_by_name("test_concept")
        assert result is not None
        assert result["concept_id"] == "con1"

    def test_get_by_name_missing(self) -> None:
        assert fsrs_store.get_concept_by_name("nonexistent") is None


class TestConceptMastery:
    """CRUD tests for concept_mastery table."""

    def _mastery(self, cid: str = "con1") -> dict[str, object]:
        return {
            "concept_id": cid,
            "p_know": 0.5,
            "p_slip": 0.1,
            "p_guess": 0.25,
            "p_transit": 0.3,
            "total_attempts": 5,
            "correct_attempts": 3,
            "last_updated": "2025-01-01T00:00:00",
        }

    def test_upsert_and_get(self) -> None:
        fsrs_store.upsert_concept_mastery(self._mastery())
        result = fsrs_store.get_concept_mastery("con1")
        assert result is not None
        assert result["p_know"] == pytest.approx(0.5)

    def test_get_all(self) -> None:
        fsrs_store.upsert_concept_mastery(self._mastery("con1"))
        fsrs_store.upsert_concept_mastery(self._mastery("con2"))
        all_m = fsrs_store.get_all_concept_mastery()
        assert len(all_m) == 2


class TestDailyStats:
    """CRUD tests for daily_stats table."""

    def _stats(self, dt: str = "2025-01-15") -> dict[str, object]:
        return {
            "date": dt,
            "reviews_completed": 10,
            "cards_created": 3,
            "concepts_learned": 2,
            "streak_days": 5,
            "session_minutes": 45,
        }

    def test_upsert_and_get(self) -> None:
        fsrs_store.upsert_daily_stats(self._stats())
        result = fsrs_store.get_daily_stats("2025-01-15")
        assert result is not None
        assert result["reviews_completed"] == 10

    def test_stats_range(self) -> None:
        fsrs_store.upsert_daily_stats(self._stats("2025-01-14"))
        fsrs_store.upsert_daily_stats(self._stats("2025-01-15"))
        fsrs_store.upsert_daily_stats(self._stats("2025-01-16"))
        results = fsrs_store.get_stats_range("2025-01-14", "2025-01-15")
        assert len(results) == 2
