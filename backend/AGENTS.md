# CLAUDE.md — GameSense Backend

This file is read by AI coding agents (Claude Code, Cursor, etc.) working on this project. Read it fully before writing any code.

---

## What We Are Building

GameSense is a real-time multi-agent AI coaching system for gamers. Screen capture → live visual indexing → moment detection → post-session dashboard with clips, scoring, and coaching.

Full product context, architecture decisions, and build plan are in `README.md`. Read that first. This file contains agent-specific coding conventions and constraints.

---

## Critical Constraints

1. **macOS only** — VideoDB CaptureSession runs on macOS. Do not add Windows/Linux paths.
2. **VideoDB hackathon SDK** — install from `git+https://github.com/Video-DB/videodb-python.git@hackathon`, not PyPI.
3. **No Voyage AI, no ChromaDB, no reranking** — these were used in ticket-triage but are not part of GameSense. Do not add them.
4. **Sandbox is managed externally** — `sandbox_start.py` and `sandbox_stop.py` handle lifecycle. FastAPI reads `VIDEODB_SANDBOX_ID` from `.env`. Do not manage sandbox inside FastAPI routes.
5. **Zero billing target** — only `VIDEO_DB_API_KEY` (hackathon credits), `OPENROUTER_API_KEY` (free tier), `GROQ_API_KEY` (free tier), `DISCORD_WEBHOOK_URL` (not a key). No other paid services.

---

## Code Style and Conventions

Follow the exact patterns from `~/Desktop/ticket-triage/code/`:

### ABC interfaces for every layer
```python
# Every major component has an ABC in interfaces.py
# Concrete implementations import and extend it
# Orchestrators/agents accept the ABC type, never the concrete class

from abc import ABC, abstractmethod

class BaseAgent(ABC):
    @abstractmethod
    async def run(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...
```

### No domain folders, no use-case folders
Structure by technical layer, not by feature:
```
agents/   llm/   memory/   schemas/   api/   eval/   tests/
```
Never create `features/`, `use_cases/`, `domains/`, `services/`.

### OOP throughout
- No free-floating functions doing business logic
- Agent classes own their state
- Memory stores are injected, not imported directly in agents

### LLM calls: always structured output
Use `complete_structured()` not `complete()` for any call that needs JSON back. The OpenRouter provider handles schema enforcement.

### Pydantic for all schemas
All data crossing API boundaries or between agents uses Pydantic models from `schemas/`. No raw dicts in function signatures.

### Config via config.py only
All env vars and constants live in `config.py`. Never call `os.getenv()` anywhere else. Import from `config` directly.

---

## LLM Provider

Reuse the OpenRouter pattern from ticket-triage. The provider is nearly identical — just update the JSON schema to match GameSense output types instead of triage types.

```python
# llm/openrouter_provider.py
from openai import OpenAI

class OpenRouterProvider(BaseLLMProvider):
    def __init__(self):
        self._client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )
        self._model = OPENROUTER_MODEL  # default: "openai/gpt-oss-120b"
```

The judge in `eval/judge.py` uses Groq (`GROQ_API_KEY`, model `llama-4-scout`) — different provider to avoid self-eval bias. Same pattern as ticket-triage's cross-family judge selection.

---

## VideoDB SDK Patterns

### Always handle these two errors
```python
from videodb.exceptions import InvalidRequestError
import re

# Pattern 1: search with no results
try:
    results = video.search(query)
    shots = results.get_shots()
except InvalidRequestError as e:
    if "No results found" in str(e):
        shots = []
    else:
        raise

# Pattern 2: scene index already exists
try:
    scene_index_id = video.index_scenes(...)
except Exception as e:
    match = re.search(r"id\s+([a-f0-9]+)", str(e))
    if match:
        scene_index_id = match.group(1)
    else:
        raise
```

### Timestamp safety
Always clamp: `start = max(0, timestamp_ms / 1000 - 5)`. Negative timestamps silently produce broken streams.

### Clip compilation in parallel
```python
import asyncio
clips = await asyncio.gather(*[compile_clip(m) for m in moments], return_exceptions=True)
clips = [c for c in clips if not isinstance(c, Exception)]
```

