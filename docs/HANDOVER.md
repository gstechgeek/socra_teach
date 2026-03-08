# Handover — socra_teach (2026-03-05)

## What's Done

### Phases Complete

| Phase | Status |
|-------|--------|
| 1 — Foundation (llama.cpp + FastAPI streaming) | Done |
| 2 — Socratic engine + cloud routing | Done |
| 3 — RAG pipeline (BM25 + vector + cross-encoder) | Done |
| 4 — PDF viewer + citations | Done (needs manual verification) |
| 5 — FSRS spaced repetition + BKT progress tracking | Done |
| 6 — Polish, optimization, advanced features | In progress |

### Recent Changes (this session)

1. **Cloud embedding via OpenRouter** — added `_embed_cloud_batch()` and `_embed_cloud()` to `embedder.py`; dispatches to `openai/text-embedding-3-small` (or `text-embedding-3-large`) via OpenRouter's `/embeddings` endpoint based on `settings.embedding_provider`.
2. **Automatic batching** — cloud embedding splits large inputs into batches of 128 to stay within API limits; fixed `KeyError: 'data'` crash when sending all 824 chunks in a single request.
3. **Config additions** — added `embedding_provider` and `cloud_embedding_model` to `config.py`; default set to `"openrouter"`.
4. **Structured logging across all RAG modules** — added `logger = logging.getLogger(__name__)` and INFO-level logging to `embedder.py`, `ingestion.py`, `store.py`, `retriever.py`, `reranker.py`; added `logging.basicConfig()` to `main.py`.
5. **Fixed silent exception swallowing** — changed `ingestion.py` exception handler from `str(exc)` only to `logger.exception()` for full tracebacks.
6. **Fixed ruff B905** — added `strict=True` to `zip(scores, chunks)` in `reranker.py`.
7. **Unit tests** — created `tests/unit/test_embedder.py` with 8 tests covering dispatch, cloud batching, error handling, and payload verification.
8. **Wiped stale LanceDB vectors** — deleted `chunks.lance` and `documents.lance` tables that had incompatible nomic-embed vectors; user re-ingested with OpenAI embeddings.
9. **Updated `.env.example`** — documented `EMBEDDING_PROVIDER` and `CLOUD_EMBEDDING_MODEL`.

### Test & Build Status

- **Backend**: 8 embedder tests passing; 102 total tests passing (coverage failure is pre-existing — 9.27% vs 80% target due to untested modules)
- **Lint**: Clean (`ruff check` passes on all changed files)

### Committed Work

On branch `ZeroRAG`:
```
c9e4037 feat: enhance embedding provider with local and cloud options, add logging, and implement unit tests
```

---

## Known Issues

### Must Fix

