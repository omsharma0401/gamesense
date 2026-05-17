"""
agents/live_coach_agent.py — Real-time coaching cues during a live session.

Runs concurrently with MomentAgent. Every 5 s it:
  1. Checks for new high-significance moments since last tick
  2. Runs pattern detection on rolling moment history
  3. If a trigger fires AND cooldown has passed → LLM generates a short cue
  4. Persists to suggestions table, delivers via macOS notification + Discord

Delivery:
  - macOS system notification banner (appears over any app, incl. fullscreen games)
  - Discord webhook (persistent log + secondary channel)
Logging: /tmp/gamesense_coach.log — tail this during a session to debug.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from agents.interfaces import BaseAgent
from config import DISCORD_WEBHOOK_URL
from memory.interfaces import BaseSessionStore
from llm.interfaces import BaseLLMProvider
from schemas.session import Moment, Session, Suggestion

logger = logging.getLogger(__name__)

# Dedicated file log for live coaching — easy to tail during a session
_coach_log = logging.getLogger("gamesense.coach")
_fh = logging.FileHandler("/tmp/gamesense_coach.log")
_fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
_coach_log.addHandler(_fh)
_coach_log.setLevel(logging.INFO)

COOLDOWN_SECONDS  = 15        # min gap between any two suggestions
PATTERN_CHECK_INTERVAL = 30   # how often to run pattern detection
TICK_INTERVAL     = 5         # polling interval
HIGH_SIG_BYPASS   = 9         # significance >= this bypasses cooldown

_SYSTEM_PROMPT = """\
You are a live in-game voice coach delivering real-time feedback through Discord overlay.
Generate exactly ONE coaching cue — 8 to 12 words maximum.

Tone rules (match the trigger type):
- hype   (kills/streaks):        high energy, stadium broadcast — "Back to back. Don't slow down."
- warning (deaths/overextend):   calm and direct — "You're over-committing. Reset before next push."
- tip    (tactical/pattern):     specific and actionable — "Stay near cover — you're getting caught open."
- focus  (idle/no moments):      quiet and refocusing — "Stay locked in. The play is coming."

