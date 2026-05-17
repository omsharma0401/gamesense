# GameSense Backend

Real-time multi-agent AI system that watches gameplay, detects key moments live, and produces a coaching dashboard after the session ends.

## What This Is

A Python FastAPI backend that:
1. Captures gameplay via macOS screen recording (VideoDB CaptureSession)
2. Indexes it continuously through a VideoDB sandbox (GEMMA VLM + audio)
3. Detects key moments in real-time as the game progresses
4. After session ends: scores the player, compiles clips, builds a highlight reel
5. Persists player history in a temporal knowledge graph + SQLite
6. Serves everything to a Next.js frontend at `~/Projects/gamesense-frontend`

## Context

Built for the VideoDB Global Hackathon (May 16–18 2026). Judging: 40% technical execution, 30% creativity, 30% depth of VideoDB usage. Deadline: May 18 10:00 AM IST.

Companion frontend: `~/Projects/gamesense-frontend` (Next.js 16, React 19, TailwindCSS v4, Recharts, Shadcn UI).

Reference project for patterns: `~/Desktop/ticket-triage` — OOP with ABC interfaces, OpenRouter provider, LLM-as-judge eval. Follow the same conventions here.

---

## Architecture Decisions (settled — do not re-debate)

### Multi-Agent: Real Concurrency via asyncio
Three agents run concurrently during a session:
- `CaptureAgent` — keeps the CaptureSession process alive
- `IndexingAgent` — runs RTStream visual + audio AI pipelines
- `MomentAgent` — polls JSONL events every 30s, detects key moments

They communicate through `/tmp/videodb_events.jsonl` (event bus). After session ends, `AnalysisAgent → MemoryAgent → HighlightAgent` run as a pipeline.

This is defensible as multi-agent because `asyncio.gather()` runs them truly concurrently with event-driven communication, not sequential function calls.

### LLM Provider: OpenRouter (same as ticket-triage)
Uses the OpenAI SDK with `base_url="https://openrouter.ai/api/v1"`. Model is swappable via `.env`. Default: `openai/gpt-oss-120b` (free, 117B MoE, native JSON schema, built for agents).

Judge LLM uses Groq (`llama-4-scout`) — different provider to avoid self-evaluation bias.

Graphiti (knowledge graph) uses OpenRouter via `OpenAIGenericClient` — same key.

### Databases: Two, Not Three
- **SQLite** — structured stats (scores, K/D, maps, timestamps). SQL is irreplaceable for graphs and trends.
- **Kuzu** (via Graphiti) — temporal knowledge graph. Tracks how player skills *change over time* ("B site struggle was true in sessions 1–5, resolved in session 6"). Embedded, no server.
- ChromaDB was considered and cut — SQLite last-N sessions fed to Claude is sufficient for pre-session briefing at demo scale.

### No Voyage AI / No Reranking
Ticket-triage used Voyage AI for embeddings and reranking. GameSense does not need it — there is no RAG retrieval pipeline over a document corpus. Moment detection and analysis work directly on LLM inference over events.

### macOS Only
VideoDB CaptureSession only works on macOS. This is a known limitation acknowledged in the demo. The architecture supports a future RTStream-based path for Windows (OBS → RTSP → VideoDB RTStream) but that is not built here.

### Sandbox Management: Standalone Scripts
The VideoDB sandbox is managed independently of FastAPI:
```bash
python sandbox_start.py   # creates sandbox, writes ID to .env, call once per session
python sandbox_stop.py    # stops sandbox, call when done to stop billing
```
FastAPI reads `VIDEODB_SANDBOX_ID` from `.env` at startup. The sandbox costs $3.50/hr (medium tier) but the hackathon provides $1000 in credits.

---

## Folder Structure

