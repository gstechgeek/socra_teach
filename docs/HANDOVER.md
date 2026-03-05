# Handover — socra_teach (2026-03-04)

## What's Done

### Phases Complete

| Phase | Status |
|-------|--------|
| 1 — Foundation (llama.cpp + FastAPI streaming) | Done |
| 2 — Socratic engine + cloud routing | Done |
| 3 — RAG pipeline (BM25 + vector + cross-encoder) | Done |
| 4 — PDF viewer + citations | Done (needs manual verification) |
| 5 — FSRS spaced repetition + BKT progress tracking | Done |
| 6 — Polish, optimization, advanced features | Not started |

### Recent Changes (this session)

1. **Cloud-only tutor routing** — removed classifier-based routing from `router.py`; all tutor queries now go to `anthropic/claude-sonnet-4-5` via `_TUTOR_TIER = "dialogue"` constant.
2. **Graceful stream error handling** — `chat.py` wraps token loop in `try/except/finally` so `done` SSE event always fires; frontend throws `FatalSSEError` to prevent auto-retry; amber warning banner in TutorPage.
3. **Bumped `max_tokens` 512 → 1024** in `config.py` for local model if ever re-enabled.
4. **Phase 4 citation linking** — full implementation:
   - Backend: `SourceRef`/`StreamSources` dataclasses in `router.py`, `sources` SSE event forwarded in `chat.py`, citation rule added to cloud prompt in `socratic.py`.
   - Frontend: `useChat.ts` handles `sources` event and exposes `SourceRef[]`; `Chat.tsx` parses `[p. N]` in markdown into clickable blue badges; `PdfViewer.tsx` accepts `targetPage` prop and calls `jumpToPage` via default-layout plugin; `App.tsx` lifted `useChat()` to bridge citations to PdfViewer; `TutorPage.tsx` renders source chips and threads `onCitationClick`.
5. **Simplified TutorPage model badge** — always purple, shows model name only.

### Test & Build Status

- **Backend**: 86 tests passing, 0 failures
- **Frontend**: builds successfully (1,727 kB bundle, chunk size warning from pdfjs-dist)
- **Lint**: 1 pre-existing ruff error in `reranker.py:51` (B905 `zip()` without `strict=`) — not introduced this session

### Committed Work

No new commits this session. All changes are uncommitted on `main`:
```
1f4c557 feat: add progress tracking features with concept graph and review session
6b208eb feat: enhance TutorPage with metadata display and update TypeScript configuration
810c929 feat: implement classifier for query intent routing and add unit tests
821bad6 feat: initialize frontend with React, Vite, and TypeScript
fe9a34b Add initial README with project title
```

---

## Known Issues

### Must Fix

1. **Blank page on Textbooks and Progress tabs** — reported by user but not yet root-caused; likely a runtime React error (no error boundary). The CSS/structure is unchanged from when it worked. Next session: check browser console for errors, add React error boundary.
2. **`type: ignore` suppressions in `progress.py:214-223`** — violates CLAUDE.md strict mypy rule; needs `cast()` or typed dict.
3. **LanceDB `table_names()` deprecation** — 114 test warnings; both `fsrs/store.py` and `rag/store.py` need `list_tables()`.
4. **Ruff B905 in `reranker.py:51`** — `zip()` without `strict=` parameter.

### Should Fix

5. **Frontend bundle size** — 1,727 kB (Vite warns at 500 kB); needs dynamic `import()` code-splitting for pdfjs-dist.
6. **No frontend tests** — Vitest + testing-library configured but zero test files exist.
7. **Backend coverage gaps** — `card_generator.py` and `fsrs/store.py` excluded from coverage; no integration tests for `chat.py` streaming or document upload.
8. **Local LLM dead code** — `llm.py`, `_stream_local_async()` in router are unused at runtime.

---

## What's Left

### Phase 4 — Verification Needed

- Citation linking code is complete but the **blank page bug** (issue #1) must be fixed first to verify the full flow: upload PDF → ask question → source chips appear → `[p. N]` badges in response → click jumps PDF viewer to page.

### Phase 6 — Not Started

- Performance optimization (bundle splitting, lazy loading)
- Memory budget verification (full-stack ≤ 7 GB)
- UI polish, accessibility, React error boundary
- Advanced features (TBD)

---

## Key Architecture Decisions to Remember

| Decision | Context |
|----------|---------|
| Cloud-only tutor | Local 1B model too slow on shared VRAM; all queries go to claude-sonnet-4-5 |
| Single tier (dialogue) | No per-message classifier routing; consistent model across conversation |
| LanceDB only (no Supabase yet) | Local-first; Supabase sync deferred |
| Background card gen via haiku | `asyncio.create_task()` after each chat turn; uses fast/cheap cloud tier |
| No retry on stream failure | Connection assumed stable; just handle drops gracefully |
| useChat lifted to App.tsx | Enables citation click bridging from Chat → PdfViewer across sibling panels |
| Citations are 1-indexed | Backend emits page numbers as-is from chunks; frontend converts to 0-indexed for `jumpToPage` |

---

## Files Changed (uncommitted)

```
CLAUDE.md                                — minor updates
backend/app/api/routes/chat.py           — try/except/finally, error SSE event, sources SSE event
backend/app/core/config.py               — max_tokens 512 → 1024
backend/app/services/tutor/router.py     — cloud-only routing, SourceRef/StreamSources, removed classifier dep
backend/app/services/tutor/socratic.py   — citation instruction rule when RAG context present
frontend/src/App.tsx                     — lifted useChat, targetPage state, citation click bridging
frontend/src/components/Chat.tsx         — [p. N] citation parsing, clickable badges, onCitationClick prop
frontend/src/components/PdfViewer.tsx    — targetPage prop, jumpToPage via defaultLayoutPlugin
frontend/src/hooks/useChat.ts            — SourceRef, sources state, FatalSSEError, exported UseChatReturn
frontend/src/pages/TutorPage.tsx         — accepts chat/onCitationClick props, source chips row
docs/HANDOVER.md                         — this file (new)
```

---

## Previous Session (2026-03-03)

Previous session completed Phase 5 (FSRS + BKT) across two sprints: backend data layer, scheduler, card generator, progress routes, and frontend review UI + dashboard. See git log for committed work.
