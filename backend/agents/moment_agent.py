"""
agents/moment_agent.py — Real-time key moment detection agent.

Polls /tmp/videodb_events.jsonl every MOMENT_POLL_INTERVAL seconds.
Uses byte-offset tracking (not line counting) for incremental reads,
so it never re-processes old events even if the file grows.

For each batch of new events:
  1. Sort by unix_ts (WebSocket delivery may be out of order)
  2. Pass the last MOMENT_CONTEXT_WINDOW events to the LLM
  3. If the LLM says is_moment=True, persist the Moment to SQLite

The frontend polls GET /session/{id} to see the live moment count.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from agents.interfaces import BaseAgent
from llm.interfaces import BaseLLMProvider
from memory.interfaces import BaseSessionStore
from schemas.session import Moment
from schemas.agent import MomentDetection
from config import (
    EVENTS_PATH,
    MOMENT_POLL_INTERVAL,
    MOMENT_CONTEXT_WINDOW,
)

logger = logging.getLogger(__name__)


_GENRE_CONTEXT = {
    "arcade-racing": (
        "This is an Arcade Racing game. "
        "Use `highlight` for clean overtakes or best laps, `clutch` for last-second recoveries or close finishes, "
        "`kill` for a dominant overtake, `death` for crashing or being passed badly, "
        "`error` for missed corners or poor lines, `strategy_break` for unexpected route/pit changes, "
        "`blunder` for major crashes or race-ending mistakes."
    ),
    "tactical-shooter": (
        "This is a Tactical Shooter (FPS). "
        "Use `kill` for frags/eliminations, `death` for the player dying, "
        "`clutch` for 1vN situations or low-HP recoveries, `error` for poor positioning or missed shots, "
        "`strategy_break` for mid-round strategy pivots, `highlight` for exceptional mechanical plays, "
        "`blunder` for team kills, throwing plays, or catastrophic mistakes."
    ),
    "rts": (
        "This is a Real-Time Strategy game. "
        "Use `kill` for successful unit trades or army wipes, `death` for losing a base or major army, "
        "`clutch` for clutch defenses under pressure, `error` for supply blocks or eco mistakes, "
        "`strategy_break` for tech switches or unexpected build orders, `highlight` for decisive battles, "
        "`blunder` for major strategic blunders."
    ),
    "turn-based-tactics": (
        "This is a Turn-Based Tactics game. "
        "Use `kill` for eliminating enemy units, `death` for losing a unit, "
        "`clutch` for winning against the odds in a single turn, `error` for tactical mistakes or wasted turns, "
        "`strategy_break` for unexpected strategy pivots, `highlight` for perfectly executed turns, "
        "`blunder` for friendly fire or catastrophic positioning errors."
    ),
}

_MOMENT_BASE_PROMPT = """You are an AI gaming coach watching live gameplay events.
Each event is a timestamped description of what the AI vision model saw on screen.

Your job: decide if the last batch of events contains a genuinely significant game moment.
Be selective — only tag events that a highlight reel editor would care about.
Filter out: loading screens, menus, spectator cam, idle periods, and minor events.

You MUST respond with a JSON object using EXACTLY these field names:
{{
  "is_moment": true or false,
  "type": one of "kill", "death", "clutch", "error", "strategy_break", "highlight", "blunder", or "none",
  "description": "brief description of what happened",
  "significance": integer 0-10 (0 if is_moment is false),
  "timestamp_ms": integer unix timestamp in milliseconds ({ts_note}),
  "commentary": "coaching insight or highlight reel commentary"
}}"""


def _build_system_prompt(genre: str) -> str:
    genre_ctx = _GENRE_CONTEXT.get(genre, "")
    ts_note = "absolute unix timestamp from the event, 0 if is_moment is false"
    return f"{genre_ctx}\n\n{_MOMENT_BASE_PROMPT.format(ts_note=ts_note)}"


def _build_moment_prompt(events: list[dict]) -> str:
    """
    Format events for the LLM.
    Skill event structure:
      {"channel": "scene_index", "data": {"text": "...", "start": 123, "end": 456}, "unix_ts": ...}
      {"channel": "audio_index", "data": {"text": "..."}}
      {"channel": "transcript",  "data": {"text": "...", "is_final": true}}
    """
    lines = []
    for e in events:
        channel = e.get("channel", e.get("event", "unknown"))
        text    = e.get("data", {}).get("text", "") if isinstance(e.get("data"), dict) else ""
        ts      = e.get("unix_ts", 0)
        if text:
            lines.append(f"[{ts:.1f}] [{channel.upper()}] {text}")
    formatted = "\n".join(lines) if lines else "(no text events in this batch)"
    return f"""Recent gameplay events (last {len(events)}, newest at bottom):

