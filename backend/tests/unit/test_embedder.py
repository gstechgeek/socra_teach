"""Unit tests for the embedding provider dispatch and cloud embedding logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ── Dispatch tests ───────────────────────────────────────────────────────────


class TestEmbedTextsDispatch:
    """embed_texts() dispatches to local or cloud based on embedding_provider."""

    @patch("app.services.rag.embedder._embed_local")
    @patch("app.services.rag.embedder.settings")
    def test_local_dispatch(self, mock_settings: MagicMock, mock_local: MagicMock) -> None:
        mock_settings.embedding_provider = "local"
        mock_local.return_value = [[0.1] * 256]

        from app.services.rag.embedder import embed_texts

        result = embed_texts(["hello"])

        mock_local.assert_called_once_with(["hello"])
        assert result == [[0.1] * 256]

    @patch("app.services.rag.embedder._embed_cloud")
    @patch("app.services.rag.embedder.settings")
    def test_openrouter_dispatch(self, mock_settings: MagicMock, mock_cloud: MagicMock) -> None:
        mock_settings.embedding_provider = "openrouter"
        mock_cloud.return_value = [[0.2] * 256]

        from app.services.rag.embedder import embed_texts

        result = embed_texts(["hello"])

        mock_cloud.assert_called_once_with(["hello"])
        assert result == [[0.2] * 256]


# ── Cloud embedding tests ────────────────────────────────────────────────────


class TestEmbedCloud:
    """Cloud embedding via the OpenRouter /embeddings endpoint."""

    def _make_mock_client(self, response_data: dict[str, object]) -> MagicMock:
        """Create a mock httpx.Client context manager with a preset response."""
        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        return mock_client

    @patch("app.services.rag.embedder.httpx.Client")
    @patch("app.services.rag.embedder.settings")
    def test_successful_embedding(
        self, mock_settings: MagicMock, mock_client_cls: MagicMock
    ) -> None:
        mock_settings.openrouter_api_key = "sk-test"
        mock_settings.openrouter_base_url = "https://openrouter.ai/api/v1"
        mock_settings.cloud_embedding_model = "openai/text-embedding-3-small"
        mock_settings.embedding_dim = 256

        mock_client = self._make_mock_client({
            "data": [
                {"embedding": [0.1] * 256, "index": 0},
                {"embedding": [0.2] * 256, "index": 1},
            ]
        })
        mock_client_cls.return_value = mock_client

        from app.services.rag.embedder import _embed_cloud_batch

        result = _embed_cloud_batch(["text1", "text2"])

        assert len(result) == 2
        assert result[0] == [0.1] * 256
        assert result[1] == [0.2] * 256

    @patch("app.services.rag.embedder.httpx.Client")
    @patch("app.services.rag.embedder.settings")
    def test_response_count_mismatch_raises(
        self, mock_settings: MagicMock, mock_client_cls: MagicMock
    ) -> None:
        mock_settings.openrouter_api_key = "sk-test"
        mock_settings.openrouter_base_url = "https://openrouter.ai/api/v1"
        mock_settings.cloud_embedding_model = "openai/text-embedding-3-small"
        mock_settings.embedding_dim = 256

        mock_client = self._make_mock_client({
            "data": [{"embedding": [0.1] * 256, "index": 0}]
        })
        mock_client_cls.return_value = mock_client

        from app.services.rag.embedder import _embed_cloud_batch

        with pytest.raises(ValueError, match="Expected 2 embeddings, got 1"):
            _embed_cloud_batch(["text1", "text2"])

    @patch("app.services.rag.embedder.httpx.Client")
    @patch("app.services.rag.embedder.settings")
    def test_out_of_order_response_sorted(
        self, mock_settings: MagicMock, mock_client_cls: MagicMock
    ) -> None:
        """Embeddings returned out of order are sorted by index."""
        mock_settings.openrouter_api_key = "sk-test"
        mock_settings.openrouter_base_url = "https://openrouter.ai/api/v1"
        mock_settings.cloud_embedding_model = "openai/text-embedding-3-small"
        mock_settings.embedding_dim = 256

        mock_client = self._make_mock_client({
            "data": [
                {"embedding": [0.9] * 256, "index": 1},
                {"embedding": [0.1] * 256, "index": 0},
            ]
        })
        mock_client_cls.return_value = mock_client

        from app.services.rag.embedder import _embed_cloud_batch

        result = _embed_cloud_batch(["text1", "text2"])

        assert result[0] == [0.1] * 256
        assert result[1] == [0.9] * 256

    @patch("app.services.rag.embedder.httpx.Client")
    @patch("app.services.rag.embedder.settings")
    def test_sends_correct_payload(
        self, mock_settings: MagicMock, mock_client_cls: MagicMock
    ) -> None:
        """Verify the request payload includes model, input, and dimensions."""
        mock_settings.openrouter_api_key = "sk-test"
        mock_settings.openrouter_base_url = "https://openrouter.ai/api/v1"
        mock_settings.cloud_embedding_model = "openai/text-embedding-3-large"
        mock_settings.embedding_dim = 256

        mock_client = self._make_mock_client({
            "data": [{"embedding": [0.5] * 256, "index": 0}]
        })
        mock_client_cls.return_value = mock_client

        from app.services.rag.embedder import _embed_cloud_batch

        _embed_cloud_batch(["hello"])

        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "https://openrouter.ai/api/v1/embeddings"
        payload = call_kwargs[1]["json"]
        assert payload["model"] == "openai/text-embedding-3-large"
        assert payload["input"] == ["hello"]
        assert payload["dimensions"] == 256
        headers = call_kwargs[1]["headers"]
        assert headers["Authorization"] == "Bearer sk-test"

    @patch("app.services.rag.embedder.httpx.Client")
    @patch("app.services.rag.embedder.settings")
    def test_missing_data_key_raises(
        self, mock_settings: MagicMock, mock_client_cls: MagicMock
    ) -> None:
        """API response without 'data' key raises ValueError with body info."""
        mock_settings.openrouter_api_key = "sk-test"
        mock_settings.openrouter_base_url = "https://openrouter.ai/api/v1"
        mock_settings.cloud_embedding_model = "openai/text-embedding-3-small"
        mock_settings.embedding_dim = 256

        mock_client = self._make_mock_client({"error": {"message": "rate limited"}})
        mock_client_cls.return_value = mock_client

        from app.services.rag.embedder import _embed_cloud_batch

        with pytest.raises(ValueError, match="unexpected response"):
            _embed_cloud_batch(["hello"])

    @patch("app.services.rag.embedder._embed_cloud_batch")
    @patch("app.services.rag.embedder._CLOUD_BATCH_SIZE", 2)
    def test_batching_splits_large_inputs(self, mock_batch: MagicMock) -> None:
        """_embed_cloud splits inputs larger than _CLOUD_BATCH_SIZE into batches."""
        mock_batch.side_effect = [
            [[0.1] * 256, [0.2] * 256],
            [[0.3] * 256],
        ]

        from app.services.rag.embedder import _embed_cloud

        result = _embed_cloud(["a", "b", "c"])

        assert mock_batch.call_count == 2
        assert len(result) == 3
        assert result[2] == [0.3] * 256
