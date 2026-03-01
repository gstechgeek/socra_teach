from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_shape() -> None:
    """Health endpoint returns the correct shape regardless of service availability."""
    response = client.get("/health")
    assert response.status_code in (200, 503)

    body = response.json()
    assert body["status"] in ("ok", "degraded")

    for key in ("local_llm", "openrouter", "supabase", "lancedb"):
        svc = body["services"][key]
        assert svc["status"] in ("ok", "error", "not_initialized"), (
            f"{key} has unexpected status: {svc['status']}"
        )
        assert isinstance(svc["detail"], str), f"{key} detail must be a string"


def test_openapi_schema_is_accessible() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "paths" in response.json()
