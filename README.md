# GameSense

GameSense is a multi-agent AI dashboard that watches your gameplay in real time, automatically cuts your best moments into clips, generates a narrated highlight reel, and gives you a breakdown of how your session actually went — all without you touching a video editor. It is built for casual gamers who want a record of their sessions and content creators who want shareable clips without the four-hour editing grind.

Hit record, play your game, stop when you are done. By the time you open the dashboard, your clips are already there.

The system runs a pipeline of specialised AI agents concurrently during your session. One captures and streams your screen through VideoDB's live infrastructure. Another indexes the footage visually and by audio as it arrives. A third watches the indexed feed in real time and marks the moments worth keeping. A fourth speaks to you while you play. After you stop, the pipeline scores your session, compiles the clips, stitches the best ones into a narrated highlight reel, and writes a short note about what to focus on next time — drawing from your full session history, not just the current run. Every part of this that touches video goes through VideoDB.

---

## Short Description (submission, 200 words)

GameSense is a multi agent AI dashboard that watches your gameplay in real time and turns it into shareable content. It streams your screen through VideoDB's CaptureSession, detects clutch plays, blunders, and key moments as they happen, and tags each with a significance score and caster commentary. After the session, it compiles clips, stitches a narrated highlight reel with ElevenLabs voice overlays, and exports a vertical cut for short-form sharing. A knowledge graph tracks your progress across sessions and drops a personalised pre-game brief before your next run. VideoDB powers every step — capture, indexing, clipping, and final export.

---

## Demo

