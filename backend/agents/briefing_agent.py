"""
agents/briefing_agent.py — Pre-session coaching brief generator.

Queries SQLite session history + Graphiti skill context for a player,
then asks the LLM to write a personalised coaching brief.
The brief is stored in SQLite and served by GET /briefing/{player_id}.
"""
from __future__ import annotations

import asyncio
import json
import logging

from agents.interfaces import BaseAgent
from llm.interfaces import BaseLLMProvider
from memory.interfaces import BaseSessionStore, BaseGraphStore
from schemas.session import Briefing, SessionSummary
from schemas.agent import BriefingOutput

logger = logging.getLogger(__name__)

_BRIEFING_SYSTEM_PROMPT = """You are a seasoned gaming coach texting your player before their next session. You sound like a real person — not a report generator.

RULES:
1. Write like you're texting a friend who games, not writing a performance review. Short sentences. Casual but sharp.
2. Reference what actually happened — mention kills, deaths, clutches, mistakes by describing the action, NOT by using the word "mechanics", "decision_making", "consistency", or "overall score". Those are internal labels, never say them out loud.
3. Name one specific thing they did well last session ("that 1v3 you pulled off near the end was clean") and one thing to watch ("you kept pushing the same angle after dying there twice — worth trying a different route").
4. End with a single concrete thing to focus on today — make it feel like advice from someone who watched the session, not a tip from a manual.
5. Focus areas: 2-4 SHORT cues (under 8 words each). These are things to think about mid-game, not categories. Example: "Reset after two bad plays in a row" or "Call the push before you peek".

NEVER use these words: mechanics, decision-making, consistency, overall score, performance metric, execution quality.

You MUST respond with a JSON object using EXACTLY these field names:
{
  "coaching_paragraph": "2-3 sentences. Conversational tone. Specific to what happened. One concrete focus for today.",
  "focus_areas": ["Short cue 1", "Short cue 2", "Short cue 3 (optional)", "Short cue 4 (optional)"]
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
            coaching_paragraph = output.coaching_paragraph
            focus_areas = output.focus_areas
        except Exception as exc:
            logger.warning("Failed to parse BriefingOutput, using fallback brief: %s | raw=%s", exc, raw[:200])
            try:
                data = json.loads(raw)
            except Exception:
                data = {}
            coaching_paragraph = data.get("coaching_paragraph") if isinstance(data, dict) and isinstance(data.get("coaching_paragraph"), str) else (
                "Your latest sessions are now logged. Focus on creating more clear, coachable moments this run so GameSense can build a sharper read on your strengths and mistakes."
            )
            focus_areas = data.get("focus_areas") if isinstance(data, dict) and isinstance(data.get("focus_areas"), list) else [
                "Create clear moments",
                "Recover after mistakes",
                "Stay consistent",
            ]
            focus_areas = [str(area) for area in focus_areas[:4]] or ["Play naturally", "Stay focused"]

        briefing = Briefing(
            player_id=self._player_id,
            coaching_paragraph=coaching_paragraph,
            focus_areas=focus_areas,
            session_count=len(history),
        )
        await self._store.save_briefing(briefing)
        logger.info(
            "Briefing generated — player=%s sessions_used=%d focus_areas=%d",
            self._player_id, len(history), len(focus_areas),
        )
        return briefing

    async def stop(self) -> None:
        pass  # runs once
