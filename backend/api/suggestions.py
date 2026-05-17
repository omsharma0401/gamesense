"""
api/suggestions.py — Live coaching suggestion routes.

GET /suggestions/{session_id}           — all suggestions for a session
GET /suggestions/{session_id}?since_ms= — only suggestions after given epoch-ms
"""
import logging
from fastapi import APIRouter, Query
from schemas.session import Suggestion

logger = logging.getLogger(__name__)
router = APIRouter()


def get_store():
    from main import app
    return app.state.store


@router.get("/{session_id}", response_model=list[Suggestion])
async def get_suggestions(
    session_id: str,
    since_ms: int = Query(0, description="Epoch milliseconds — return only newer suggestions"),
):
    """Return live coaching suggestions for a session, optionally filtered by time."""
    store = get_store()
    suggestions = await store.get_suggestions(session_id, since_ms=since_ms)
    logger.debug("Serving %d suggestions — session=%s since_ms=%d", len(suggestions), session_id, since_ms)
    return suggestions
