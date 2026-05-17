"""
memory/graph_store.py — Graphiti + embedded Kuzu temporal knowledge graph.

Stores player skill evolution as episodes. Each session produces one episode:
  "Session 7 (CS2): B site clutch rate improved to 60%. Persistent weakness:
   overcommitting after going up 2-0 in rounds."

Graphiti extracts entities and temporal edges from these summaries, building
a graph that tracks HOW skills change over time — not just what they are now.

CRITICAL: add_episode() calls the LLM internally (entity extraction).
Always call via asyncio.create_task(), never await in a request path.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from memory.interfaces import BaseGraphStore
from config import (
    KUZU_DB_PATH,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    OPENROUTER_BASE_URL,
)

logger = logging.getLogger(__name__)


class GraphitiGraphStore(BaseGraphStore):
    """
    Temporal knowledge graph backed by Graphiti + embedded Kuzu.
    No Docker required — Kuzu runs embedded in-process.
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = str(db_path or KUZU_DB_PATH)
        self._graphiti: object | None = None  # graphiti_core.Graphiti, typed loosely to avoid import at module level
        logger.info("GraphitiGraphStore configured — db=%s", self._db_path)

    async def init(self) -> None:
        """Initialise the Graphiti instance and build the graph schema."""
        logger.info("Initialising Graphiti graph at %s", self._db_path)
        try:
            from graphiti_core import Graphiti
            from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
            from graphiti_core.llm_client.config import LLMConfig

            from graphiti_core.driver.kuzu_driver import KuzuDriver
            from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
            from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

            llm_config = LLMConfig(
                api_key=OPENROUTER_API_KEY,
                model=OPENROUTER_MODEL,
                base_url=OPENROUTER_BASE_URL,
            )
            llm_client = OpenAIGenericClient(config=llm_config, max_tokens=512)
            embedder = OpenAIEmbedder(
                config=OpenAIEmbedderConfig(
                    api_key=OPENROUTER_API_KEY,
                    base_url=OPENROUTER_BASE_URL,
                )
            )
            cross_encoder = OpenAIRerankerClient(config=llm_config)
            self._graphiti = Graphiti(
                graph_driver=KuzuDriver(db=self._db_path),
                llm_client=llm_client,
                embedder=embedder,
                cross_encoder=cross_encoder,
            )
            await self._graphiti.build_indices_and_constraints()
            logger.info("Graphiti graph initialised successfully")

        except ImportError as exc:
            logger.error(
                "graphiti-core not installed — graph store will be disabled: %s", exc
            )
            self._graphiti = None
        except Exception as exc:
            logger.error("Graphiti init failed: %s", exc)
            self._graphiti = None

    async def add_episode(self, player_id: str, session_id: str, summary: str) -> None:
        """
        Add a session episode to the knowledge graph.

        This method calls the LLM internally (entity + edge extraction).
        Always call via asyncio.create_task() — never await on the request path.

        Example episode text:
          'CS2 Session 7 [player-001]: Overall score 74/100.
           B site clutch rate has improved significantly over the last 3 sessions.
           Recurring blunder: pushing the same corner 3+ times and dying each time.
           Decision-making score dropped compared to session 6.'
        """
        if self._graphiti is None:
            logger.warning(
                "Graphiti not available — skipping episode for session=%s", session_id
            )
            return

        episode_name = f"{player_id}::{session_id}"
        logger.info(
            "Adding graph episode — player=%s session=%s chars=%d",
            player_id, session_id, len(summary),
        )
        try:
            from datetime import datetime
            await self._graphiti.add_episode(
                name=episode_name,
                episode_body=summary,
                source_description=f"GameSense session analysis for player {player_id}",
                reference_time=datetime.utcnow(),
            )
            logger.info("Graph episode added — player=%s session=%s", player_id, session_id)
        except Exception as exc:
            # Never let graph failures break the main pipeline
            logger.error(
                "Failed to add graph episode for session=%s: %s", session_id, exc
            )

    async def get_skill_context(self, player_id: str, limit: int = 5) -> list[str]:
        """
        Search the graph for the player's most relevant skill episodes.
        Returns natural-language strings passed directly into the briefing prompt.
        """
        if self._graphiti is None:
            logger.warning("Graphiti not available — returning empty skill context")
            return []

        query = f"What are {player_id}'s strengths, weaknesses, and recent skill changes?"
        logger.info("Querying graph for player context — player=%s", player_id)
        try:
            results = await self._graphiti.search(query=query, num_results=limit)
            # Graphiti returns structured results; extract the fact text
            episodes: list[str] = []
            for result in results:
                fact = getattr(result, "fact", None) or getattr(result, "content", str(result))
                if fact:
                    episodes.append(str(fact))

            logger.info("Graph context fetched — player=%s episodes=%d", player_id, len(episodes))
            return episodes

        except Exception as exc:
            logger.error("Graph search failed for player=%s: %s", player_id, exc)
            return []
