# AGENTS.md — Socratic AI Tutor

Agent-facing reference for Codex, Gemini CLI, and any other AI coding assistant. Keep responses consistent with the architecture and constraints documented here.

---

## What This Project Is

A local-first Socratic tutoring app running on Steam Deck OLED. Uses llama.cpp (Vulkan) for local inference, tiered cloud fallbacks via OpenRouter (`anthropic/claude-sonnet-4-5`, `deepseek/deepseek-r1`, `anthropic/claude-haiku-4-5`), FastAPI + SSE for streaming responses, React/Vite for the UI, LanceDB for vector search, and Supabase for auth and cloud sync.

---

## Repository Layout

```
socra_teach/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # HTTP route handlers (chat, documents, progress)
│   │   ├── core/             # config.py (settings), llm.py (llama.cpp wrapper)
│   │   └── services/
│   │       ├── rag/          # retriever.py, reranker.py
│   │       ├── tutor/        # socratic.py, router.py (local↔cloud)
│   │       └── fsrs/         # scheduler.py (py-fsrs + BKT)
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   └── pyproject.toml
├── frontend/
│   ├── src/                  # React + TypeScript source
│   ├── package.json
│   └── vite.config.ts
├── models/                   # .gitignored — GGUF model files
├── data/                     # .gitignored — LanceDB index, uploaded PDFs
└── scripts/                  # setup and migration scripts
```

---

## Commands

### Safe to run (read-only / non-destructive)

```bash
# Backend (from backend/)
uv run pytest tests/unit/          # unit tests only
uv run ruff check .                # lint check (no file writes)
uv run mypy app/                   # type check

# Frontend (from frontend/)
npm run test                       # Vitest
npm run lint                       # ESLint check
```

### Mutating / starts servers

```bash
# Backend (from backend/)
uv sync                            # installs / updates deps from pyproject.toml
uv run uvicorn app.main:app --reload --port 8000   # dev server
uv run pytest                      # full suite (unit + integration)
uv run ruff format .               # auto-format files

# Frontend (from frontend/)
npm install                        # install dependencies
npm run dev                        # Vite dev server (http://localhost:5173)
npm run build                      # production build
```

---

## Architecture Snapshot

| Layer | Stack |
|-------|-------|
| Local LLM | Llama 3.2-1B Q4_K_M / llama.cpp / Vulkan |
| Cloud API | OpenRouter (`openrouter.ai/api/v1`) — single key, OpenAI-compatible |
| Cloud tier 1 | `anthropic/claude-sonnet-4-5` — complex dialogue |
| Cloud tier 2 | `deepseek/deepseek-r1` — math / STEM reasoning |
| Cloud tier 3 | `anthropic/claude-haiku-4-5` — fast / cheap fallback |
| LLM Router | `services/tutor/router.py` — intent → local or cloud tier |
| Embeddings | nomic-embed-text-v1.5 |
| RAG | BM25 (0.6) + vector (0.4) + cross-encoder re-rank; LanceDB |
| Backend | Python 3.11 / FastAPI / sse-starlette |
| Frontend | React 18 / TypeScript strict / Vite |
| Database | Supabase (PostgreSQL + pgvector + Auth + RLS) |
| Scheduling | py-fsrs (FSRS) + BKT knowledge tracing |
| Container | Distrobox Ubuntu 24.04 via Podman (on SteamOS) |

---

## Hard Constraints

- `n_ctx` ≤ 4096 — KV cache causes OOM above this on 16 GB shared RAM
- Vulkan only — no ROCm, no CUDA (AMD RDNA2 iGPU)
- `async/await` throughout FastAPI — no blocking I/O on the event loop
- Use `httpx` for async HTTP — never `requests`
- Do NOT commit: `.gguf` files, LanceDB indexes, `.env`, or any API keys
- Total RAM budget: ≤ 7 GB with model loaded and full stack running

---

## Branch & Commit Conventions

- Branches: `feature/phase-N-description` | `fix/description` | `test/description`
- Commits: Conventional Commits — `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `perf:`
- All merges to `main` via PR — no direct pushes

---

## QA Gates (all must pass before merging a feature)

1. `uv run pytest` — all tests pass
2. `uv run ruff check .` — zero lint errors
3. `uv run mypy app/` — zero type errors
4. Backend coverage ≥ 80% for `backend/app/`
5. RAM ≤ 7 GB with model loaded
6. Local LLM ≥ 20 tok/s on Vulkan (Phase close gate only)

---

## Phase Map

| Phase | Scope |
|-------|-------|
| 1 | llama.cpp + FastAPI streaming chat (Foundation) |
| 2 | Socratic engine + cloud LLM routing |
| 3 | RAG pipeline — ingestion, retrieval, re-ranking |
| 4 | PDF viewer + in-context citations |
| 5 | FSRS spaced repetition + BKT progress tracking |
| 6 | Polish, optimization, advanced features |