---

## Graphiti Setup

Uses Kuzu embedded backend (no server, no Docker). Uses OpenRouter as the LLM client.

```python
from graphiti_core import Graphiti
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.llm_client.config import LLMConfig

graphiti = Graphiti(
    "kuzu:///data/kuzu", "", "",
    llm_client=OpenAIGenericClient(config=LLMConfig(
        api_key=OPENROUTER_API_KEY,
        model=OPENROUTER_MODEL,
        base_url="https://openrouter.ai/api/v1"
    ))
)
```

**`add_episode()` is slow** — it calls the LLM internally to extract graph entities. Never await it in a request path. Always:
```python
asyncio.create_task(graph_store.add_episode(summary))
```

---

## SQLite Concurrency

Multiple agents write to SQLite concurrently. Use a single module-level asyncio lock:

```python
# memory/session_store.py
import asyncio
_write_lock = asyncio.Lock()

async def write_session(self, session: Session) -> None:
    async with _write_lock:
        # db write here
```

---

## JSONL Event File

All VideoDB WebSocket events land in `/tmp/videodb_events.jsonl` via `ws_listener.py`.

MomentAgent reads this file incrementally:
```python
# Track byte offset, not line number
with open(EVENTS_PATH, "r") as f:
    f.seek(self._last_offset)
    new_lines = f.readlines()
    self._last_offset = f.tell()

events = [json.loads(l) for l in new_lines if l.strip()]
events.sort(key=lambda e: e["unix_ts"])  # sort — delivery may be out of order
```

---

## Testing Conventions

### Unit tests: mock the LLM
```python
# tests/conftest.py
@pytest.fixture
def mock_llm():
    class MockLLM(BaseLLMProvider):
        def complete_structured(self, system, user):
            # Return deterministic fixture JSON based on input
            if "moment" in user.lower():
                return json.dumps(FIXTURE_MOMENT_RESPONSE)
            return json.dumps(FIXTURE_ANALYSIS_RESPONSE)
        def complete(self, system, user): return self.complete_structured(system, user)
        @property
        def model_name(self): return "mock"
    return MockLLM()
```

### Never call real APIs in unit tests
No `VIDEO_DB_API_KEY`, no `OPENROUTER_API_KEY` in `tests/`. All external calls are mocked.

### Fixtures live in eval/fixtures.py
Pre-recorded game events (JSONL) and pre-seeded sessions (JSON) are the test corpus. Add new fixtures there, not inline in test files.

### Judge eval is independent
`eval/runner.py --no-judge` must pass with zero API keys. The judge (real LLM) is opt-in.

---

## FastAPI Conventions

```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from api import session, analysis, clips, discord
app.include_router(session.router, prefix="/session")
app.include_router(analysis.router, prefix="/analysis")
app.include_router(clips.router, prefix="/clips")
app.include_router(discord.router, prefix="/discord")
```

Routes return Pydantic models, not raw dicts. Use `response_model=` on every route.

---

## What NOT to Build

- No user authentication (single-player demo)
- No Docker / containerization
- No cloud deployment (runs locally)
- No WebSocket streaming to frontend (frontend polls instead)
- No TikTok integration (not available in India)
- No Voyage AI / reranking
- No ChromaDB (cut — SQLite + Graphiti is sufficient)
- No Mem0 (cut — RAG via SQLite + Graphiti covers it)
- No LangChain (not needed — direct SDK calls are cleaner)
- No YouTube upload in Phase 1–4 (add only if Phase 5 has time)

---

## Current State

The backend directory is empty. No code has been written yet. Start from Phase 1 in README.md.

The frontend at `~/Projects/gamesense-frontend` is scaffolded (Next.js 16 with Tailwind, Recharts, Shadcn) but has no GameSense-specific pages yet.

Reference implementation for patterns: `~/Desktop/ticket-triage/code/`
- `llm/interfaces.py` — copy the BaseLLMProvider pattern directly
- `llm/openrouter_provider.py` — adapt (update JSON schema, keep retry logic)
- `judge.py` — adapt for GameSense eval dimensions
- `agent/orchestrator.py` — study the pattern, do not copy directly (different domain)