Genre context will be provided. Use genre-appropriate language.
Output the cue ONLY. No quotes. No emojis. End with a period."""

# Trigger → suggestion type mapping
_TYPE_MAP: dict[str, str] = {
    "moment:clutch":           "hype",
    "moment:kill":             "hype",
    "moment:highlight":        "hype",
    "moment:death":            "warning",
    "moment:blunder":          "warning",
    "moment:error":            "warning",
    "moment:strategy_break":   "tip",
    "pattern:kill_streak":     "hype",
    "pattern:overextending":   "warning",
    "pattern:consecutive_neg": "warning",
    "pattern:idle":            "focus",
    "pattern:improving":       "hype",
}


def _infer_type(trigger: str) -> str:
    return _TYPE_MAP.get(trigger, "tip")


class LiveCoachAgent(BaseAgent):
    """Emits real-time coaching suggestions during an active session."""

    def __init__(
        self,
        session: Session,
        llm: BaseLLMProvider,
        store: BaseSessionStore,
    ):
        self._session     = session
        self._llm         = llm
        self._store       = store
        self._running     = False

        self._last_suggestion_at: float = 0.0
        self._last_pattern_check: float = 0.0
        self._last_moment_ts: int       = 0      # high-water mark for new moments
        self._processed_moment_ids: set[str] = set()

        _coach_log.info(
            "LiveCoachAgent started — session=%s genre=%s game=%s",
            session.id, session.genre, session.game_name or "—",
        )

    async def run(self) -> None:
        self._running = True
        logger.info("LiveCoachAgent running — session=%s", self._session.id)
        while self._running:
            await asyncio.sleep(TICK_INTERVAL)
            try:
                await self._tick()
            except Exception as exc:
                logger.warning("LiveCoachAgent tick error: %s", exc)

    async def stop(self) -> None:
        self._running = False
        logger.info("LiveCoachAgent stopped — session=%s", self._session.id)

    # ── Main tick ─────────────────────────────────────────────────────────────

    async def _tick(self) -> None:
        moments = await self._store.get_moments(self._session.id)
        if not moments:
            return

        now = time.monotonic()
        now_ms = time.time() * 1000
        cooldown_ok = (now - self._last_suggestion_at) >= COOLDOWN_SECONDS

        # New moments since last tick
        new_moments = [m for m in moments if m.id not in self._processed_moment_ids]
        for m in new_moments:
            self._processed_moment_ids.add(m.id)

        trigger_text: Optional[str] = None
        trigger_key:  Optional[str] = None

        # ── 1. High-significance new moment ───────────────────────────────────
        if new_moments:
            best = max(new_moments, key=lambda m: m.significance)
            sig  = best.significance
            if sig >= 6 and (cooldown_ok or sig >= HIGH_SIG_BYPASS):
                trigger_key  = f"moment:{best.type}"
                trigger_text = (
                    f"{best.type} moment (significance {sig}/10): {best.description}"
                )
                _coach_log.info("Trigger: moment — %s sig=%d", best.type, sig)

        # ── 2. Pattern detection (every PATTERN_CHECK_INTERVAL s) ─────────────
        if not trigger_key and (now - self._last_pattern_check) >= PATTERN_CHECK_INTERVAL:
            self._last_pattern_check = now
            pattern = self._detect_pattern(moments, now_ms)
            if pattern and cooldown_ok:
                trigger_key, trigger_text = pattern
                _coach_log.info("Trigger: pattern — %s", trigger_key)

        if not trigger_key:
            return

        # ── 3. Generate + deliver ──────────────────────────────────────────────
        suggestion = await self._generate(trigger_key, trigger_text, moments)
        if suggestion:
            await self._store.save_suggestion(suggestion)
            asyncio.create_task(self._deliver(suggestion))
            self._last_suggestion_at = now
            _coach_log.info(
                "[%s] %s  (trigger=%s)",
                suggestion.type.upper(), suggestion.text, suggestion.trigger,
            )

    # ── Pattern detection ─────────────────────────────────────────────────────

    def _detect_pattern(
        self, moments: list[Moment], now_ms: float
    ) -> Optional[tuple[str, str]]:
        five_min_ago = now_ms - 5 * 60 * 1000
        one_min_ago  = now_ms - 60 * 1000
        three_min_ago = now_ms - 3 * 60 * 1000

        recent_5m = [m for m in moments if m.timestamp_ms > five_min_ago]
        recent_1m = [m for m in moments if m.timestamp_ms > one_min_ago]

        neg_types = {"death", "blunder", "error"}
        pos_types = {"kill", "clutch", "highlight"}

        deaths_5m = [m for m in recent_5m if m.type in neg_types]
        kills_5m  = [m for m in recent_5m if m.type in pos_types]

        # 3+ deaths in 5 minutes
        if len(deaths_5m) >= 3:
            return (
                "pattern:overextending",
                f"{len(deaths_5m)} deaths/blunders in the last 5 minutes — player is overextending",
            )

        # 3+ kills in 5 minutes
        if len(kills_5m) >= 3:
            return (
                "pattern:kill_streak",
                f"{len(kills_5m)} kills/highlights in the last 5 minutes — player is on fire",
            )

        # 2+ negatives in last 60 seconds
        neg_1m = [m for m in recent_1m if m.type in neg_types]
        if len(neg_1m) >= 2:
            return (
                "pattern:consecutive_neg",
                "two negative events in 60 seconds — player needs to reset",
            )

        # Idle: no moments in 3 minutes
        if moments:
            last_ts = moments[-1].timestamp_ms
            if (now_ms - last_ts) > 3 * 60 * 1000:
                return (
                    "pattern:idle",
                    "no notable moments in over 3 minutes — engagement dropping",
                )

        # Positive run: last 3 moments all positive
        last_3 = moments[-3:]
        if len(last_3) == 3 and all(m.type in pos_types for m in last_3):
            return (
                "pattern:improving",
                "last three moments all positive — player is clicking in",
            )

        return None

    # ── LLM generation ───────────────────────────────────────────────────────

    async def _generate(
        self,
        trigger_key: str,
        trigger_text: str,
        moments: list[Moment],
    ) -> Optional[Suggestion]:
        stype = _infer_type(trigger_key)
        genre = self._session.genre
        game  = self._session.game_name or genre

        # Build brief recent context (last 3 moments)
        context_lines = [
            f"  - [{m.type}] sig={m.significance}: {m.description}"
            for m in moments[-3:]
        ]
        context = "\n".join(context_lines) or "  (no prior moments)"

        user_prompt = (
            f"Game: {game} ({genre})\n"
            f"Trigger: {trigger_text}\n"
            f"Tone required: {stype}\n"
            f"Recent moments:\n{context}\n\n"
            "Generate the coaching cue now."
        )

        try:
            text = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._llm.complete(_SYSTEM_PROMPT, user_prompt).strip(),
            )
            # Strip stray quotes the LLM sometimes adds
            text = text.strip('"').strip("'").strip()
            if not text:
                return None

            return Suggestion(
                session_id=self._session.id,
                text=text,
                type=stype,  # type: ignore[arg-type]
                trigger=trigger_key,
                significance=7,
            )
        except Exception as exc:
            logger.warning("LLM generation failed for coaching cue: %s", exc)
            return None

    # ── Delivery ──────────────────────────────────────────────────────────────

    async def _deliver(self, suggestion: Suggestion) -> None:
        """Fire macOS notification banner + Discord webhook in parallel."""
        await asyncio.gather(
            self._notify_macos(suggestion),
            self._notify_discord(suggestion),
            return_exceptions=True,
        )

    async def _notify_macos(self, suggestion: Suggestion) -> None:
        """macOS system notification — appears over any app, incl. fullscreen games."""
        icons  = {"hype": "🔥", "warning": "⚠️", "tip": "💡", "focus": "🎯"}
        labels = {"hype": "On fire", "warning": "Watch out", "tip": "Tip", "focus": "Focus"}
        icon   = icons.get(suggestion.type, "📡")
        label  = labels.get(suggestion.type, "Coach")
        # Escape double-quotes so osascript doesn't break
        safe_text  = suggestion.text.replace('"', "'")
        safe_label = f"{icon} {label}"
        script = (
            f'display notification "{safe_text}" '
            f'with title "GameSense" '
            f'subtitle "{safe_label}" '
            f'sound name "Glass"'
        )
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["osascript", "-e", script],
                    timeout=3, capture_output=True,
                ),
            )
        except Exception as exc:
            logger.debug("macOS notification failed: %s", exc)

    async def _notify_discord(self, suggestion: Suggestion) -> None:
        """Discord webhook — persistent log in your server channel."""
        if not DISCORD_WEBHOOK_URL:
            return
        icons = {"hype": "🔥", "warning": "⚠️", "tip": "💡", "focus": "🎯"}
        icon  = icons.get(suggestion.type, "📡")
        game  = self._session.game_name or self._session.genre
        colors = {"hype": 0x4ade80, "warning": 0xf87171, "tip": 0xfbbf24, "focus": 0x60a5fa}

        payload = {
            "username": "GameSense Coach",
            "embeds": [{
                "description": f"**{suggestion.text}**",
                "color": colors.get(suggestion.type, 0xccff00),
                "footer": {"text": f"{icon}  {game} · live coaching"},
            }],
        }
        try:
            async with httpx.AsyncClient() as client:
                await client.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5.0)
        except Exception as exc:
            logger.debug("Discord delivery failed: %s", exc)
