"""
api/session.py — Session lifecycle routes.

POST /session/start   — starts the three concurrent live agents
POST /session/stop    — stops agents, triggers post-session pipeline
GET  /session/active  — returns the running session (polled every 2s by frontend)
GET  /session/{id}    — returns session + live moment count
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks

from schemas.session import Session
from schemas.agent import SessionStartInput, SessionStopInput, LiveSessionStatus
from config import PLAYER_ID

logger = logging.getLogger(__name__)
router = APIRouter()

# ── State held in-process (single-user demo) ──────────────────────────────────
# In a multi-user system this would be a proper session manager.
_active_session: Session | None = None
_session_tasks: list[asyncio.Task] = []


def get_active_session() -> Session | None:
    return _active_session


def get_store():
    """Returns the SQLiteSessionStore from the app state."""
    from main import app
    return app.state.store


def get_llm():
    """Returns the LLM provider from the app state."""
    from main import app
    return app.state.llm


def get_graph():
    """Returns the graph store from the app state."""
    from main import app
    return app.state.graph


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/start", response_model=LiveSessionStatus)
async def start_session(body: SessionStartInput, background_tasks: BackgroundTasks):
    """Start a new GameSense session. Launches Capture + Indexing + Moment agents."""
    global _active_session, _session_tasks

    if _active_session:
        raise HTTPException(
            status_code=409,
            detail=f"A session is already active: {_active_session.id}",
        )

    logger.info("Starting session — genre=%s player=%s", body.genre, body.player_id)

    store = get_store()
    llm   = get_llm()

    # Create and persist the session row
    session = Session(player_id=body.player_id, genre=body.genre)
    await store.create_session(session)
    _active_session = session

    # Import agents here to avoid circular imports at module level
    from agents.capture_agent  import CaptureAgent
    from agents.indexing_agent import IndexingAgent
    from agents.moment_agent   import MomentAgent

    capture  = CaptureAgent(session.id, body.player_id, body.genre)
    indexing = IndexingAgent()
    moment   = MomentAgent(session.id, body.genre, llm, store)

    # Store agent refs on app state for stop route access
    from main import app
    app.state.capture_agent  = capture
    app.state.indexing_agent = indexing
    app.state.moment_agent   = moment

    async def run_agents():
        """Run capture + indexing + moment agents concurrently."""
        try:
            capture_task  = asyncio.create_task(capture.run())
            await capture.wait_for_active(timeout=90)   # wait for RTStream to be live
            indexing_task = asyncio.create_task(indexing.run())
            moment_task   = asyncio.create_task(moment.run())
            await asyncio.gather(capture_task, indexing_task, moment_task, return_exceptions=True)
        except Exception as exc:
            logger.error("Agent run loop failed: %s", exc, exc_info=True)

    # Launch agents as a background task (non-blocking)
    background_tasks.add_task(run_agents)

    logger.info("Session started — id=%s", session.id)
    return LiveSessionStatus(
        session_id=session.id,
        genre=session.genre,
        player_id=session.player_id,
        status="active",
        moments_detected=0,
        elapsed_seconds=0.0,
    )


@router.post("/stop")
async def stop_session(body: SessionStopInput, background_tasks: BackgroundTasks):
    """Stop the active session and trigger the post-session pipeline."""
    global _active_session

    if not _active_session or _active_session.id != body.session_id:
        raise HTTPException(status_code=404, detail="Session not found or not active")

    logger.info("Stopping session — id=%s", body.session_id)

    from main import app
    capture  = getattr(app.state, "capture_agent",  None)
    indexing = getattr(app.state, "indexing_agent", None)
    moment   = getattr(app.state, "moment_agent",   None)

    # Signal all live agents to stop
    for agent in [capture, indexing, moment]:
        if agent:
            await agent.stop()

    # Snapshot the session before clearing
    session = _active_session
    session.ended_at = datetime.utcnow()
    session.status   = "processing"
    _active_session  = None

    store = get_store()
    llm   = get_llm()
    graph = get_graph()

    await store.update_session(session)

    # Get the video_id from capture agent if available
    if capture and capture.video_id:
        session.video_id = capture.video_id
        await store.update_session(session)
        logger.info("Video exported — video_id=%s", session.video_id)

    # Run post-session pipeline in background
    background_tasks.add_task(run_post_session_pipeline, session, store, llm, graph, capture)

    logger.info("Session stopped — post-session pipeline queued")
    return {"status": "processing", "session_id": session.id}


@router.get("/active", response_model=LiveSessionStatus | None)
async def get_active():
    """Return the currently running session, or null. Polled every 2s by frontend."""
    session = _active_session
    if not session:
        return None

    from main import app
    moment_agent = getattr(app.state, "moment_agent", None)
    moments_detected = moment_agent.moments_detected if moment_agent else 0

    elapsed = (datetime.utcnow() - session.started_at).total_seconds()
    return LiveSessionStatus(
        session_id=session.id,
        genre=session.genre,
        player_id=session.player_id,
        status="active",
        moments_detected=moments_detected,
        elapsed_seconds=elapsed,
    )


@router.get("/{session_id}", response_model=LiveSessionStatus)
async def get_session(session_id: str):
    """Return session status and live moment count."""
    store   = get_store()
    session = await store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    moments = await store.get_moments(session_id)
    latest  = moments[-1].description if moments else None
    elapsed = (
        (session.ended_at or datetime.utcnow()) - session.started_at
    ).total_seconds()

    return LiveSessionStatus(
        session_id=session.id,
        genre=session.genre,
        player_id=session.player_id,
        status=session.status,
        moments_detected=len(moments),
        elapsed_seconds=elapsed,
        latest_moment=latest,
    )


# ── Post-session pipeline ─────────────────────────────────────────────────────

async def run_post_session_pipeline(session, store, llm, graph, capture=None):
    """
    Sequential post-session pipeline:
    AnalysisAgent → MemoryAgent → (HighlightAgent + BriefingAgent in parallel)
    """
    from agents.analysis_agent  import AnalysisAgent
    from agents.memory_agent    import MemoryAgent
    from agents.highlight_agent import HighlightAgent
    from agents.briefing_agent  import BriefingAgent

    logger.info("Post-session pipeline starting — session=%s", session.id)

    # Grace period — lets any in-progress MomentAgent poll finish writing to SQLite
    await asyncio.sleep(3.0)

    # Wait for CaptureAgent export (polls the live object — no file I/O race)
    if capture and not session.video_id:
        logger.info("Waiting for CaptureAgent export (up to 90s)...")
        deadline = asyncio.get_event_loop().time() + 90
        while asyncio.get_event_loop().time() < deadline:
            if capture.video_id:
                session.video_id = capture.video_id
                await store.update_session(session)
                logger.info("video_id ready — %s", session.video_id)
                break
            await asyncio.sleep(2.0)
        else:
            logger.warning("video_id not available after 90s")

    try:
        # 1. Analysis — score + clip compilation
        analysis_agent = AnalysisAgent(session, llm, store)
        analysis       = await analysis_agent.run()
        logger.info("Analysis complete — score=%d", analysis.score.overall)

        # 2. Memory — persist to SQLite + Graphiti
        memory_agent = MemoryAgent(session, analysis, store, graph)
        await memory_agent.run()

        # 3. Highlight reel + Briefing — run in parallel (both are independent)
        highlight_agent = HighlightAgent(session, analysis, store)
        briefing_agent  = BriefingAgent(session.player_id, llm, store, graph)
        await asyncio.gather(
            highlight_agent.run(),
            briefing_agent.run(),
            return_exceptions=True,
        )

        logger.info("Post-session pipeline complete — session=%s", session.id)

    except Exception as exc:
        logger.error("Post-session pipeline failed: %s", exc, exc_info=True)
        # Mark session as failed so frontend shows an error
        session.status = "failed"
        await store.update_session(session)
