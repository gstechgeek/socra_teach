from __future__ import annotations

import uuid as uuid_mod
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
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


@pytest.fixture()
def client(_temp_lancedb) -> TestClient:  # type: ignore[no-untyped-def]
    """Create a test client with a temp LanceDB."""
    from app.main import app

    return TestClient(app)


class TestGetConcepts:
    """Tests for GET /api/progress/concepts."""

    def test_empty_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/progress/concepts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["concepts"] == []
        assert data["edges"] == []


class TestGetDueCards:
    """Tests for GET /api/progress/cards/due."""

    def test_empty_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/progress/cards/due")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetAllCards:
    """Tests for GET /api/progress/cards."""

    def test_empty_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/progress/cards")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetCard:
    """Tests for GET /api/progress/cards/{card_id}."""

    def test_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/progress/cards/nonexistent")
        assert resp.status_code == 404


class TestSubmitReview:
    """Tests for POST /api/progress/cards/{card_id}/review."""

    def test_missing_card_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/progress/cards/nonexistent/review",
            json={"rating": 3, "duration_ms": 1000},
        )
        assert resp.status_code == 404

    def test_invalid_rating_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/progress/cards/some-id/review",
            json={"rating": 5, "duration_ms": 0},
        )
        assert resp.status_code == 422


class TestGetStats:
    """Tests for GET /api/progress/stats."""

    def test_empty_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/progress/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "today" in data
        assert "history" in data
        assert data["today"]["reviews_completed"] == 0