1. **Blank page on Textbooks and Progress tabs** — not yet root-caused; likely React runtime error.
2. **`type: ignore` suppressions in `progress.py:214-223`** — violates CLAUDE.md strict mypy rule.
3. **LanceDB `table_names()` deprecation** — 114 test warnings; needs `list_tables()`.
4. **Backend coverage at 9.27%** — far below 80% target; `health.py`, `main.py`, `scheduler.py`, `bkt.py`, `classifier.py`, `socratic.py` have 0% coverage.
5. **"Connection lost" on first chat query** — streaming rINFO:     127.0.0.1:56454 - "POST /api/chat/stream HTTP/1.1" 200 OK
14:14:10  INFO      app.services.rag.retriever  Retrieving top-10 for query: what are the contents of this book?…
14:14:10  INFO      app.services.rag.embedder  Embedding 1 text(s) via openrouter/openai/text-embedding-3-small
14:14:11  INFO      httpx  HTTP Request: POST https://openrouter.ai/api/v1/embeddings "HTTP/1.1 200 OK"
14:14:12  INFO      app.services.rag.retriever  Retrieved 10 chunk(s), top score=0.6000
14:14:12  INFO      app.services.rag.reranker  Re-ranking 10 chunk(s) for query: what are the contents of this book?…
14:14:19  INFO      sentence_transformers.cross_encoder.CrossEncoder  Use pytorch device: cpu
Batches: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1/1 [00:01<00:00,  1.12s/it]
14:14:22  INFO      app.services.rag.reranker  Re-ranking complete — returning top 3
INFO:     127.0.0.1:60176 - "POST /api/chat/stream HTTP/1.1" 200 OK
14:39:02  INFO      app.services.rag.retriever  Retrieving top-10 for query: What are the contents of the book?…
14:39:02  INFO      app.services.rag.embedder  Embedding 1 text(s) via openrouter/openai/text-embedding-3-small
14:39:04  INFO      httpx  HTTP Request: POST https://openrouter.ai/api/v1/embeddings "HTTP/1.1 200 OK"
14:39:05  INFO      app.services.rag.retriever  Retrieved 10 chunk(s), top score=0.6000
14:39:05  INFO      app.services.rag.reranker  Re-ranking 10 chunk(s) for query: What are the contents of the book?…
Batches: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1/1 [00:01<00:00,  1.16s/it]
14:39:06  INFO      app.services.rag.reranker  Re-ranking complete — returning top 3
14:39:10  INFO      httpx  HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"esponse cut off mid-sentence ("Looking at problem 5.26(a) on (p"); may be a timeout or response length issue with claude-sonnet-4-5.

### Should Fix

6. **Frontend bundle size** — 1,727 kB (Vite warns at 500 kB); needs code-splitting for pdfjs-dist.
7. **No frontend tests** — Vitest configured but zero test files.
8. **Local LLM dead code** — `llm.py`, `_stream_local_async()` unused at runtime.
9. **Cross-encoder loads on CPU** — ~10s re-ranking latency for 10 chunks; consider cloud re-ranking or disabling for simple queries.

---

## What's Left

### Phase 6 — In Progress

- Performance optimization (bundle splitting, lazy loading, cloud re-ranking evaluation)
- Memory budget verification (full-stack ≤ 7 GB)
- UI polish, accessibility, React error boundary
- Fix streaming connection loss issue
- Backend test coverage improvement

---

## Key Architecture Decisions to Remember

| Decision | Context |
|----------|---------|
| Cloud-only tutor | Local 1B model too slow on shared VRAM; all queries go to claude-sonnet-4-5 |
| Cloud embedding via OpenRouter | Local nomic-embed too slow on CPU (~70-80% of ingestion time); OpenAI text-embedding-3-small via OpenRouter cuts embedding to ~6s for 824 chunks |
| Sync httpx for cloud embedding | Both call sites (ingestion thread, retriever thread) are sync; async httpx would require restructuring |
| Deferred sentence-transformers import | Saves ~500 MB RAM when using cloud embedding provider |
| Batch size 128 for cloud embedding | OpenRouter/OpenAI has payload limits; 824 chunks → 7 batches |
| LanceDB only (no Supabase yet) | Local-first; Supabase sync deferred |
| Background card gen via haiku | `asyncio.create_task()` after each chat turn; uses fast/cheap cloud tier |
| Citations are 1-indexed | Backend emits page numbers as-is from chunks; frontend converts to 0-indexed for `jumpToPage` |

---

## Files Changed (uncommitted)

```
(none — working tree clean)
```

---

## Previous Session (2026-03-04)

1. Cloud-only tutor routing — removed classifier-based routing; all queries go to claude-sonnet-4-5.
2. Graceful stream error handling — try/except/finally in chat.py, FatalSSEError in frontend.
3. Phase 4 citation linking — full implementation across backend and frontend.
4. Simplified TutorPage model badge.

## Previous Session (2026-03-03)

Previous session completed Phase 5 (FSRS + BKT) across two sprints: backend data layer, scheduler, card generator, progress routes, and frontend review UI + dashboard. See git log for committed work.