{formatted}

Is there a significant game moment here? Respond with the JSON schema."""


class MomentAgent(BaseAgent):
    """
    Polls the JSONL events file and detects key moments via LLM.

    Injects:
        llm:   LLM provider for moment classification
        store: Session store to persist detected moments
    """

    def __init__(
        self,
        session_id: str,
        genre: str,
        llm: BaseLLMProvider,
        store: BaseSessionStore,
        poll_interval: int = MOMENT_POLL_INTERVAL,
    ):
        self._session_id    = session_id
        self._genre         = genre
        self._llm           = llm
        self._store         = store
        self._poll_interval = poll_interval
        self._running       = False
        self._last_offset   = 0       # byte offset — reads only new lines
        self._moments_detected = 0
        self._system_prompt = _build_system_prompt(genre)

        logger.info(
            "MomentAgent created — session=%s genre=%s poll=%ds", session_id, genre, poll_interval
        )

    @property
    def moments_detected(self) -> int:
        return self._moments_detected

    async def run(self) -> None:
        """Poll the events file every poll_interval seconds until stop() is called."""
        self._running = True
        logger.info("MomentAgent started — polling every %ds", self._poll_interval)

        # Wait briefly for the events file to appear
        await self._wait_for_events_file()

        while self._running:
            try:
                await self._poll()
            except Exception as exc:
                logger.error("MomentAgent poll error: %s", exc, exc_info=True)

            await asyncio.sleep(self._poll_interval)

        logger.info(
            "MomentAgent stopped — total moments detected: %d", self._moments_detected
        )

    async def stop(self) -> None:
        if not self._running:
            return
        logger.info("MomentAgent stopping")
        self._running = False

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _wait_for_events_file(
        self, timeout: float = 120.0, poll: float = 2.0
    ) -> None:
        """Wait until the events file exists (written by ws_listener)."""
        deadline = time.monotonic() + timeout
        logger.info("Waiting for events file at %s", EVENTS_PATH)
        while time.monotonic() < deadline:
            if EVENTS_PATH.exists():
                logger.info("Events file ready")
                return
            await asyncio.sleep(poll)
        logger.warning(
            "Events file did not appear within %.0fs — proceeding anyway", timeout
        )

    async def _poll(self) -> None:
        """Read new events since the last poll and check for moments."""
        events = self._read_new_events()
        logger.debug("Poll cycle — read %d new events", len(events))

        if not events:
            return

        # Sort by unix_ts — WebSocket delivery may be out of order
        events.sort(key=lambda e: e.get("unix_ts", 0))

        # Keep the most recent context window
        context = events[-MOMENT_CONTEXT_WINDOW:]
        logger.debug("Sending %d events to LLM for moment detection", len(context))

        # Run LLM call in a thread to avoid blocking the event loop
        raw = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._llm.complete_structured(
                system=self._system_prompt,
                user=_build_moment_prompt(context),
                schema_name="moment_detection",
            ),
        )

        try:
            detection = MomentDetection.model_validate_json(raw)
        except Exception as exc:
            logger.warning("Failed to parse MomentDetection JSON: %s | raw=%s", exc, raw[:200])
            return

        logger.debug(
            "LLM detection result — is_moment=%s type=%s significance=%d",
            detection.is_moment, detection.type, detection.significance,
        )

        if not detection.is_moment or detection.type in (None, "none"):
            return

        # Persist the moment
        moment = Moment(
            session_id=self._session_id,
            type=detection.type,
            timestamp_ms=detection.timestamp_ms,
            description=detection.description,
            significance=detection.significance,
            commentary=detection.commentary,
        )
        await self._store.add_moment(moment)
        self._moments_detected += 1

        logger.info(
            "Moment #%d detected — type=%s ts=%dms sig=%d: %s",
            self._moments_detected,
            moment.type,
            moment.timestamp_ms,
            moment.significance,
            moment.description[:80],
        )

    def _read_new_events(self) -> list[dict]:
        """
        Read only new lines from the events file since the last poll.
        Uses byte-offset tracking — correct and fast regardless of file size.
        """
        if not EVENTS_PATH.exists():
            return []

        try:
            with open(EVENTS_PATH, "r") as f:
                f.seek(self._last_offset)
                new_lines = f.readlines()
                self._last_offset = f.tell()
        except OSError as exc:
            logger.warning("Could not read events file: %s", exc)
            return []

        events = []
        for line in new_lines:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.debug("Skipping malformed event line: %s", exc)

        return events
