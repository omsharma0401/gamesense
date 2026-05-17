"""
agents/interfaces.py — Abstract base class for all GameSense agents.

Every agent implements this interface. The session orchestrator in main.py
only ever holds BaseAgent references — never concrete classes.
"""
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """
    A GameSense agent — an autonomous unit with a run/stop lifecycle.

    During-session agents (Capture, Indexing, Moment) run concurrently via
    asyncio.gather() and are stopped when the player clicks 'End Session'.

    Post-session agents (Analysis, Memory, Highlight, Briefing) run as a
    sequential pipeline after the session ends.
    """

    @abstractmethod
    async def run(self) -> None:
        """
        Start the agent's main loop.

        For live agents: blocks until stop() is called.
        For post-session agents: runs once and returns.
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """
        Signal the agent to stop and clean up.
        Must be idempotent — calling stop() twice is safe.
        """
        ...

    @property
    def name(self) -> str:
        """Human-readable agent name for logging."""
        return self.__class__.__name__
