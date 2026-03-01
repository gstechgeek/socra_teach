# CLAUDE.md — Socratic AI Tutor

This file configures Claude Code for the `socra_teach` project. Read it fully before making any suggestions or edits.

---

## Project Overview

Socratic AI Tutor is a local-first, privacy-preserving tutoring application that runs on a Steam Deck OLED. It uses a quantized Llama 3.2-1B model via llama.cpp (Vulkan backend) for primary inference, with three tiered cloud fallbacks served through a single OpenRouter API key: `anthropic/claude-sonnet-4-5` for complex Socratic dialogue, `deepseek/deepseek-r1` for math and STEM reasoning chains, and `anthropic/claude-haiku-4-5` as a fast cheap tier for lighter cloud queries. The Socratic method — answering questions with guiding questions — is the pedagogical core. A hybrid RAG pipeline (BM25 + vector search + cross-encoder re-ranking) grounds responses in user-uploaded textbooks. FSRS-based spaced repetition and BKT knowledge tracing close the learning loop.

---

## Development Environment

- **Platform**: Steam Deck OLED (SteamOS); all Python work runs inside Distrobox (Ubuntu 24.04 via Podman)
- **Hardware**: 16 GB shared RAM, AMD RDNA2 iGPU — **Vulkan only. No ROCm. No CUDA.**
- **Python**: 3.11+, managed by `uv`
- **Node**: 20 LTS

---

## Repository Structure

```
socra_teach/
├── .github/
│   └── copilot-instructions.md
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/            # chat.py, documents.py, progress.py
│   │   ├── core/                  # config.py (settings), llm.py (llama.cpp wrapper)
│   │   ├── services/
│   │   │   ├── rag/               # retriever.py, reranker.py
│   │   │   ├── tutor/             # socratic.py (prompt engine), router.py (local↔cloud)
│   │   │   └── fsrs/              # scheduler.py (py-fsrs + BKT)
│   │   └── main.py
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── models/                        # .gitignored — GGUF model files live here
├── data/                          # .gitignored — LanceDB index, uploaded PDFs
├── scripts/                       # setup.sh, migrate.py, etc.
├── docs/
├── .env.example
├── AGENTS.md
└── CLAUDE.md
```

---

## Key Commands

### Backend (run from `backend/`)

```bash
uv sync                                              # install / sync dependencies
uv run uvicorn app.main:app --reload --port 8000     # dev server
uv run pytest                                        # full test suite
uv run pytest tests/unit/                            # unit tests only
uv run pytest tests/integration/                     # integration tests only
uv run ruff check . && uv run ruff format --check .  # lint + format check
uv run mypy app/                                     # type check
```

### Frontend (run from `frontend/`)

```bash
npm install       # install dependencies
npm run dev       # Vite dev server (http://localhost:5173)
npm run build     # production build
npm run test      # Vitest
npm run lint      # ESLint + Prettier check
```

---

## Architecture

| Layer | Technology |
|-------|------------|
| Local LLM | Llama 3.2-1B Q4_K_M, llama.cpp, Vulkan backend |
| Cloud API | OpenRouter (`https://openrouter.ai/api/v1`) — OpenAI-compatible |
| Cloud tier 1 | `anthropic/claude-sonnet-4-5` — complex Socratic dialogue |
| Cloud tier 2 | `deepseek/deepseek-r1` — math / STEM reasoning chains |
| Cloud tier 3 | `anthropic/claude-haiku-4-5` — fast, cheap lighter queries |
| LLM Router | Intent classifier → local / cloud tier decision |
| Embeddings | nomic-embed-text-v1.5 |
| Vector DB | LanceDB (local) + Supabase pgvector (cloud sync) |
| RAG | Hybrid BM25 (0.6) + vector (0.4) + cross-encoder re-rank |
| Ingestion | Docling (on-device) + MinerU (pre-process) |
| Backend | FastAPI + sse-starlette (streaming SSE) |
| Frontend | React 18 + TypeScript + Vite |
| UI libs | @react-pdf-viewer, KaTeX, Streamdown |
| Auth / DB | Supabase (PostgreSQL + pgvector + Auth + RLS) |
| Scheduling | py-fsrs (FSRS algorithm) + BKT knowledge tracing |
| Container | Distrobox Ubuntu 24.04 via Podman |

---

## Python Coding Conventions

- **Async-first**: All FastAPI route handlers and I/O-bound service calls must be `async`. Never call blocking I/O (file reads, network, DB) inside an async route without `await` or `run_in_executor`.
- **Type hints**: Required on all public function signatures and class attributes. Add `from __future__ import annotations` at the top of each file.
- **Linting**: `ruff` with `line-length = 100`. Run `uv run ruff check .` before committing.
- **Formatting**: `ruff format`. No other formatter.
- **Type checking**: `mypy` in strict mode for `app/`. Errors must be resolved — no `type: ignore` suppressions.
- **HTTP client**: Use `httpx` (async). Never use `requests`.
- **Docstrings**: Required on all public classes and service-layer functions (Google style).

---

## TypeScript / React Conventions

- **Strict mode**: `"strict": true` in `tsconfig.json`. No exceptions.
- **No `any`**: Use `unknown` + type guards or proper generics instead.
- **Functional components only**: No class components. Use hooks for state and side effects.
- **Linting**: ESLint + Prettier enforced. Config lives in `frontend/`.
- **No default exports** from non-page component files.

---

## Testing Requirements (QA Protocol)

- Every new service or utility requires unit tests **before the PR can be merged**.
- Every API route requires at least one integration test.
- **Backend coverage target**: ≥ 80% for `backend/app/`.
- **Async tests**: Use `pytest-anyio` with `@pytest.mark.anyio`. Never call `asyncio.run()` inside tests.
- **Frontend**: Vitest + `@testing-library/react`. Test behaviour, not implementation details.
- **Memory budget gate**: Full-stack runtime (model loaded + server + frontend) must stay ≤ 7 GB RAM.
- **LLM perf gate**: Local model must achieve ≥ 20 tok/s on Vulkan before a Phase is closed.

---

## Agile Workflow

- **Sprint length**: 2 weeks. Each sprint maps to a sub-section of one Phase.
- **Branch naming**: `feature/phase-N-short-description` | `fix/short-description` | `test/short-description`
- **Commits**: Conventional Commits — `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `perf:`
- **PR policy**: All merges to `main` require a PR. No direct pushes to `main`.
- **Definition of Done**: All tests pass, lint clean, coverage target met, memory within budget, PR reviewed.

### 6-Phase Roadmap

| Phase | Scope | Weeks |
|-------|-------|-------|
| 1 | Foundation — llama.cpp + FastAPI streaming chat | 1–2 |
| 2 | Socratic engine + cloud LLM routing | 3–4 |
| 3 | RAG pipeline — ingestion, hybrid retrieval, re-ranking | 5–8 |
| 4 | PDF viewer integration + in-context citations | 9–10 |
| 5 | FSRS spaced repetition + BKT progress tracking | 11–14 |
| 6 | Polish, optimization, advanced features | 15–18 |

---

## Critical Constraints — Never Violate

| Constraint | Reason |
|-----------|--------|
| `n_ctx` ≤ 4096 | KV cache above this causes OOM on 16 GB shared RAM |
| No ROCm | RDNA2 iGPU has no ROCm support; Vulkan is the only GPU path |
| No blocking I/O in async routes | Stalls the entire FastAPI event loop |
| No `.gguf`, LanceDB data, or `.env` committed | Model files are large; secrets must never enter git history |
| Use `httpx`, not `requests` | `requests` is synchronous; async FastAPI requires async HTTP |