```
gamesense-backend/
│
├── main.py                  # FastAPI app, lifespan, CORS (allow localhost:3000)
├── config.py                # All env vars and constants — single source of truth
├── requirements.txt
├── .env.example
├── sandbox_start.py         # Standalone: create sandbox, write ID to .env
├── sandbox_stop.py          # Standalone: stop sandbox by ID
│
├── agents/
│   ├── interfaces.py        # BaseAgent ABC: run(), stop()
│   ├── capture_agent.py     # Owns CaptureSession + ws_listener lifecycle
│   ├── indexing_agent.py    # Starts RTStream visual + audio AI pipelines
│   ├── moment_agent.py      # Polls JSONL, detects moments via LLM
│   ├── analysis_agent.py    # Post-session: score + analysis via LLM
│   ├── memory_agent.py      # Writes to Graphiti + SQLite
│   ├── briefing_agent.py    # Pre-session coaching from memory
│   └── highlight_agent.py   # Compiles highlight reel via Timeline editor
│
├── llm/
│   ├── interfaces.py        # BaseLLMProvider ABC — same as ticket-triage
│   └── openrouter_provider.py  # OpenRouter impl — adapted from ticket-triage
│
├── memory/
│   ├── interfaces.py        # BaseGraphStore, BaseSessionStore ABCs
│   ├── graph_store.py       # Graphiti + Kuzu wrapper
│   └── session_store.py     # SQLite wrapper (sessions, moments, briefings)
│
├── schemas/
│   ├── session.py           # Session, Moment, Score, Clip, Briefing (Pydantic)
│   └── agent.py             # Agent input/output types
│
├── api/
│   ├── session.py           # POST /session/start|stop, GET /session/{id}|active
│   ├── analysis.py          # GET /analysis/{id}, /briefing/{player_id}, /history/{player_id}
│   ├── clips.py             # GET /clips/{id}, POST /clips/{id}/highlight
│   └── discord.py           # POST /discord/share (webhook, no OAuth)
│
├── eval/
│   ├── interfaces.py        # BaseJudge ABC
│   ├── fixtures.py          # Pre-seeded sessions + JSONL event files for testing
│   ├── judge.py             # LLM-as-judge (adapted from ticket-triage/code/judge.py)
│   ├── runner.py            # python -m eval.runner [--no-judge]
│   └── seed_demo.py         # Seeds 4 historical sessions before demo
│
└── tests/
    ├── conftest.py          # Shared fixtures: mock LLM, sample events
    ├── test_moment_agent.py
    ├── test_analysis_agent.py
    ├── test_memory_agent.py
    ├── test_briefing_agent.py
    ├── test_highlight_agent.py
    └── test_api.py
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
# Required
VIDEO_DB_API_KEY=        # console.videodb.io — free tier + hackathon credits
OPENROUTER_API_KEY=      # openrouter.ai — free, no credit card
GROQ_API_KEY=            # console.groq.com — free, no credit card
DISCORD_WEBHOOK_URL=     # Discord channel → Edit → Integrations → Webhooks

# Written by sandbox_start.py — do not set manually
VIDEODB_SANDBOX_ID=

# Optional overrides
OPENROUTER_MODEL=openai/gpt-oss-120b
GROQ_JUDGE_MODEL=llama-4-scout
PLAYER_ID=player-001
GAME_NAME=CS2
MOMENT_POLL_INTERVAL=30
KUZU_DB_PATH=./data/kuzu
SQLITE_DB_PATH=./data/gamesense.db
EVENTS_PATH=/tmp/videodb_events.jsonl
```

**Cost: zero.** OpenRouter and Groq are free tiers, no credit card. VideoDB has free tier + hackathon credits.

---

## Setup

```bash
# 1. Install SDK (hackathon branch)
pip install "git+https://github.com/Video-DB/videodb-python.git@hackathon"
pip install fastapi uvicorn python-dotenv openai graphiti-core[kuzu] pytest httpx

# 2. Copy env
cp .env.example .env
# Fill in VIDEO_DB_API_KEY, OPENROUTER_API_KEY, GROQ_API_KEY, DISCORD_WEBHOOK_URL

# 3. Start sandbox (run once per work session)
python sandbox_start.py

# 4. Run backend
uvicorn main:app --reload --port 8000

# 5. Stop sandbox when done
python sandbox_stop.py
```

---

## API Routes

```
POST /session/start              body: { game, player_id }
POST /session/stop               body: { session_id }
GET  /session/{session_id}       live status + moments detected so far
GET  /session/active             currently running session or null

GET  /analysis/{session_id}             full analysis: score, clips, patterns, summary
GET  /analysis/briefing/{player_id}     pre-session coaching brief from memory
GET  /analysis/history/{player_id}      last N sessions for graphs { sessions[], scores[] }

GET  /clips/{session_id}         all clips with stream URLs
POST /clips/{session_id}/highlight   trigger highlight reel generation
GET  /clips/highlight/{session_id}   get highlight reel stream URL

POST /discord/share              body: { session_id, moment_id, webhook_url }
```

---

## Agent Lifecycle

### During Session (concurrent)
```python
async def run_session(game, player_id):
    capture_task  = asyncio.create_task(capture_agent.run())
    await capture_agent.wait_for_active()           # blocks until RTStreams ready
    indexing_task = asyncio.create_task(indexing_agent.run(capture_agent.rtstreams))
    moment_task   = asyncio.create_task(moment_agent.run())
    await asyncio.gather(capture_task, indexing_task, moment_task)
```

### After Session (pipeline)
```python
analysis  = await analysis_agent.run(session_id, video_id, moments)
           await memory_agent.run(analysis)          # SQLite + Graphiti
highlight = asyncio.create_task(highlight_agent.run(analysis.top_moments))
briefing  = await briefing_agent.generate(player_id) # stored for next session
```

---

## Key Implementation Details

### MomentAgent event polling
- Tracks byte offset in JSONL file — reads only new lines since last poll
- Sorts events by `unix_ts` before processing (handles out-of-order delivery)
- Window: last 10 events passed to LLM for context
- Filters: loading screens, menus, pause screens → `is_moment: false`
- Moment types: `kill`, `death`, `clutch`, `error`, `strategy_break`, `highlight`, `blunder`

### AnalysisAgent clip compilation
- `video.search()` raises `InvalidRequestError: No results found` — always wrap in try/except, treat as no clip for that moment
- Run clip compilations in parallel: `asyncio.gather(*[compile(m) for m in moments])`
- Cap at top 20 moments by significance to avoid oversized prompts

