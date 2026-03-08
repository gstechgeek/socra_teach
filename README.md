# Socratic AI Tutor

A local-first, privacy-preserving tutoring application built for the Steam Deck OLED. Upload your textbooks, ask questions, and learn through guided Socratic dialogue — all running on-device with optional cloud LLM fallback.

## Features

- **Socratic Tutoring** — The tutor answers questions with guiding questions, encouraging active reasoning rather than passive consumption
- **PDF Textbook Viewer** — Side-by-side split-pane layout with built-in PDF viewer (thumbnails, bookmarks, search)
- **Hybrid RAG Pipeline** — Retrieval-Augmented Generation grounds responses in your uploaded textbooks using BM25 keyword search + vector similarity + cross-encoder re-ranking
- **Document-Scoped Retrieval** — Queries are automatically scoped to the textbook you're currently reading
- **In-Context Citations** — Clickable page references in tutor responses that jump to the source in the PDF viewer
- **PDF Selection Capture** — Draw a rectangle over any text or diagram in the PDF and use it as visual context for the tutor (multimodal)
- **Spaced Repetition** — FSRS-based flashcard scheduling with Bayesian Knowledge Tracing (BKT) for mastery estimation
- **Concept Graph** — Visual map of learned concepts and their prerequisite relationships
- **Progress Dashboard** — Track reviews completed, cards created, concepts learned, and study streaks

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React 18 + TypeScript + Vite)                    │
│  ┌──────────────┐  ┌──────────────────────────────────────┐ │
│  │  PDF Viewer   │  │  Socratic Chat + Review UI          │ │
│  │  (react-pdf-  │  │  (KaTeX, react-markdown, SSE)       │ │
│  │   viewer)     │  │                                      │ │
│  └──────────────┘  └──────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + SSE
┌──────────────────────────▼──────────────────────────────────┐
│  Backend (FastAPI + sse-starlette)                           │
│  ┌────────────┐  ┌──────────┐  ┌──────────────────────────┐│
│  │ RAG Engine │  │  Tutor   │  │  FSRS + BKT Scheduler    ││
│  │ BM25+Vec+  │  │  Router  │  │  Card Gen (auto)         ││
│  │ Reranker   │  │          │  │                           ││
│  └─────┬──────┘  └────┬─────┘  └──────────────────────────┘│
│        │              │                                      │
│  ┌─────▼──────┐  ┌────▼─────┐                              │
│  │  LanceDB   │  │ OpenRouter│                              │
│  │  (local)   │  │ Cloud API │                              │
│  └────────────┘  └──────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

| Layer | Technology |
|-------|------------|
| Local LLM | Llama 3.2-1B Q4_K_M via llama.cpp (Vulkan backend) |
| Cloud LLM | OpenRouter API — Claude Sonnet 4.5 (dialogue), DeepSeek R1 (STEM reasoning), Claude Haiku 4.5 (fast tier) |
| Embeddings | nomic-embed-text-v1.5 (local) or OpenAI text-embedding-3-small (cloud via OpenRouter) |
| Vector Store | LanceDB (local-first) |
| RAG | Hybrid BM25 (0.6) + vector (0.4) fusion, cross-encoder re-ranking |
| PDF Ingestion | PyMuPDF + pymupdf4llm (page-first chunking with printed page labels) |
| Spaced Repetition | py-fsrs (FSRS algorithm) + Bayesian Knowledge Tracing |
| Frontend | React 18, TypeScript strict, Vite, react-pdf-viewer, KaTeX |
| Backend | Python 3.11+, FastAPI, SSE streaming, httpx |

## Getting Started

### Prerequisites

- Python 3.11+ (managed by [uv](https://docs.astral.sh/uv/))
- Node.js 20 LTS
- An [OpenRouter](https://openrouter.ai/) API key

On Steam Deck, all Python work runs inside Distrobox (Ubuntu 24.04 via Podman).

### Setup

1. **Clone and configure environment**

   ```bash
   git clone https://github.com/your-username/socra_teach.git
   cd socra_teach
   cp .env.example backend/.env
   # Edit backend/.env — set your OPENROUTER_API_KEY
   ```

2. **Install backend dependencies**

   ```bash
   cd backend
   uv sync
   ```

3. **Install frontend dependencies**

   ```bash
   cd frontend
   npm install
   ```

4. **Pre-download ML models** (first time only, if using local embeddings)

   ```bash
   cd backend

   # Embedding model (~130 MB)
   uv run python -c "
   from app.services.rag.embedder import get_embedder
   get_embedder()
   print('Embedder ready')
   "

   # Cross-encoder for re-ranking (~85 MB)
   uv run python -c "
   from app.services.rag.reranker import _get_cross_encoder
   _get_cross_encoder()
   print('Cross-encoder ready')
   "
   ```

### Running

Start both servers (from the repo root):

```bash
# Terminal 1 — Backend
cd backend
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### Usage

1. Go to the **Textbooks** tab and upload a PDF
2. Switch to the **Tutor** tab — the PDF opens in the left pane, chat on the right
3. Ask questions about the textbook content; the tutor responds with Socratic guidance grounded in the text
4. Click citation badges (e.g., `p.127`) to jump to the referenced page
5. Use the **Select** button to draw a rectangle over diagrams or equations and send them as visual context
6. Visit the **Progress** tab to review flashcards and track your learning

## Development

### Commands

```bash
# Backend (from backend/)
uv sync                                              # install dependencies
uv run uvicorn app.main:app --reload --port 8000     # dev server
uv run pytest                                        # full test suite
uv run ruff check . && uv run ruff format --check .  # lint + format check
uv run mypy app/                                     # type check

# Frontend (from frontend/)
npm install       # install dependencies
npm run dev       # Vite dev server
npm run build     # production build
npm run test      # Vitest
npm run lint      # ESLint + Prettier
```

### Project Structure

```
socra_teach/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # chat, documents, progress, health
│   │   ├── core/              # config, llm (llama.cpp wrapper)
│   │   └── services/
│   │       ├── rag/           # embedder, ingestion, retriever, reranker, store
│   │       ├── tutor/         # socratic prompt engine, LLM router, classifier
│   │       └── fsrs/          # scheduler, BKT, card generator, store
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/        # Chat, PdfViewer, ConceptGraph, ReviewSession, ProgressDashboard
│   │   ├── hooks/             # useChat, useDocuments, useProgress, useRectSelect, useReviewQueue
│   │   └── pages/             # TutorPage, DocumentsPage, ProgressPage
│   ├── package.json
│   └── vite.config.ts
├── models/                    # .gitignored — GGUF model files
├── data/                      # .gitignored — LanceDB index, uploaded PDFs
├── .env.example
├── CLAUDE.md
└── AGENTS.md
```

### Conventions

- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) — `feat:`, `fix:`, `test:`, `docs:`
- **Branches**: `feature/phase-N-description`, `fix/description`, `test/description`
- **Python**: Async-first, type hints required, ruff formatting, mypy strict
- **TypeScript**: Strict mode, no `any`, functional components only

## Hardware Constraints

This project is designed for the Steam Deck OLED's shared 16 GB RAM:

| Constraint | Limit |
|-----------|-------|
| LLM context window | 4096 tokens max (KV cache OOM above this) |
| GPU backend | Vulkan only (no ROCm, no CUDA) |
| Full-stack RAM budget | 7 GB max |
| Local LLM throughput | 20+ tok/s target |

## License

Private project — not yet licensed for distribution.
