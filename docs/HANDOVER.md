# Handover — socra_teach (2026-03-09)

## What's Done

### Phases Complete

| Phase | Status |
|-------|--------|
| 1 — Foundation (llama.cpp + FastAPI streaming) | Done |
| 2 — Socratic engine + cloud routing | Done |
| 3 — RAG pipeline (BM25 + vector + cross-encoder) | Done |
| 4 — PDF viewer + citations | Done |
| 5 — FSRS spaced repetition + BKT progress tracking | Done |
| 6 — Polish, optimization, advanced features | In progress |

### Recent Changes (this session)

1. **PDF rectangle selection** — implemented full-stack feature: `useRectSelect.ts` hook for mouse-drag, canvas pixel capture in `PdfViewer.tsx`, selection preview chip in `Chat.tsx`, multimodal OpenAI vision format in `router.py` via `_inject_selection_image()`.
2. **RAG page-first chunking** — replaced broken header-first chunking (only 2 page values across 824 chunks) with `_page_first_chunks()` in `ingestion.py` that processes each page independently, trivially preserving page numbers.
3. **Printed page labels** — added `_build_page_label_map()` and `_resolve_page_number()` using PyMuPDF's `page.get_label()` to map PDF page indices to printed page numbers (fixes ~8-page front matter offset).
4. **Page-aware retrieval** — `retriever.py` now parses page references from queries (`_PAGE_REF_RE`), injects chunks from mentioned pages, and applies +0.3 page boost in fusion scoring; BM25 tokens include `["page", str(page)]`.
5. **Document-scoped retrieval** — `retrieve()` accepts `doc_id` parameter; filters BM25 and vector results to the active textbook; frontend passes `activeDocId` through `useChat` → `ChatRequest` → `route_and_stream()` → `retrieve()`.
6. **Page-fit default zoom** — `PdfViewer.tsx` now uses `SpecialZoomLevel.PageFit` as `defaultScale`.
7. **README** — populated `README.md` with features, architecture diagram, setup instructions, usage guide, and development commands.
8. **Test fixes** — updated `test_ingestion.py` to use `_page_first_chunks` (removed references to deleted `_markdown_section_chunks` and `_find_page_at_position`); added test for section name inheritance across pages.
9. **Card generator JSON fix** — added brace-depth extraction fallback in `card_generator.py` for LLM responses with extra text after the JSON object.
10. **BM25 index expanded** — `get_all_chunk_texts()` now returns `(id, text, page, doc_id)` 4-tuples; `rebuild_bm25_index()` tracks `_bm25_doc_ids` parallel array for document filtering.

### Test & Build Status

- **Backend**: 110 tests passing; coverage 81.45% (above 80% target)
- **Lint**: Clean (`ruff check` passes on all changed files)
- **Frontend**: TypeScript compiles clean (`tsc --noEmit` passes)

### Committed Work

On branch `ZeroRAG`:
```
f7e81ed docs: update README with comprehensive application overview and features
411436d feat: implement PDF selection capture and multimodal chat integration
```

---

## Known Issues

### Must Fix

1. **Blank page on Textbooks and Progress tabs** — not yet root-caused; likely React runtime error.
2. **`type: ignore` suppressions in `progress.py:214-223`** — violates CLAUDE.md strict mypy rule.
3. **LanceDB `table_names()` deprecation** — 114 test warnings; needs `list_tables()`.
4. **"Connection lost" on first chat query** — response cut off mid-sentence; may be timeout or response length issue with claude-sonnet-4-5.
5. **PDF selection "Use as context" button** — `onMouseDown` stopPropagation fix applied but not manually verified by user (conversation moved to RAG work before confirmation).

### Should Fix

6. **Frontend bundle size** — 1,727 kB (Vite warns at 500 kB); needs code-splitting for pdfjs-dist.
7. **No frontend tests** — Vitest configured but zero test files.
8. **Local LLM dead code** — `llm.py`, `_stream_local_async()` unused at runtime.
9. **Cross-encoder loads on CPU** — ~10s re-ranking latency for 10 chunks; consider cloud re-ranking or disabling for simple queries.
10. **Re-ingest required** — existing LanceDB chunks use old chunking strategy (broken page numbers); re-upload textbooks to get page-first chunks with printed page labels.

---

## What's Left

### Phase 6 — In Progress

- Performance optimization (bundle splitting, lazy loading, cloud re-ranking evaluation)
- Memory budget verification (full-stack ≤ 7 GB)
- UI polish, accessibility, React error boundary
- Fix streaming connection loss issue
- Frontend test coverage
- Verify PDF selection feature end-to-end

---

## Key Architecture Decisions to Remember

| Decision | Context |
|----------|---------|
| Cloud-only tutor | Local 1B model too slow on shared VRAM; all queries go to claude-sonnet-4-5 |
| Cloud embedding via OpenRouter | Local nomic-embed too slow on CPU; OpenAI text-embedding-3-small via OpenRouter |
| Page-first chunking | Header-first chunking collapsed 497 pages into 2 sections; page-first processes each page independently |
| Printed page labels | PyMuPDF `page.get_label()` maps PDF page indices to printed page numbers (front matter offset) |
| Document-scoped retrieval | `active_doc_id` flows frontend → backend; retriever filters BM25/vector/page results by doc_id |
| Page-aware retrieval | BM25 tokens include page number; mentioned pages get +0.3 boost and direct chunk injection |
| Multimodal selection via OpenAI vision format | PDF rectangle captures sent as base64 PNG in `image_url` content parts to cloud LLM |
| LanceDB only (no Supabase yet) | Local-first; Supabase sync deferred |
| Background card gen via haiku | `asyncio.create_task()` after each chat turn; uses fast/cheap cloud tier |
| Citations are 1-indexed | Backend emits page numbers as-is from chunks; frontend converts to 0-indexed for `jumpToPage` |

---

## Files Changed (uncommitted)

```
M backend/app/api/routes/chat.py          — added active_doc_id to ChatRequest
M backend/app/services/rag/retriever.py   — doc_id filtering, _bm25_doc_ids, 4-tuple rebuild
M backend/app/services/rag/store.py       — get_all_chunk_texts returns (id, text, page, doc_id)
M backend/app/services/tutor/router.py    — passes active_doc_id to retrieve()
M backend/tests/unit/test_ingestion.py    — updated to use _page_first_chunks, added inheritance test
M frontend/src/App.tsx                    — passes activeDocId to useChat
M frontend/src/components/PdfViewer.tsx   — SpecialZoomLevel.PageFit default
M frontend/src/hooks/useChat.ts           — accepts activeDocId, sends active_doc_id in request
```

---

## Previous Session (2026-03-05)

1. Cloud embedding via OpenRouter — `_embed_cloud_batch()` in `embedder.py` for `openai/text-embedding-3-small`.
2. Automatic batching — cloud embedding splits large inputs into batches of 128.
3. Structured logging across all RAG modules.
4. Unit tests — `test_embedder.py` with 8 tests.
5. Wiped stale LanceDB vectors for re-ingestion with OpenAI embeddings.

## Previous Session (2026-03-04)

1. Cloud-only tutor routing — removed classifier-based routing; all queries go to claude-sonnet-4-5.
2. Graceful stream error handling — try/except/finally in chat.py, FatalSSEError in frontend.
3. Phase 4 citation linking — full implementation across backend and frontend.
4. Simplified TutorPage model badge.

## Previous Session (2026-03-03)

Previous session completed Phase 5 (FSRS + BKT) across two sprints: backend data layer, scheduler, card generator, progress routes, and frontend review UI + dashboard. See git log for committed work.
