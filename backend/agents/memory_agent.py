"""
agents/memory_agent.py — Persists session analysis to SQLite and Graphiti.

Runs after AnalysisAgent. Responsibilities:
  1. Update the Session row in SQLite with final scores and status
  2. Fire-and-forget: add a skill episode to Graphiti (this calls the LLM
     internally — we never await it in the request path)

The Graphiti episode is a natural-language summary of the session that the
temporal knowledge graph uses to track how the player's skills change over time.
"""
from __future__ import annotations

import asyncio
import logging

from agents.interfaces import BaseAgent
from memory.interfaces import BaseSessionStore, BaseGraphStore
from schemas.session import Session, AnalysisResult

logger = logging.getLogger(__name__)


def _build_episode_summary(session: Session, analysis: AnalysisResult) -> str:
    """
    Build a natural-language episode string for the knowledge graph.
    Graphiti extracts entities and temporal relationships from this text.
    """
    pattern_lines = "\n".join(f"  - {p}" for p in analysis.patterns)
    blunders = [m for m in analysis.moments if m.type == "blunder"]
    clutches  = [m for m in analysis.moments if m.type == "clutch"]

    return (
        f"GameSense Session (genre={session.genre}, player={session.player_id}):\n"
        f"Overall score: {analysis.score.overall}/100 "
        f"(mechanics={analysis.score.mechanics}, "
        f"decision_making={analysis.score.decision_making}, "
        f"consistency={analysis.score.consistency})\n"
        f"Moments detected: {len(analysis.moments)} "
        f"(clutches={len(clutches)}, blunders={len(blunders)})\n"
        f"Session summary: {analysis.summary}\n"
        f"Recurring patterns identified:\n{pattern_lines or '  None identified.'}"
    )


class MemoryAgent(BaseAgent):
    """
    Persists analysis results to SQLite and (async) to Graphiti.

    Injects:
        session:  The completed session object
        analysis: AnalysisResult from AnalysisAgent
        store:    Session store (SQLite)
        graph:    Graph store (Graphiti + Kuzu)
    """

    def __init__(
        self,
        session: Session,
        analysis: AnalysisResult,
        store: BaseSessionStore,
        graph: BaseGraphStore,
    ):
        self._session  = session
        self._analysis = analysis
        self._store    = store
        self._graph    = graph
        logger.info("MemoryAgent created — session=%s", session.id)

    async def run(self) -> None:
        """Persist the analysis. Fires the Graphiti episode as a background task."""
        logger.info("MemoryAgent starting — session=%s", self._session.id)

        # 1. Update session row with final scores and status
        self._session.score             = self._analysis.score
        self._session.status            = "complete"
        self._session.moments_detected  = len(self._analysis.moments)

        await self._store.update_session(self._session)
        logger.info(
            "Session updated in SQLite — id=%s score=%d",
            self._session.id, self._analysis.score.overall,
        )

        # 2. Save the full analysis blob
        await self._store.save_analysis(self._analysis)
        logger.info("Analysis saved to SQLite — session=%s", self._session.id)

        # 3. Fire-and-forget: add episode to Graphiti
        # add_episode() calls the LLM internally — never await on a request path
        episode_summary = _build_episode_summary(self._session, self._analysis)
        asyncio.create_task(
            self._graph.add_episode(
                player_id=self._session.player_id,
                session_id=self._session.id,
                summary=episode_summary,
            )
        )
        logger.info(
            "Graphiti episode queued (fire-and-forget) — player=%s",
            self._session.player_id,
        )

        logger.info("MemoryAgent complete")

    async def stop(self) -> None:
        """No-op — MemoryAgent runs once."""
        pass
