"""
memory/interfaces.py — Abstract base classes for the persistence layer.

Swap SQLite for Postgres, or Kuzu for Neo4j, without touching any agent code.
Agents only ever hold BaseSessionStore or BaseGraphStore references.
"""
from abc import ABC, abstractmethod
from typing import Optional

from schemas.session import Session, SessionSummary, Moment, Briefing, AnalysisResult, HighlightReel


# ── Session Store — SQLite (structured, queryable stats) ──────────────────────

class BaseSessionStore(ABC):
    """
    Persistent store for structured session data.
    Backed by SQLite in production. In-memory dict for unit tests.
    """

    @abstractmethod
    async def init(self) -> None:
        """Create tables / indexes if they don't exist. Call once on startup."""
        ...

    # ── Session CRUD ──────────────────────────────────────────────────────────

    @abstractmethod
    async def create_session(self, session: Session) -> None:
        """Persist a new session row."""
        ...

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Fetch a session by ID. Returns None if not found."""
        ...

    @abstractmethod
    async def update_session(self, session: Session) -> None:
        """Overwrite all mutable fields on an existing session row."""
        ...

    @abstractmethod
    async def get_active_session(self) -> Optional[Session]:
        """Return the currently running session, or None."""
        ...

    @abstractmethod
    async def get_session_history(
        self, player_id: str, limit: int = 10
    ) -> list[SessionSummary]:
        """Return the last `limit` sessions for a player, newest first."""
        ...

    # ── Moment CRUD ───────────────────────────────────────────────────────────

    @abstractmethod
    async def add_moment(self, moment: Moment) -> None:
        """Append a detected moment to the moments table."""
        ...

    @abstractmethod
    async def get_moments(self, session_id: str) -> list[Moment]:
        """Return all moments for a session, ordered by timestamp_ms."""
        ...

    # ── Analysis ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def save_analysis(self, analysis: AnalysisResult) -> None:
        """Persist the complete post-session analysis."""
        ...

    @abstractmethod
    async def get_analysis(self, session_id: str) -> Optional[AnalysisResult]:
        """Fetch analysis for a session. Returns None if not yet complete."""
        ...

    # ── Briefing ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def save_briefing(self, briefing: Briefing) -> None:
        """Persist a coaching brief so the frontend can poll it."""
        ...

    @abstractmethod
    async def get_latest_briefing(self, player_id: str) -> Optional[Briefing]:
        """Return the most recent briefing for a player."""
        ...

    # ── Highlight Reel ────────────────────────────────────────────────────────

    @abstractmethod
    async def save_highlight_reel(self, reel: HighlightReel) -> None:
        """Persist highlight reel metadata (stream URL, status)."""
        ...

    @abstractmethod
    async def get_highlight_reel(self, session_id: str) -> Optional[HighlightReel]:
        """Return highlight reel for a session, or None if not generated."""
        ...


# ── Graph Store — Graphiti + Kuzu (temporal skill knowledge graph) ────────────

class BaseGraphStore(ABC):
    """
    Temporal knowledge graph for player skill evolution.
    Records how player strengths and weaknesses change across sessions.
    Backed by Graphiti + embedded Kuzu in production.

    IMPORTANT: add_episode() is slow (internal LLM call). Always call it via
    asyncio.create_task() — never await it in a request path.
    """

    @abstractmethod
    async def init(self) -> None:
        """Initialise the graph schema / indices. Call once on startup."""
        ...

    @abstractmethod
    async def add_episode(self, player_id: str, session_id: str, summary: str) -> None:
        """
        Add a session episode to the knowledge graph.
        Graphiti extracts entities and edges from the natural-language summary.

        Args:
            player_id:  Player the episode belongs to.
            session_id: Session ID for deduplication.
            summary:    Natural-language summary, e.g.:
                        'Session 6: B site clutch rate improved to 60%.
                         Recurring issue: overcommitting after going up 2-0.'
        """
        ...

    @abstractmethod
    async def get_skill_context(self, player_id: str, limit: int = 5) -> list[str]:
        """
        Query the graph for the player's most relevant recent skill episodes.
        Returns a list of natural-language episode strings for the briefing prompt.
        """
        ...
