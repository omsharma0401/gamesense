"""
api/clips.py — Clip retrieval and highlight reel routes.

GET  /clips/{session_id}              — all clips with stream URLs
POST /clips/{session_id}/highlight    — trigger highlight reel generation
GET  /clips/highlight/{session_id}    — get highlight reel status + stream URL
"""
import asyncio
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from schemas.session import Clip, HighlightReel, AnalysisResult

logger = logging.getLogger(__name__)
router = APIRouter()


def get_store():
    from main import app
    return app.state.store

def get_llm():
    from main import app
    return app.state.llm


@router.get("/{session_id}", response_model=list[Clip])
async def get_clips(session_id: str):
    """Return all compiled clips for a session."""
    store    = get_store()
    analysis = await store.get_analysis(session_id)

    if not analysis:
        session = await store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.status in ("active", "processing"):
            return []   # Still processing — return empty list
        return []   # Analysis failed — return empty list

    logger.info("Serving %d clips — session=%s", len(analysis.clips), session_id)
    return analysis.clips


@router.post("/{session_id}/highlight", response_model=HighlightReel)
async def trigger_highlight(session_id: str, background_tasks: BackgroundTasks):
    """Trigger highlight reel generation if not already running."""
    store = get_store()
    existing = await store.get_highlight_reel(session_id)

    if existing and existing.status in ("generating", "complete"):
        logger.info("Highlight already %s — session=%s", existing.status, session_id)
        return existing

    analysis = await store.get_analysis(session_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found — run session first")

    session = await store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info("Triggering highlight reel — session=%s", session_id)

    async def generate():
        from agents.highlight_agent import HighlightAgent
        agent = HighlightAgent(session, analysis, store)
        await agent.run()

    background_tasks.add_task(generate)

    # Return pending status immediately
    reel = HighlightReel(session_id=session_id, status="generating")
    await store.save_highlight_reel(reel)
    return reel


@router.get("/highlight/{session_id}", response_model=HighlightReel)
async def get_highlight(session_id: str):
    """Poll this endpoint to check highlight reel status and get the stream URL."""
    store = get_store()
    reel  = await store.get_highlight_reel(session_id)

    if not reel:
        raise HTTPException(status_code=404, detail="Highlight reel not generated yet")

    logger.info("Serving highlight reel — session=%s status=%s", session_id, reel.status)
    return reel


@router.post("/highlight/{session_id}/vertical", response_model=HighlightReel)
async def trigger_vertical_highlight(session_id: str, background_tasks: BackgroundTasks):
    """Trigger 9:16 vertical reframe of the highlight reel (for Reels/TikTok sharing)."""
    store = get_store()
    reel  = await store.get_highlight_reel(session_id)

    if not reel or reel.status != "complete":
        raise HTTPException(status_code=404, detail="Landscape highlight reel not ready yet")

    if reel.vertical_stream_url:
        logger.info("Vertical highlight already exists — session=%s", session_id)
        return reel

    session  = await store.get_session(session_id)
    analysis = await store.get_analysis(session_id)
    if not session or not analysis:
        raise HTTPException(status_code=404, detail="Session or analysis not found")

    logger.info("Triggering vertical highlight — session=%s", session_id)

    async def generate():
        from agents.highlight_agent import HighlightAgent
        agent = HighlightAgent(session, analysis, store)
        await agent._generate_vertical(reel, analysis.clips)

    background_tasks.add_task(generate)
    return reel
