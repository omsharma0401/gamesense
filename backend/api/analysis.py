"""
api/analysis.py — Analysis, briefing, and history routes.

GET /analysis/{session_id}   — full analysis (score, clips, patterns, summary)
GET /briefing/{player_id}    — most recent pre-session coaching brief
GET /history/{player_id}     — last N sessions for Recharts trend graphs
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from schemas.session import AnalysisResult, Briefing, SessionSummary

logger = logging.getLogger(__name__)
router = APIRouter()


def get_store():
    from main import app
    return app.state.store


@router.get("/{session_id}", response_model=AnalysisResult)
async def get_analysis(session_id: str):
    """Return the full post-session analysis. Returns 202 if still processing."""
    store    = get_store()
    analysis = await store.get_analysis(session_id)

    if not analysis:
        # Check if the session exists at all
        session = await store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.status in ("active", "processing"):
            raise HTTPException(status_code=202, detail="Analysis still in progress")
        raise HTTPException(status_code=404, detail="Analysis not found")

    logger.info("Serving analysis — session=%s score=%d", session_id, analysis.score.overall)
    return analysis


@router.get("/briefing/{player_id}", response_model=Briefing)
async def get_briefing(player_id: str):
    """Return the latest coaching brief for a player."""
    store    = get_store()
    briefing = await store.get_latest_briefing(player_id)

    if not briefing:
        logger.info("No briefing found for player=%s — returning default", player_id)
        # Return a default briefing rather than 404, so the frontend always has something
        from schemas.session import Briefing
        return Briefing(
            player_id=player_id,
            coaching_paragraph=(
                "No session history yet. Play your first session and GameSense "
                "will build a personalised coaching brief just for you."
            ),
            focus_areas=["Play naturally", "Focus on one skill at a time", "Enjoy the game"],
            session_count=0,
        )

    logger.info("Serving briefing — player=%s sessions=%d", player_id, briefing.session_count)
    return briefing


@router.get("/history/{player_id}", response_model=list[SessionSummary])
async def get_history(
    player_id: str,
    limit: int = 10,
    game_name: Optional[str] = Query(None),
):
    """Return last `limit` sessions. Supports ?limit=N&game_name=Mario+Kart+8."""
    store   = get_store()
    history = await store.get_session_history(player_id, limit=limit, game_name=game_name)
    logger.info("Serving history — player=%s game=%s sessions=%d", player_id, game_name, len(history))
    return history


@router.get("/games/{player_id}", response_model=list[str])
async def get_games(player_id: str, genre: Optional[str] = Query(None)):
    """Return distinct game names recorded by a player, optionally filtered by genre."""
    store = get_store()
    games = await store.get_game_names(player_id, genre=genre)
    logger.info("Serving game names — player=%s genre=%s count=%d", player_id, genre, len(games))
    return games