### HighlightAgent
- Clamp timestamps: `max(0, ts - 5)` — negative timestamps silently break streams
- Cap at 8 clips, ~90 seconds total
- Generate music in parallel while compiling clips
- Mix positive + negative moments for emotional arc

### Graphiti setup
```python
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.llm_client.config import LLMConfig

graphiti = Graphiti(
    "kuzu:///data/kuzu", "", "",
    llm_client=OpenAIGenericClient(config=LLMConfig(
        api_key=OPENROUTER_API_KEY,
        model="openai/gpt-oss-120b",
        base_url="https://openrouter.ai/api/v1"
    ))
)
```
`add_episode()` is slow (internal LLM call) — always run as `asyncio.create_task()`, never await in request path.

### CaptureAgent critical notes
- `CaptureClient` must stay alive for the entire session — run as a long-lived coroutine
- Writes session_id and rtstream_ids to `/tmp/videodb_capture_info.json` for other agents
- Shutdown order: `stop_capture()` → wait for `capture_session.exported` → kill ws_listener
- macOS screen capture permission must be granted before first run

---

## Testing

### Run all unit tests (no API keys needed)
```bash
pytest tests/ -v
```

### Run eval with LLM judge
```bash
python -m eval.runner           # full eval with judge
python -m eval.runner --no-judge  # pipeline smoke test only
```

### Seed demo data before presenting
```bash
python eval/seed_demo.py        # inserts 4 historical sessions so briefing fires
```

### Test layers
1. **Unit** — pure logic, mock LLM returns fixture JSON, no network
2. **Integration** — real Kuzu + SQLite on temp dir, mock LLM
3. **Judge eval** — real LLM judge scores agent outputs against fixtures
4. **Smoke** — manual scripts in `smoke/` to verify API keys work

---

## What Can Go Wrong

| Risk | Fix |
|---|---|
| macOS screen capture permission not granted | Check permission before start, return 403 with instructions |
| Sandbox >5 min to activate | `wait_for_ready(timeout=300)`, fail fast if exceeded |
| ws_listener dies mid-session | Monitor PID file, auto-restart subprocess |
| JSONL events out of order | Sort by `unix_ts` before processing |
| `index_scenes()` on already-indexed video | Catch + extract existing index ID with `re.search(r"id\s+([a-f0-9]+)", str(e))` |
| `video.search()` returns `InvalidRequestError: No results found` | Catch, treat as empty, skip clip |
| VideoAsset negative timestamp | `max(0, ts - 5)` on all timestamps |
| Graphiti `add_episode()` blocking request | `asyncio.create_task()`, never await in path |
| ChromaDB collection conflict on restart | `get_or_create_collection()` not `create_collection()` |
| Claude/LLM prompt too large (long sessions) | Cap at top 20 moments by significance |
| CORS blocking Next.js → FastAPI | `allow_origins=["http://localhost:3000"]` in FastAPI CORS |
| SQLite concurrent writes from agents | Single asyncio lock around all write ops |
| Demo has no history for briefing | Run `python eval/seed_demo.py` before demo |

---

## Build Order

Build in this sequence. Each phase is testable before the next begins.

```
Phase 1 — Core capture pipeline
  config.py → schemas/session.py → llm/ → memory/session_store.py
  → agents/interfaces.py → agents/capture_agent.py
  → agents/indexing_agent.py → agents/moment_agent.py
  → sandbox_start.py + sandbox_stop.py
  TEST: run capture + see moments appear in SQLite

Phase 2 — Post-session analysis
  agents/analysis_agent.py → agents/highlight_agent.py
  → api/session.py + api/clips.py → main.py
  TEST: trigger analysis on a saved session

Phase 3 — Memory + briefing
  memory/graph_store.py → agents/memory_agent.py
  → agents/briefing_agent.py → api/analysis.py
  TEST: seed fixtures, verify briefing generates

Phase 4 — Eval + tests
  eval/fixtures.py → eval/judge.py → tests/
  RUN: pytest tests/ && python -m eval.runner --no-judge

Phase 5 — Polish
  api/discord.py → wire to frontend → seed_demo.py → record demo
```

---

## Demo Script (3 minutes)

1. Dashboard opens → pre-session briefing plays (from seeded memory)
2. Player selects game, clicks "Start GameSense" → capture begins
3. Play 2–3 minutes → live alert fires mid-game
4. Click "End Session" → dashboard loads in <60 seconds
5. Clips grid with AI commentary on each card
6. Search bar: type "best moments" → clips appear from past sessions
7. "Generate Highlights" → narrated reel plays
8. One-click Discord share of top clip

---

## Frontend

The Next.js frontend lives at `~/Projects/gamesense-frontend`. It polls:
- `GET /session/active` every 2s during capture (live moment count)
- `GET /analysis/{session_id}` after session stops
- `GET /history/{player_id}` for trend graphs (Recharts)

Backend must be running on `http://localhost:8000` with CORS allowing `http://localhost:3000`.
