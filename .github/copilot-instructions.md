# Copilot Instructions — Socratic AI Tutor

GitHub Copilot instructions for the `socra_teach` monorepo. Apply these rules to all suggestions across both `backend/` (Python) and `frontend/` (TypeScript/React).

---

## Stack

| Area | Technology |
|------|------------|
| Backend language | Python 3.11+ |
| Backend framework | FastAPI + sse-starlette |
| Python package manager | `uv` (`uv add`, `uv sync`, `uv run`) |
| Local LLM | llama-cpp-python (Vulkan backend) |
| Cloud API | OpenRouter — single OpenAI-compatible endpoint for all cloud models |
| Cloud tier 1 | `anthropic/claude-sonnet-4-5` — complex Socratic dialogue |
| Cloud tier 2 | `deepseek/deepseek-r1` — math / STEM reasoning chains |
| Cloud tier 3 | `anthropic/claude-haiku-4-5` — fast, cheap lighter queries |
| Vector DB | LanceDB |
| Learning scheduler | py-fsrs + custom BKT |
| HTTP client | `httpx` (async) |
| Frontend framework | React 18 + TypeScript (strict) |
| Frontend build | Vite |
| JS package manager | `npm` |
| UI libs | @react-pdf-viewer, KaTeX, Streamdown |
| Python lint/format | `ruff` (line-length = 100) |
| Python type check | `mypy` (strict) |
| Python tests | `pytest` + `pytest-anyio` |
| JS lint/format | ESLint + Prettier |
| JS tests | Vitest + `@testing-library/react` |

---

## Python Rules

- All route handlers and any I/O-bound functions must be `async def`.
- Start every file with `from __future__ import annotations`.
- Type-annotate every public function signature and class attribute.
- Use `httpx.AsyncClient` for all outbound HTTP — never `requests`.
- Format with `ruff format`; lint with `ruff check` (line-length = 100).
- Google-style docstrings on public classes and service-layer functions.
- Async tests must use `@pytest.mark.anyio` — never `asyncio.run()` inside tests.
- Do not suppress mypy errors with `type: ignore` — fix the types.
- Add new packages with `uv add <package>`, not `pip install`.

---

## TypeScript / React Rules

- `"strict": true` in tsconfig — no exceptions.
- No `any`. Use `unknown` + type guards, or proper generics.
- Functional components and hooks only — no class components.
- Run `npm run lint` to validate after any TypeScript change.
- No default exports from non-page component files.

---

## Patterns to Follow

### SSE Streaming (LLM output)
```python
from sse_starlette.sse import EventSourceResponse

async def chat_endpoint(...):
    async def token_generator():
        async for token in llm.stream(prompt):
            yield {"data": token}
    return EventSourceResponse(token_generator())
```

### Service-Layer Architecture
Routes call services; services call the data layer. Do not put business logic in route handlers.
```
routes/chat.py
  → services/tutor/socratic.py   (Socratic prompt construction)
  → services/tutor/router.py     (local vs. cloud routing decision)
  → services/rag/retriever.py    (hybrid BM25 + vector retrieval)
  → LanceDB / Supabase
```

### LLM Routing
All model selection (local vs. cloud tier) goes through `services/tutor/router.py`. Route handlers never call the LLM directly.

### OpenRouter Cloud Client
Cloud calls use the OpenRouter OpenAI-compatible endpoint with `httpx`. Never import `openai` directly — call via raw `httpx.AsyncClient` to avoid adding an openai SDK dependency:
```python
import httpx
from app.core.config import settings

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

CLOUD_MODELS = {
    "dialogue": "anthropic/claude-sonnet-4-5",   # complex Socratic turns
    "reasoning": "deepseek/deepseek-r1",           # math / STEM chains
    "fast": "anthropic/claude-haiku-4-5",          # quick / cheap tier
}

async def call_openrouter(model_key: str, messages: list[dict], stream: bool = True):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OPENROUTER_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json={"model": CLOUD_MODELS[model_key], "messages": messages, "stream": stream},
            timeout=60,
        )
        response.raise_for_status()
        return response
```

### FSRS Scheduling
All spaced repetition logic goes through `services/fsrs/scheduler.py`. Do not call py-fsrs directly from route handlers.

### Vector Queries
Use the LanceDB Python API directly. Do not wrap vector queries in an ORM abstraction.

### Environment / Config
All settings come from `core/config.py` (Pydantic `BaseSettings`). Never hardcode values or read `os.environ` outside of that module.

---

## Patterns to Avoid

- Blocking I/O inside async routes — `time.sleep`, `requests.get`, synchronous `open()` without `aiofiles`
- Hardcoded secrets or API keys anywhere in source files
- Using `requests` — always `httpx` async
- Setting `n_ctx` above 4096 (causes OOM on 16 GB shared RAM)
- Any ROCm or CUDA dependencies (hardware is Vulkan-only RDNA2)
- `type: ignore` comments to silence mypy — fix the root cause
- Class components or stateful logic outside of React hooks
- Calling `uv` or `pip` inside test files to install packages at test time

---

## Testing Patterns

### Backend — async unit test
```python
import pytest

@pytest.mark.anyio
async def test_retriever_returns_results(mock_lancedb):
    results = await retrieve(query="photosynthesis", top_k=5)
    assert len(results) == 5
```

### Frontend — component test
```tsx
import { render, screen } from "@testing-library/react";
import { ChatMessage } from "./ChatMessage";

test("renders assistant message", () => {
  render(<ChatMessage role="assistant" content="What do you think?" />);
  expect(screen.getByText("What do you think?")).toBeInTheDocument();
});
```

---

## Hardware Constraints (affect all suggestions)

- **Platform**: Steam Deck OLED — 16 GB shared RAM, AMD RDNA2 iGPU
- **GPU compute**: Vulkan only — no ROCm, no CUDA, no Metal
- **RAM budget**: Full-stack runtime ≤ 7 GB total
- **LLM context**: `n_ctx` hard limit of 4096 tokens
- **LLM perf target**: ≥ 20 tokens/sec for local model on Vulkan
