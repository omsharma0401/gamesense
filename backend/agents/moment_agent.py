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
        "GENRE: Arcade Racing.\n"
        "MOMENT TYPES:\n"
        "  `highlight` — A clean, textbook overtake or a new personal best lap. The kind of line that makes a pro nod.\n"
        "  `clutch` — Last-second save: drafted past on the final straight, recovered from a near-crash, or held off a chase for 2+ laps.\n"
        "  `kill` — A dominant, clinical overtake — left the opponent with zero chance to respond.\n"
        "  `death` — Crashed hard, spun out, or got overtaken in an embarrassing way. Position lost.\n"
        "  `error` — Missed apex, braked too late, clipped a wall, or ran wide. Cost time.\n"
        "  `strategy_break` — Switched racing line mid-race, took an unexpected shortcut, changed tactic.\n"
        "  `blunder` — Major crash, collision that ended a run, or catastrophic position loss in one incident.\n"
        "SIGNIFICANCE GUIDE: Overtaking for 1st place late = 9-10. Overtaking for top 5 = 7-8. Minor position change = 4-6. Clip wall = 3. Loading screen = 0."
    ),
    "tactical-shooter": (
        "GENRE: Tactical Shooter (FPS/Tactical).\n"
        "MOMENT TYPES:\n"
        "  `kill` — Clean frag or elimination. Extra weight if it's through smoke, long range, or clutch timing.\n"
        "  `death` — Player eliminated. Note if it was avoidable (poor positioning, peeked too early).\n"
        "  `clutch` — 1vN scenario (player vs multiple opponents), or surviving with near-zero HP. Heart-pounding.\n"
        "  `highlight` — Exceptional mechanical play: no-scope, spray transfer, prefiring blind, pixel-perfect flick.\n"
        "  `error` — Repositioning mistake, peeked too early, threw a grenade poorly, rotated wrong.\n"
        "  `strategy_break` — Mid-round shift: eco to force-buy, abandoned plant site, unexpected rotate, fake.\n"
        "  `blunder` — Team kill, weapon drop at wrong moment, failed plant/defuse, round-ending mistake under pressure.\n"
        "SIGNIFICANCE GUIDE: 1v3+ clutch = 9-10. Entry frag or ace = 8-9. Clean 2-tap = 6-7. Standard kill = 4-5. Menu/loadout screen = 0."
    ),
    "rts": (
        "GENRE: Real-Time Strategy.\n"
        "MOMENT TYPES:\n"
        "  `kill` — Successful army engagement: wiped enemy units, took out a key structure.\n"
        "  `death` — Lost a major army, base structure destroyed, or key unit eliminated.\n"
        "  `clutch` — Held off an attack with inferior forces, last-minute resource shift that turned the game.\n"
        "  `highlight` — Perfectly executed build order, map control established, or decisive tech advantage secured.\n"
        "  `error` — Supply block, mineral float (over-saturation), missed attack timing, or poor unit positioning.\n"
        "  `strategy_break` — Tech tree pivot, unexpected all-in, hidden expansion, or timing attack.\n"
        "  `blunder` — Lost macro advantage, base traded badly, catastrophic army loss from miscontrol.\n"
        "SIGNIFICANCE GUIDE: Army wipe / base destruction = 9-10. Major skirmish win = 7-8. Supply block = 4-5. Small scout lost = 2-3."
    ),
    "turn-based-tactics": (
        "GENRE: Turn-Based Tactics.\n"
        "MOMENT TYPES:\n"
        "  `kill` — Enemy unit eliminated, especially a high-value target.\n"
        "  `death` — Player unit lost — was it avoidable? Note if the unit was overexposed.\n"
        "  `clutch` — Turn where a seemingly lost situation was reversed, often with precise multi-unit coordination.\n"
        "  `highlight` — Perfect ambush, flanking manoeuvre that broke the line, or a setup that created a domino effect.\n"
        "  `error` — Wasted action (unit moved but couldn't act), friendly unit trapped, or missed optimal move.\n"
        "  `strategy_break` — Full pivot in tactical approach, gave up a position strategically, or used an unexpected ability chain.\n"
        "  `blunder` — Friendly fire, catastrophic positioning (unit isolated and killed), or missed win condition.\n"
        "SIGNIFICANCE GUIDE: Clutch reversal = 9-10. High-value kill = 7-8. Setup move = 5-6. Minor tactical gain = 3-4."
    ),
}

_MOMENT_BASE_PROMPT = """You are a live esports broadcast analyst watching real-time gameplay events from an AI vision feed.
Your job: identify genuinely significant game moments that belong in a highlight reel.

STRICT FILTERS — return is_moment=false for:
  - Loading screens, menus, inventory/loadout screens
  - Spectator cam or other players' perspectives
  - Idle periods, cutscenes, map transitions
  - Minor position adjustments or routine actions

Only flag events a broadcast director would cut to. Be selective — quality over quantity.

COMMENTARY GUIDE — write commentary like a live esports caster:
  - Use present tense: "He HOLDS the angle", "She THREADS the needle"
  - Punchy and vivid: "Silky smooth", "No hesitation", "Textbook execution"
  - For errors: honest but constructive: "Pushed too early — classic over-aggression"
  - For blunders: "Oh no — that's a round-ending mistake right there"
  - Keep it to 1-2 sentences maximum

You MUST respond with a JSON object using EXACTLY these field names:
{{
  "is_moment": true or false,
  "type": one of "kill", "death", "clutch", "error", "strategy_break", "highlight", "blunder", or "none",
  "description": "Concrete factual description of exactly what happened and what it means for the game state",
  "significance": integer 0-10 (0 if is_moment is false, see genre significance guide above),
  "timestamp_ms": integer unix timestamp in milliseconds ({ts_note}),
  "commentary": "Broadcast-style caster commentary, 1-2 sentences, present tense, vivid language"
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
