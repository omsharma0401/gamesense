"""
agents/indexing_agent.py — Real-time visual and audio indexing agent.

Reads RTStream IDs from /tmp/videodb_capture_info.json (written by CaptureAgent
after capture_session.active event) and attaches two AI pipelines:

  1. Visual: index_visuals() — describes what's on screen every 2s (5 frames)
     → events arrive on 'scene_index' WebSocket channel
  2. Audio:  index_audio()   — summarises mic/system audio every 30 words
     → events arrive on 'audio_index' WebSocket channel

Both pipelines pass ws_connection_id so results appear in videodb_events.jsonl.

IMPORTANT from skill docs:
  - model_name is a tier string: "basic", "pro", "ultra" (NOT SandboxModel enum)
  - index_audio / index_visuals return RTStreamSceneIndex objects
  - Always pass ws_connection_id so results are captured in JSONL
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from agents.interfaces import BaseAgent
from config import (
    VIDEO_DB_API_KEY,
    CAPTURE_INFO_PATH,
    VISUAL_INDEX_PROMPT,
    AUDIO_INDEX_PROMPT,
    VISUAL_INDEX_MODEL,
    AUDIO_INDEX_MODEL,
    VISUAL_INDEX_BATCH_SECONDS,
    VISUAL_INDEX_FRAME_COUNT,
    AUDIO_INDEX_BATCH_SECONDS,
)

logger = logging.getLogger(__name__)

WS_ID_FILE = __import__('pathlib').Path("/tmp/videodb_ws_id")


class IndexingAgent(BaseAgent):
    """
    Attaches visual + audio indexing pipelines to each RTStream from the capture.

    Reads capture info (rtstream_ids, ws_id) from /tmp/videodb_capture_info.json.
    Sends ws_connection_id so all results flow into the events JSONL file.
    """

    def __init__(self):
        self._running = False
        self._visual_indexes: list = []  # RTStreamSceneIndex objects
        self._audio_indexes:  list = []
        logger.info("IndexingAgent created")

    async def run(self) -> None:
        self._running = True
        logger.info("IndexingAgent starting")

        try:
            capture_info = await self._wait_for_capture_info()
            ws_id        = self._read_ws_id()

            rtstream_ids: list[str] = capture_info.get("rtstream_ids", [])
            rtstreams_meta: list[dict] = capture_info.get("rtstreams", [])

            if not rtstream_ids:
                logger.warning("No RTStream IDs in capture info — IndexingAgent idle")
                while self._running:
                    await asyncio.sleep(5.0)
                return

            logger.info(
                "Starting AI pipelines on %d RTStream(s) — ws_id=%s",
                len(rtstream_ids), ws_id,
            )

            # Attach pipelines to each stream (visual on display, audio on mic/sys)
            await self._attach_pipelines(rtstreams_meta, ws_id)

            logger.info("IndexingAgent active — pipelines running, waiting for stop()")
            while self._running:
                await asyncio.sleep(5.0)

        except Exception as exc:
            logger.error("IndexingAgent fatal: %s", exc, exc_info=True)
            raise

    async def stop(self) -> None:
        if not self._running:
            return
        logger.info("IndexingAgent stopping")
        self._running = False
        # Optionally stop the indexes gracefully
        for idx in self._visual_indexes + self._audio_indexes:
            try:
                idx.stop()
                logger.debug("RTStreamSceneIndex stopped — id=%s", getattr(idx, "rtstream_index_id", "?"))
            except Exception as exc:
                logger.warning("Could not stop index: %s", exc)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _wait_for_capture_info(self, timeout: float = 120.0) -> dict:
        """Poll CAPTURE_INFO_PATH until it has rtstream_ids."""
        logger.info("Waiting for capture info (timeout=%.0fs)…", timeout)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if CAPTURE_INFO_PATH.exists():
                try:
                    info = json.loads(CAPTURE_INFO_PATH.read_text())
                    if info.get("rtstream_ids"):
                        logger.info(
                            "Capture info ready — %d RTStream(s) found",
                            len(info["rtstream_ids"]),
                        )
                        return info
                except (json.JSONDecodeError, OSError):
                    pass
            await asyncio.sleep(2.0)
        raise TimeoutError(f"Capture info not available within {timeout}s")

    def _read_ws_id(self) -> Optional[str]:
        """Read the WebSocket connection ID from /tmp/videodb_ws_id."""
        if WS_ID_FILE.exists():
            ws_id = WS_ID_FILE.read_text().strip()
            logger.debug("ws_id read — %s", ws_id)
            return ws_id
        logger.warning("ws_id file not found — results may not arrive in JSONL")
        return None

    async def _attach_pipelines(self, rtstreams_meta: list[dict], ws_id: Optional[str]) -> None:
        """Attach visual pipeline to display streams, audio to audio streams."""
        tasks = []
        for rts in rtstreams_meta:
            rtstream_id  = rts["rtstream_id"]
            media_types  = rts.get("media_types", [])
            name         = rts.get("name", "")

            if "video" in media_types:
                tasks.append(self._start_visual(rtstream_id, ws_id, name))
            if "audio" in media_types:
                tasks.append(self._start_audio(rtstream_id, ws_id, name))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error("Pipeline attach failed for stream %d: %s", i, r)

    async def _start_visual(self, rtstream_id: str, ws_id: Optional[str], stream_name: str) -> None:
        """Start visual indexing on a display RTStream."""
        logger.info(
            "Starting visual index — rtstream=%s name=%s model=%s batch=%ds frames=%d",
            rtstream_id, stream_name, VISUAL_INDEX_MODEL, VISUAL_INDEX_BATCH_SECONDS, VISUAL_INDEX_FRAME_COUNT,
        )
        try:
            import videodb
            conn  = videodb.connect(api_key=VIDEO_DB_API_KEY)
            coll  = conn.get_collection()
            rtstream = coll.get_rtstream(rtstream_id)

            kwargs = dict(
                prompt=VISUAL_INDEX_PROMPT,
                batch_config={
                    "type":        "time",
                    "value":       VISUAL_INDEX_BATCH_SECONDS,
                    "frame_count": VISUAL_INDEX_FRAME_COUNT,
                },
                model_name=VISUAL_INDEX_MODEL,
                name=f"gamesense_visual_{stream_name}",
            )
            if ws_id:
                kwargs["ws_connection_id"] = ws_id

            # Run in executor — SDK call is synchronous
            idx = await asyncio.get_event_loop().run_in_executor(
                None, lambda: rtstream.index_visuals(**kwargs)
            )
            self._visual_indexes.append(idx)
            logger.info(
                "Visual index started — rtstream=%s index_id=%s",
                rtstream_id, getattr(idx, "rtstream_index_id", "?"),
            )
        except Exception as exc:
            logger.error("Visual indexing failed for rtstream=%s: %s", rtstream_id, exc, exc_info=True)
            raise

    async def _start_audio(self, rtstream_id: str, ws_id: Optional[str], stream_name: str) -> None:
        """Start audio indexing on a mic/system_audio RTStream."""
        logger.info(
            "Starting audio index — rtstream=%s name=%s batch=%dwords",
            rtstream_id, stream_name, AUDIO_INDEX_BATCH_SECONDS,
        )
        try:
            import videodb
            conn  = videodb.connect(api_key=VIDEO_DB_API_KEY)
            coll  = conn.get_collection()
            rtstream = coll.get_rtstream(rtstream_id)

            kwargs = dict(
                prompt=AUDIO_INDEX_PROMPT,
                batch_config={"type": "word", "value": AUDIO_INDEX_BATCH_SECONDS},
                name=f"gamesense_audio_{stream_name}",
            )
            if AUDIO_INDEX_MODEL:
                kwargs["model_name"] = AUDIO_INDEX_MODEL
            if ws_id:
                kwargs["ws_connection_id"] = ws_id

            idx = await asyncio.get_event_loop().run_in_executor(
                None, lambda: rtstream.index_audio(**kwargs)
            )
            self._audio_indexes.append(idx)
            logger.info(
                "Audio index started — rtstream=%s index_id=%s",
                rtstream_id, getattr(idx, "rtstream_index_id", "?"),
            )
        except Exception as exc:
            logger.error("Audio indexing failed for rtstream=%s: %s", rtstream_id, exc, exc_info=True)
            raise
