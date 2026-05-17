"""
agents/briefing_agent.py — Pre-session coaching brief generator.

Queries SQLite session history + Graphiti skill context for a player,
then asks the LLM to write a personalised coaching brief.
The brief is stored in SQLite and served by GET /briefing/{player_id}.
"""
from __future__ import annotations

import asyncio
import logging

from agents.interfaces import BaseAgent
from llm.interfaces import BaseLLMProvider
from memory.interfaces import BaseSessionStore, BaseGraphStore
from schemas.session import Briefing, SessionSummary
from schemas.agent import BriefingOutput

logger = logging.getLogger(__name__)

_BRIEFING_SYSTEM_PROMPT = """You are a professional esports coach with access to a
player's full history. Write a personalised coaching brief for their next session.

Rules:
- Reference specific trends from their history (cite session numbers or score changes)
- Be concrete — not 'work on aim' but 'your B site entry rate has been dropping over 3 sessions'
- End with exactly one sentence of what to focus on today
- Focus areas: 2 to 4 bullet points, specific and actionable

You MUST respond with a JSON object using EXACTLY these field names:
{
  "coaching_paragraph": "personalised coaching paragraph drawing on history, ending with one actionable focus sentence",
  "focus_areas": ["specific area 1", "specific area 2", "optional area 3"]
}"""


def _build_briefing_prompt(player_id: str, history: list[SessionSummary], skill_context: list[str]) -> str:
    history_lines = "\n".join(
        f"  Session {i+1} ({s.genre}): score={s.score or 'N/A'} "
        f"mechanics={s.mechanics or 'N/A'} decisions={s.decision_making or 'N/A'} "
        f"consistency={s.consistency or 'N/A'} moments={s.moments_detected}"
        for i, s in enumerate(history)
    )
    graph_lines = "\n".join(f"  - {ep}" for ep in skill_context) if skill_context else "  No graph context yet."

    return (
        f"Player: {player_id}\n\n"
        f"Recent sessions (last {len(history)}, oldest first):\n{history_lines}\n\n"
        f"Skill evolution context from knowledge graph:\n{graph_lines}\n\n"
        "Write a personalised pre-session coaching brief."
    )


class BriefingAgent(BaseAgent):
    """Generates a personalised pre-session coaching brief from player history."""

    def __init__(
        self,
        player_id: str,
        llm: BaseLLMProvider,
        store: BaseSessionStore,
        graph: BaseGraphStore,
        history_limit: int = 6,
    ):
        self._player_id     = player_id
        self._llm           = llm
        self._store         = store
        self._graph         = graph
        self._history_limit = history_limit
        logger.info("BriefingAgent created — player=%s", player_id)

    async def run(self) -> Briefing:
        """Generate and persist a coaching brief. Returns the Briefing."""
        logger.info("BriefingAgent starting — player=%s", self._player_id)

        # 1. Fetch session history from SQLite
        history = await self._store.get_session_history(self._player_id, limit=self._history_limit)
        logger.info("Fetched %d historical sessions for briefing", len(history))

        if not history:
            logger.info("No history found — returning default briefing")
            briefing = Briefing(
                player_id=self._player_id,
                coaching_paragraph=(
                    "Welcome to GameSense! Play your first session and I'll build "
                    "a personalised brief based on your real gameplay data."
                ),
                focus_areas=["Play naturally", "Don't overthink", "Have fun"],
                session_count=0,
            )
            await self._store.save_briefing(briefing)
            return briefing

        # 2. Fetch skill context from Graphiti
        skill_context = await self._graph.get_skill_context(self._player_id, limit=5)
        logger.info("Fetched %d skill context episodes from graph", len(skill_context))

        # 3. Generate brief via LLM
        raw = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._llm.complete_structured(
                system=_BRIEFING_SYSTEM_PROMPT,
                user=_build_briefing_prompt(self._player_id, history, skill_context),
                schema_name="briefing_output",
            ),
        )

        try:
            output = BriefingOutput.model_validate_json(raw)
        except Exception as exc:
            logger.error("Failed to parse BriefingOutput: %s | raw=%s", exc, raw[:200])
            raise

        briefing = Briefing(
            player_id=self._player_id,
            coaching_paragraph=output.coaching_paragraph,
            focus_areas=output.focus_areas,
            session_count=len(history),
        )
        await self._store.save_briefing(briefing)
        logger.info(
            "Briefing generated — player=%s sessions_used=%d focus_areas=%d",
            self._player_id, len(history), len(output.focus_areas),
        )
        return briefing

    async def stop(self) -> None:
        pass  # runs once
