from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

from app.core.config import settings


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    """Load and cache the nomic-embed-text-v1.5 embedding model.

    Loaded once at first call and reused across all requests.
    trust_remote_code=True is required by nomic-embed-text-v1.5.

    Returns:
        A ready-to-use SentenceTransformer instance.
    """
    return SentenceTransformer(settings.embedding_model, trust_remote_code=True)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text strings into 256-dim float32 vectors.

    CPU-bound — call via asyncio.to_thread() from async contexts to avoid
    blocking the FastAPI event loop.

    Uses Matryoshka representation: the model outputs 768-dim vectors but
    the first 256 dimensions are used (controlled by settings.embedding_dim).

    Args:
        texts: List of strings to embed.

    Returns:
        List of normalised 256-dim float32 vectors, one per input string.
    """
    model = get_embedder()
    vecs = model.encode(
        texts,
        normalize_embeddings=True,
        output_value="sentence_embedding",
    )
    # Truncate to Matryoshka reduced dimension
    return [v[: settings.embedding_dim].tolist() for v in vecs]