Link to demo video: [Watch Demo](https://drive.google.com/drive/folders/1CG4AD22jtywjCaX1kLB69T5XBxvoi8JY)

---

## The Problem It Solves

A typical gaming session generates gigabytes of footage and hundreds of micro-decisions. Watching it back objectively is tedious. Clipping and editing highlights for YouTube or sharing with friends takes hours. And without any kind of structured record, bad habits compound quietly — the same positioning mistake made in session three is still there in session thirty.

GameSense eliminates all three of these. It acts as an untiring observer: it watches the stream in real time, semantically understands what is happening in the game, and surfaces every moment worth keeping alongside ready-to-share clips. The dashboard also tracks skill trends across sessions, so you can see whether things are actually improving rather than just feeling like they are.

---

## What It Does

**Live moment detection.** As you play, the AI indexes your screen every few seconds and listens to in-game audio. It sends each batch of events to an LLM that decides whether something significant just happened — a clean clutch, a bad crash, a dominant run, a mistake. Every flagged moment gets a type label, a significance score from zero to ten, and a line of broadcast-style caster commentary written in real time.

**Live audio cues.** While the session is running, a separate agent watches the accumulating moment log and detects patterns: three deaths in five minutes, a kill streak, an idle period where nothing is happening. When a pattern fires, it generates a short coaching cue, synthesises it to audio using ElevenLabs via VideoDB, and plays it through your speakers via macOS `afplay`. The cue also posts to a Discord channel if you have one configured. Eight to twelve words, caster tone, genre-appropriate language.

**All Clips.** Every detected moment becomes a clip. The analysis agent searches the exported recording semantically, generates a stream URL for the relevant segment, and creates a thumbnail. Clips are tagged by type — CLUTCH, BLUNDER, HIGHLIGHT, ERROR, and so on — and scored with a Skill Points system that awards or deducts points based on how significant the moment was. A 1v3 clutch might award +20 points; missing an easy jump deducts −15. The clips screen lets you browse by session, genre, or game title.

**Highlight reel.** The highlight agent picks the best clips from the session, orders them chronologically, generates per-clip voiced commentary using ElevenLabs through VideoDB, and assembles everything into a single Timeline with a video track and an audio narration track. The final stream URL is embeddable directly. An optional 9:16 vertical version is generated in the background using VideoDB's reframe API, suitable for Reels or short-form sharing.

**Performance trends.** After the session ends, an LLM scores the session across three dimensions — mechanics, decision-making, and consistency — on a scale of zero to one hundred. The Performance screen plots these across your last ten sessions using interactive charts. You also get a player archetype ("The Clutch Artist", "The Aggressive Entry") and an epic summary line in the style of a wrapped card.

**Pre-session note.** Before your next session, the dashboard generates a short, conversational note written from your session history and a temporal knowledge graph that tracks how your tendencies have shifted over time. It reads like a text from someone who watched your last few sessions, not a generated report.

---

## How VideoDB Is Used

VideoDB is not a peripheral integration here. It is what makes the live pipeline possible at all.

**Live capture.** `CaptureAgent` uses `videodb.connect().create_capture_session()` to initiate a server-side capture session tied to the player's desktop. A local `CaptureClient` requests screen and microphone permissions, enumerates channels, and calls `start_session()`. VideoDB manages the live stream from this point and emits lifecycle events over a WebSocket that a listener subprocess writes to a local JSONL file.

**Real-time visual indexing.** `IndexingAgent` picks up the RTStream IDs produced by the capture session and calls `rtstream.index_visuals()` with a prompt that describes what the model should look for: player actions, health and ammo state, enemy positions, map context. Batches run every five seconds with three frames per batch. Results arrive as WebSocket events in the same JSONL file.

**Real-time audio indexing.** On audio-capable streams (microphone, system audio), `IndexingAgent` calls `rtstream.index_audio()` with a prompt focused on callouts, ability sounds, and kill confirmations. Batches run on a word-count basis. Results flow into the same event file.

**Moment detection from the indexed feed.** `MomentAgent` reads the JSONL file incrementally using byte-offset tracking so it never reprocesses old events. Every thirty seconds it sends the most recent events to an LLM that classifies whether a significant moment occurred and writes the result to SQLite.

**Clip compilation.** After the session ends, `AnalysisAgent` calls `video.index_scenes()` on the exported recording to build a semantic index, then for each detected moment calls `video.search()` with the moment description as the query and generates a playable clip using `video.generate_stream(timeline=[(start, end)])`. Thumbnails come from `video.generate_thumbnail()`. Clips are compiled in parallel.

**Highlight reel assembly.** `HighlightAgent` generates per-clip voiced narration using `collection.generate_voice()` (ElevenLabs, voice matched to moment type), then builds a `Timeline` with a video track and audio commentary track, finalised with `timeline.generate_stream()`. The optional vertical version uses `video.reframe(mode=ReframeMode.smart)`.

**Live coaching voice.** `LiveCoachAgent` also calls `collection.generate_voice()` during the session to synthesise short coaching cues, which are played locally via `afplay`.

**Sandbox compute.** Scene indexing on the exported recording uses a VideoDB sandbox (`SandboxTier.medium`) provisioned by `sandbox_start.py` before the session.

---

## Architecture

The backend is a pipeline of specialised agents that coordinate through shared state in SQLite and a JSONL event file. Agents write to and read from these shared resources rather than calling each other directly.

### Live session pipeline (four concurrent agents)

`CaptureAgent` manages the full VideoDB capture lifecycle: launching the WebSocket listener subprocess, obtaining the WebSocket ID, creating the server-side `CaptureSession`, initialising the local `CaptureClient`, waiting for the `capture_session.active` event, and waiting for the `capture_session.exported` event to obtain the final video ID.

`IndexingAgent` waits for the capture info file, reads the RTStream IDs, and attaches visual and audio AI pipelines to each stream. Runs until `stop()` is called.

`MomentAgent` polls the JSONL event file on a byte-offset basis every thirty seconds, sorts events by timestamp, takes the last ten as context, and sends them to an LLM for moment classification. Detected moments are written to SQLite.

`LiveCoachAgent` ticks every five seconds, detects patterns in the growing moment log, generates short audio cues via LLM and VideoDB voice synthesis, plays them locally, and posts to Discord.

### Post-session pipeline (sequential, then parallel)

`AnalysisAgent` scores the session and compiles clips.

`MemoryAgent` persists the full analysis to SQLite and fires a background task to add a session episode to the Graphiti knowledge graph.

`HighlightAgent` and `BriefingAgent` run in parallel: the first assembles the narrated reel, the second queries the graph and session history to generate the pre-session note.

## Prerequisites

- macOS (VideoDB CaptureSession requires macOS for screen and microphone capture)
- Python 3.11 or later
- Node.js 20 or later
- A VideoDB API key — [console.videodb.io](https://console.videodb.io)
- An OpenRouter API key (free tier works) — [openrouter.ai](https://openrouter.ai)
- A Groq API key (free tier, eval judge only) — [console.groq.com](https://console.groq.com)
- Optional: a Discord webhook URL for the live cue log

---

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/omsharma0401/gamesense.git
cd gamesense
```

### 2. Create and activate a Python virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

Your shell prompt will change to show `(venv)`. Every Python command from this point must be run with this environment active. If you open a new terminal, run `source venv/bin/activate` again from the `backend/` directory before running anything.

### 3. Install backend dependencies

The `requirements.txt` includes the VideoDB hackathon SDK installed directly from GitHub (it is not on PyPI), along with FastAPI, uvicorn, graphiti-core, aiosqlite, openai, httpx, pydantic, and the test dependencies.

```bash
pip install -r requirements.txt
```

This may take a couple of minutes because `graphiti-core[kuzu]` pulls in the embedded Kuzu database. If the Git install of VideoDB fails, you can install it separately first:

```bash
pip install git+https://github.com/Video-DB/videodb-python.git@hackathon
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` in any editor and fill in your keys:

```env
VIDEO_DB_API_KEY=your_videodb_key_here
OPENROUTER_API_KEY=your_openrouter_key_here
GROQ_API_KEY=your_groq_key_here          # optional, eval judge only
DISCORD_WEBHOOK_URL=                      # optional, live cue log
```

Leave everything else at the defaults shown in `.env.example`. Do not set `VIDEODB_SANDBOX_ID` manually — it is written automatically in the next step.

### 5. Create a VideoDB sandbox

The sandbox provides GPU compute for scene indexing on the exported recording. It must be running before you start a session.

```bash
python sandbox_start.py
```

This creates a medium-tier sandbox, polls until it is active (roughly thirty seconds), and writes the sandbox ID into `.env` as `VIDEODB_SANDBOX_ID`. The sandbox uses hackathon credits. Stop it when you are done for the day with `python sandbox_stop.py`.

### 6. Start the backend API server

```bash
uvicorn main:app --reload --port 8000
```

The server starts at `http://localhost:8000`. You should see log lines confirming that SQLite, Graphiti, and the LLM provider initialised without errors.

Quick sanity check:

```bash
curl http://localhost:8000/health
# {"status": "ok", "service": "gamesense-api"}
```

Interactive API docs are at `http://localhost:8000/docs`.

### 7. Start the frontend

Open a new terminal — the virtual environment only affects the backend.

```bash
cd frontend
npm install
npm run dev
```

The frontend starts at `http://localhost:3000`.

---

## Running a Session

1. Open `http://localhost:3000`.
2. In the sidebar, pick your genre. You can also type a game name — this keeps your session history filterable per title.
3. Click "Start Recording". macOS will ask for screen recording and microphone permissions on the first run — grant both. The button changes to a live recording state with a moment counter.
4. Play your game. The sidebar feed shows audio cues as they arrive. If you have Discord configured, the same cues appear in your channel.
5. Click "Stop Recording" when done. The post-session pipeline runs in the background.
6. Browse the dashboard:
   - **All Clips** — every tagged moment as a playable clip with commentary, type label, and Skill Points
   - **Highlights** — the narrated highlight reel assembled from the session
   - **Performance** — score trends across sessions and your pre-session note
   - **Session Wrap** — your player archetype, epic summary, and dimension scores
   - **Raw Records** — the full moment and session log

### Stop the sandbox when done

```bash
cd backend
source venv/bin/activate
python sandbox_stop.py
```

---

## Tech Stack

**Backend**
- Python 3.13, FastAPI, uvicorn
- `aiosqlite` — async SQLite (sessions, moments, analyses, briefings, highlights, suggestions)
- `graphiti-core[kuzu]` — embedded temporal knowledge graph, no Docker required
- `openai` SDK pointed at OpenRouter (primary LLM) and Groq (eval judge)
- `httpx` — async HTTP for Discord webhooks and audio downloads
- `pydantic` v2 — all schemas
- `videodb` hackathon branch — capture, indexing, clips, voice, timeline, reframe

**Frontend**
- Next.js 16, React 19, TypeScript
- Tailwind CSS v4
- Recharts for trend graphs
- Framer Motion for transitions
- `hls.js` for VideoDB stream playback
- Shadcn UI components

**External services**
- VideoDB (capture, indexing, clip generation, voice synthesis, timeline, sandbox compute)
- OpenRouter (default model: `openai/gpt-oss-120b`)
- Groq (`meta-llama/llama-4-scout-17b-16e-instruct`, eval judge only)
- Discord (optional webhook)

---

## Running Tests

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

Unit tests mock all LLM and VideoDB calls. No API keys required.

---

## Supported Genres

The moment detection model receives genre-specific context before classifying each event, so both the language and what counts as significant are calibrated to the game type. The platform currently supports four genres.

| Genre | Example Games | What the AI Tracks |
|-------|---------------|--------------------|
| Arcade Racing | Asphalt 8/9, Mario Kart | Overtakes, crashes, clutch recoveries, missed apexes, clean laps |
| Tactical Shooter | Valorant, CS2 | Kills, deaths, clutch rounds, mechanical highlights, round-ending blunders |
| Real-Time Strategy | StarCraft II, Clash Royale | Unit trades, base raids, clutch defences, economy errors, tech switches |
| Turn-Based Tactics | Chess, 8 Ball Pool | Eliminations, units lost, clutch reversals, perfect turns, tactical pivots |

---



## Folder Structure

```
gamesense/
├── backend/
│   ├── agents/
│   │   ├── interfaces.py           # BaseAgent ABC
│   │   ├── capture_agent.py        # VideoDB desktop capture lifecycle
│   │   ├── indexing_agent.py       # RTStream visual + audio indexing
│   │   ├── moment_agent.py         # Real-time moment detection via LLM
│   │   ├── live_coach_agent.py     # Live audio cues + ElevenLabs TTS
│   │   ├── analysis_agent.py       # Post-session scoring + clip compilation
│   │   ├── highlight_agent.py      # Highlight reel assembly with Timeline
│   │   ├── memory_agent.py         # SQLite + Graphiti persistence
│   │   ├── briefing_agent.py       # Pre-session note generation
│   │   └── ws_listener.py          # WebSocket listener subprocess
│   ├── api/
│   │   ├── session.py              # POST /session/start, /session/stop, GET /session/active
│   │   ├── analysis.py             # GET /analysis/{id}, /briefing/{player}, /history/{player}
│   │   ├── clips.py                # GET /clips/{id}, POST /clips/{id}/highlight
│   │   ├── suggestions.py          # GET /suggestions/{id}
│   │   └── discord.py              # Discord webhook helpers
│   ├── llm/
│   │   ├── interfaces.py           # BaseLLMProvider ABC
│   │   └── openrouter_provider.py  # OpenAI-compatible client for OpenRouter
│   ├── memory/
│   │   ├── interfaces.py           # BaseSessionStore, BaseGraphStore ABCs
│   │   ├── session_store.py        # SQLiteSessionStore
│   │   └── graph_store.py          # GraphitiGraphStore (Kuzu backend)
│   ├── schemas/
│   │   ├── session.py              # Session, Moment, Score, Clip, AnalysisResult, etc.
│   │   └── agent.py                # LLM output schemas (MomentDetection, AnalysisOutput, etc.)
│   ├── eval/
│   │   ├── judge.py                # Groq-based eval judge
│   │   ├── runner.py               # Eval runner (--no-judge for zero-key CI)
│   │   └── fixtures.py             # Pre-recorded events and sessions
│   ├── tests/                      # pytest unit tests (mocked LLM, no API keys needed)
│   ├── data/
│   │   ├── gamesense.db            # SQLite database (gitignored)
│   │   └── kuzu/                   # Graphiti graph database (gitignored)
│   ├── config.py                   # All env vars and constants
│   ├── main.py                     # FastAPI entry point
│   ├── sandbox_start.py            # Creates VideoDB sandbox, writes ID to .env
│   ├── sandbox_stop.py             # Stops the sandbox (run when done to save credits)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx
    │   │   └── page.tsx            # Root dashboard layout
    │   ├── components/
    │   │   ├── layout/
    │   │   │   └── Sidebar.tsx     # Nav, genre/game selector, record toggle, live cue feed
    │   │   ├── dashboard/
    │   │   │   ├── AllClipsScreen.tsx      # Clip grid by session with Skill Points
    │   │   │   ├── HighlightsScreen.tsx    # Highlight reel player
    │   │   │   ├── PerformanceScreen.tsx   # Trend charts + pre-session note
    │   │   │   ├── WrappedScreen.tsx       # Persona, epic summary, dimension scores
    │   │   │   └── RecordsScreen.tsx       # Raw moment and session records
    │   │   └── ui/
    │   │       ├── HlsPlayer.tsx   # hls.js wrapper for VideoDB stream URLs
    │   │       └── ...             # Shadcn components
    │   └── lib/
    │       ├── api.ts              # Typed API client
    │       ├── genres.ts           # Genre config, moment labels, Skill Points weights
    │       └── utils.ts
    └── package.json
```

---



## A Few Design Notes

**Why polling instead of WebSockets to the frontend.** The frontend polls every two seconds for session status and every five seconds for live cues. This is adequate for the update cadence that cues require, avoids managing a persistent WebSocket connection from the browser, and simplifies the server considerably.

**Why a separate judge model.** The Groq judge uses a different model family than the OpenRouter inference model. This avoids the well-documented self-evaluation bias where a model rates its own outputs more favourably than an independent evaluator would.

**Why structured output for every LLM call.** Every LLM call that returns data uses `complete_structured()` with a named JSON schema. Parse failures are recoverable with fallback values rather than pipeline-breaking exceptions.
