"""
agents/capture_agent.py — Screen capture lifecycle agent.

Uses the correct VideoDB Capture SDK flow as documented in:
  .agents/skills/videodb/reference/capture.md
  .agents/skills/videodb/reference/capture-reference.md

Correct flow:
  1. Launch ws_listener.py (skill script) in background → gets WebSocket ID
  2. Wait for /tmp/videodb_ws_id to be written
  3. conn.create_capture_session(end_user_id, ws_connection_id=ws_id)
  4. conn.generate_client_token()
  5. CaptureClient(token) → request permissions → list channels → start_capture_session()
  6. Poll /tmp/videodb_events.jsonl for capture_session.active event
     → save rtstream IDs to /tmp/videodb_capture_info.json for IndexingAgent
  7. On stop: client.stop_capture() → client.shutdown()
     → poll for capture_session.exported → save video_id
  8. Kill ws_listener (kill $(cat /tmp/videodb_ws_pid))
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agents.interfaces import BaseAgent
from config import (
    VIDEO_DB_API_KEY,
    EVENTS_PATH,
    CAPTURE_INFO_PATH,
    ROOT_DIR,
)

logger = logging.getLogger(__name__)

WS_ID_FILE  = Path("/tmp/videodb_ws_id")
WS_PID_FILE = Path("/tmp/videodb_ws_pid")


class CaptureAgent(BaseAgent):
    """
    Manages the full VideoDB desktop capture lifecycle:
    ws_listener → CaptureSession → CaptureClient → active → stop → exported.

    Video IDs become available after the capture_session.exported event.
    """

    def __init__(self, session_id: str, player_id: str, genre: str):
        self._session_id      = session_id
        self._player_id       = player_id
        self._genre           = genre
        self._running         = False

        # Populated during run()
        self._ws_process: Optional[subprocess.Popen] = None
        self._ws_id: Optional[str] = None
        self._capture_session_id: Optional[str] = None
        self._client = None          # CaptureClient
        self._video_id: Optional[str] = None
        self._rtstream_ids: list[str] = []

        # Set once capture_session.active event is seen
        self._active_event = asyncio.Event()

        logger.info(
            "CaptureAgent created — session=%s genre=%s player=%s",
            session_id, genre, player_id,
        )

    @property
    def video_id(self) -> Optional[str]:
        return self._video_id

    @property
    def rtstream_ids(self) -> list[str]:
        return self._rtstream_ids

    async def wait_for_active(self, timeout: float = 90.0) -> None:
        """Block until capture_session.active event arrives."""
        logger.info("Waiting for capture to go active (timeout=%.0fs)…", timeout)
        try:
            await asyncio.wait_for(self._active_event.wait(), timeout=timeout)
            logger.info("Capture active — rtstreams=%s", self._rtstream_ids)
        except asyncio.TimeoutError:
            logger.error("Capture did not become active within %.0fs", timeout)
            raise

    async def run(self) -> None:
        self._running = True
        logger.info("CaptureAgent starting")
        try:
            await self._start_ws_listener()
            await self._wait_for_ws_id()
            await self._start_capture_session()
            await self._monitor_events()   # blocks until stop()
            await self._stop_capture()
            await self._wait_for_export()
        except Exception as exc:
            logger.error("CaptureAgent fatal error: %s", exc, exc_info=True)
            raise
        finally:
            await self._kill_ws_listener()
            logger.info("CaptureAgent finished — video_id=%s", self._video_id)

    async def stop(self) -> None:
        if not self._running:
            return
        logger.info("CaptureAgent.stop() called")
        self._running = False

    # ── Step 1: Launch ws_listener (official skill script) ────────────────────

    async def _start_ws_listener(self) -> None:
        """Launch the official skill ws_listener.py in background."""
        # Clear old files
        for f in [WS_ID_FILE, WS_PID_FILE, EVENTS_PATH]:
            if f.exists():
                f.unlink()
        EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)

        ws_listener = ROOT_DIR / "agents" / "ws_listener.py"
        cmd = [
            sys.executable, str(ws_listener),
            "--clear",
            f"--cwd={ROOT_DIR}",
        ]
        self._ws_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        logger.info("ws_listener launched — pid=%d", self._ws_process.pid)
        # Give it a moment to connect before reading the ws_id
        await asyncio.sleep(3.0)

    # ── Step 2: Read WebSocket ID ─────────────────────────────────────────────

    async def _wait_for_ws_id(self, timeout: float = 30.0) -> None:
        """Poll /tmp/videodb_ws_id until it appears."""
        deadline = time.monotonic() + timeout
        logger.info("Waiting for WebSocket ID…")
        while time.monotonic() < deadline:
            if WS_ID_FILE.exists():
                self._ws_id = WS_ID_FILE.read_text().strip()
                logger.info("WebSocket ID obtained — ws_id=%s", self._ws_id)
                return
            await asyncio.sleep(1.0)
        raise TimeoutError(f"WebSocket ID not written within {timeout}s")

    # ── Step 3–5: CaptureSession + CaptureClient ──────────────────────────────

    async def _start_capture_session(self) -> None:
        """Create server-side CaptureSession and start the local CaptureClient."""
        logger.info("Creating CaptureSession — ws_id=%s", self._ws_id)
        try:
            import videodb
            from videodb.capture import CaptureClient

            conn = videodb.connect(api_key=VIDEO_DB_API_KEY)

            # Create server-side session
            cap_session = conn.create_capture_session(
                end_user_id=self._player_id,
                collection_id="default",
                ws_connection_id=self._ws_id,
                metadata={"genre": self._genre, "gamesense_session_id": self._session_id},
            )
            self._capture_session_id = cap_session.id
            logger.info("CaptureSession created — cap_session_id=%s", self._capture_session_id)

            # Generate token for local client
            token = conn.generate_client_token()

            # Init local CaptureClient
            self._client = CaptureClient(client_token=token)

            # Request permissions
            logger.info("Requesting screen capture permissions…")
            await self._client.request_permission("microphone")
            await self._client.request_permission("screen_capture")

            # Discover channels
            channels = await self._client.list_channels()
            logger.debug("Available channels:")
            for ch in channels.all():
                logger.debug("  %s (%s): %s", ch.id, ch.type, ch.name)

            # Enable storage on display (so we get a video_id after export)
            display = channels.displays.default
            mic     = channels.mics.default
            sys_aud = channels.system_audio.default

            selected = []
            if display:
                display.store = True   # persist to get exported_video_id
                display.is_primary = True
                selected.append(display)
                logger.info("Display channel selected — %s", display.name)
            if mic:
                selected.append(mic)
            if sys_aud:
                selected.append(sys_aud)

            # Start streaming
            await self._client.start_session(
                capture_session_id=self._capture_session_id,
                channels=selected,
            )
            logger.info("Capture streaming started — waiting for active event…")

        except Exception as exc:
            logger.error("Failed to start CaptureSession: %s", exc, exc_info=True)
            raise

    # ── Step 6: Monitor events until stop() ───────────────────────────────────

    async def _monitor_events(self) -> None:
        """
        Read JSONL events while session is active.
        Sets _active_event when capture_session.active is seen.
        Exits when self._running is False.
        """
        offset = 0
        logger.info("Monitoring events at %s", EVENTS_PATH)

        while self._running:
            events = self._read_new_events(offset)
            for event in events:
                ev_type = event.get("event", "")
                if ev_type == "capture_session.active":
                    rtstreams = event.get("data", {}).get("rtstreams", [])
                    self._rtstream_ids = [r["rtstream_id"] for r in rtstreams]
                    self._write_capture_info(rtstreams)
                    self._active_event.set()
                    logger.info(
                        "capture_session.active received — rtstreams=%s",
                        self._rtstream_ids,
                    )
            # Track offset
            if EVENTS_PATH.exists():
                offset = EVENTS_PATH.stat().st_size

            await asyncio.sleep(2.0)

    def _read_new_events(self, from_offset: int) -> list[dict]:
        if not EVENTS_PATH.exists():
            return []
        try:
            with open(EVENTS_PATH, "r") as f:
                f.seek(from_offset)
                lines = f.readlines()
            events = []
            for line in lines:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return events
        except OSError:
            return []

    def _write_capture_info(self, rtstreams: list[dict]) -> None:
        """Write capture metadata so IndexingAgent can pick it up."""
        info = {
            "session_id":        self._session_id,
            "capture_session_id": self._capture_session_id,
            "ws_id":             self._ws_id,
            "rtstream_ids":      [r["rtstream_id"] for r in rtstreams],
            "rtstreams":         rtstreams,
            "genre":             self._genre,
            "player_id":         self._player_id,
        }
        CAPTURE_INFO_PATH.write_text(json.dumps(info, indent=2))
        logger.debug("Capture info written to %s", CAPTURE_INFO_PATH)

    # ── Step 7: Stop capture ──────────────────────────────────────────────────

    async def _stop_capture(self) -> None:
        if not self._client:
            return
        logger.info("Stopping CaptureClient…")
        try:
            await self._client.stop_session()
            await self._client.shutdown()
            logger.info("CaptureClient stopped and shut down")
        except Exception as exc:
            logger.error("Error stopping CaptureClient: %s", exc)

    # ── Step 8: Wait for export ───────────────────────────────────────────────

    async def _wait_for_export(self, timeout: float = 120.0) -> None:
        """
        Poll events for capture_session.exported.
        This event contains the exported_video_id — do NOT kill ws_listener before this.
        """
        logger.info("Waiting for capture_session.exported event (timeout=%.0fs)…", timeout)
        deadline = time.monotonic() + timeout
        offset   = 0

        while time.monotonic() < deadline:
            events = self._read_new_events(offset)
            for event in events:
                if event.get("event") == "capture_session.exported":
                    data = event.get("data", {})
                    self._video_id = data.get("exported_video_id")
                    logger.info(
                        "capture_session.exported — video_id=%s stream_url=%s",
                        self._video_id, data.get("stream_url", "N/A"),
                    )
                    # Update capture info with final video_id
                    if CAPTURE_INFO_PATH.exists():
                        try:
                            info = json.loads(CAPTURE_INFO_PATH.read_text())
                            info["video_id"] = self._video_id
                            info["status"]   = "exported"
                            CAPTURE_INFO_PATH.write_text(json.dumps(info, indent=2))
                        except Exception:
                            pass
                    return

            if EVENTS_PATH.exists():
                offset = EVENTS_PATH.stat().st_size
            await asyncio.sleep(3.0)

        logger.warning("capture_session.exported not received within %.0fs", timeout)

    # ── Kill ws_listener after export (never before!) ─────────────────────────

    async def _kill_ws_listener(self) -> None:
        """Kill the ws_listener process using its PID file."""
        if WS_PID_FILE.exists():
            try:
                pid = int(WS_PID_FILE.read_text().strip())
                os.kill(pid, 15)  # SIGTERM
                logger.info("ws_listener killed — pid=%d", pid)
            except Exception as exc:
                logger.warning("Could not kill ws_listener: %s", exc)
        elif self._ws_process and self._ws_process.poll() is None:
            self._ws_process.terminate()
            logger.info("ws_listener terminated via Popen")
