from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All values can be overridden by a .env file placed in backend/
    or by real environment variables (env vars take precedence).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Local LLM ─────────────────────────────────────────────────────────────
    model_path: str = "../models/llama-3.2-1b-instruct-q4_k_m.gguf"
    n_ctx: int = 4096  # NEVER increase beyond 4096 (KV cache OOM on 16 GB)
    n_gpu_layers: int = -1  # -1 = offload all layers to Vulkan
    max_tokens: int = 1024

    # ── OpenRouter (cloud LLM tiers) ──────────────────────────────────────────
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    cloud_model_dialogue: str = "anthropic/claude-sonnet-4-5"
    cloud_model_reasoning: str = "deepseek/deepseek-r1"
    cloud_model_fast: str = "anthropic/claude-haiku-4-5"

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_provider: str = "openrouter"  # "local" (sentence-transformers) or "openrouter"
    embedding_model: str = "nomic-ai/nomic-embed-text-v1.5"
    cloud_embedding_model: str = "openai/text-embedding-3-small"
    embedding_dim: int = 256  # Matryoshka reduced dimension

    # ── Vector store ──────────────────────────────────────────────────────────
    lancedb_path: str = "../data/lancedb"

    # ── Supabase ──────────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_key: str = ""

    # ── Ingestion ──────────────────────────────────────────────────────────────
    ingestion_timeout: int = 300  # seconds before PDF parsing is aborted

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
