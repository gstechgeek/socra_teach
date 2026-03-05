from __future__ import annotations

import logging
from functools import lru_cache

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Timeout for cloud embedding requests ─────────────────────────────────────
_CLOUD_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
_CLOUD_BATCH_SIZE = 128  # max texts per API call (OpenRouter/OpenAI limit)


# ── Local embedding ──────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _get_local_embedder():  # type: ignore[no-untyped-def]
    """Load and cache the local sentence-transformers embedding model.

    Import is deferred so sentence-transformers is not loaded when using
    the cloud provider, saving ~500 MB of RAM on the Steam Deck.

    Returns:
        A ready-to-use SentenceTransformer instance.
    """
    from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

    logger.info("Loading local embedding model: %s", settings.embedding_model)
    return SentenceTransformer(settings.embedding_model, trust_remote_code=True)


def _embed_local(texts: list[str]) -> list[list[float]]:
    """Embed texts using the local sentence-transformers model."""
    model = _get_local_embedder()
    vecs = model.encode(
        texts,
        normalize_embeddings=True,
        output_value="sentence_embedding",
    )
    # Truncate to Matryoshka reduced dimension
    return [v[: settings.embedding_dim].tolist() for v in vecs]


# ── Cloud embedding (OpenRouter) ─────────────────────────────────────────────


def _embed_cloud_batch(texts: list[str]) -> list[list[float]]:
    """Embed a single batch of texts via the OpenRouter embeddings API.

    Args:
        texts: List of strings to embed (should be ≤ ``_CLOUD_BATCH_SIZE``).

    Returns:
        List of float32 vectors, one per input string.

    Raises:
        httpx.HTTPStatusError: If the API returns a non-2xx response.
        ValueError: If the response is missing ``data`` or count doesn't match.
    """
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "https://github.com/socra-teach",
    }
    payload: dict[str, object] = {
        "model": settings.cloud_embedding_model,
        "input": texts,
        "dimensions": settings.embedding_dim,
    }

    with httpx.Client(timeout=_CLOUD_TIMEOUT) as client:
        response = client.post(
            f"{settings.openrouter_base_url}/embeddings",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

    body = response.json()
    if "data" not in body:
        logger.error("Unexpected API response (no 'data' key): %s", str(body)[:500])
        msg = f"Embedding API returned unexpected response: {str(body)[:200]}"
        raise ValueError(msg)

    data: list[dict[str, object]] = body["data"]
    # Sort by index defensively (OpenAI API may return out of order)
    data.sort(key=lambda item: item["index"])  # type: ignore[arg-type]

    if len(data) != len(texts):
        msg = f"Expected {len(texts)} embeddings, got {len(data)}"
        raise ValueError(msg)

    return [item["embedding"] for item in data]  # type: ignore[misc]


def _embed_cloud(texts: list[str]) -> list[list[float]]:
    """Embed texts via OpenRouter, automatically batching large inputs.

    Splits inputs into batches of ``_CLOUD_BATCH_SIZE`` to stay within
    API limits, then concatenates the results in order.

    Args:
        texts: List of strings to embed.

    Returns:
        List of float32 vectors (dimension controlled by ``settings.embedding_dim``).
    """
    if len(texts) <= _CLOUD_BATCH_SIZE:
        return _embed_cloud_batch(texts)

    all_vectors: list[list[float]] = []
    total_batches = (len(texts) + _CLOUD_BATCH_SIZE - 1) // _CLOUD_BATCH_SIZE
    for i in range(0, len(texts), _CLOUD_BATCH_SIZE):
        batch = texts[i : i + _CLOUD_BATCH_SIZE]
        batch_num = i // _CLOUD_BATCH_SIZE + 1
        logger.info("Cloud embedding batch %d/%d (%d texts)", batch_num, total_batches, len(batch))
        all_vectors.extend(_embed_cloud_batch(batch))
    return all_vectors


# ── Public API ───────────────────────────────────────────────────────────────


def get_embedder():  # type: ignore[no-untyped-def]
    """Load and cache the local embedding model (backward-compat helper).

    Used by the first-run setup script documented in CLAUDE.md.
    """
    return _get_local_embedder()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text strings into fixed-dim float32 vectors.

    Dispatches to local (sentence-transformers) or cloud (OpenRouter)
    based on ``settings.embedding_provider``.

    CPU/IO-bound — call via ``asyncio.to_thread()`` from async contexts.

    Args:
        texts: List of strings to embed.

    Returns:
        List of normalised float32 vectors, one per input string.
        Dimension is controlled by ``settings.embedding_dim`` (default 256).
    """
    provider = settings.embedding_provider
    logger.info(
        "Embedding %d text(s) via %s",
        len(texts),
        f"openrouter/{settings.cloud_embedding_model}" if provider == "openrouter" else "local",
    )
    if provider == "openrouter":
        return _embed_cloud(texts)
    return _embed_local(texts)
