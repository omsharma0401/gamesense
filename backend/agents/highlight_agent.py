"""
agents/highlight_agent.py — Highlight reel generation agent.

Picks top MAX_HIGHLIGHT_CLIPS moments (mixing positive + negative for arc),
generates per-clip ElevenLabs commentary overlays via VideoDB, and assembles
a Timeline with clips + audio overlays at each clip's exact timestamp.
Returns a stream_url the frontend embeds directly.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from agents.interfaces import BaseAgent
from memory.interfaces import BaseSessionStore
from schemas.session import Session, AnalysisResult, HighlightReel, Clip
from config import (
    VIDEO_DB_API_KEY,
    MAX_HIGHLIGHT_CLIPS,
)

try:
    from videodb import ReframeMode  # type: ignore
    _REFRAME_AVAILABLE = True
except ImportError:
    _REFRAME_AVAILABLE = False

logger = logging.getLogger(__name__)


def _select_highlight_clips(clips: list[Clip], max_clips: int) -> list[Clip]:
    """Use all clips sorted chronologically — highlight reel = full session story."""
    selected = sorted(clips, key=lambda c: c.start_time)
    if len(selected) > max_clips:
        selected = selected[:max_clips]
    logger.info("Clip selection — total=%d", len(selected))
    return selected


_COMMENTATOR_INSTRUCTIONS = (
    "Live esports play-by-play commentator. Punchy, short, high-energy. "
    "React to EXACTLY what happened — one or two sentences max. "
    "Stadium broadcast tone — excited but professional."
)


class HighlightAgent(BaseAgent):
    """Compiles a highlight reel from top clips with OmniVoice narration."""

    def __init__(self, session: Session, analysis: AnalysisResult, store: BaseSessionStore):
        self._session  = session
        self._analysis = analysis
        self._store    = store
        logger.info("HighlightAgent created — session=%s", session.id)

    async def run(self) -> Optional[HighlightReel]:
        logger.info("HighlightAgent starting — session=%s", self._session.id)
        reel = HighlightReel(session_id=self._session.id, status="generating")
        await self._store.save_highlight_reel(reel)

        try:
            clips = _select_highlight_clips(self._analysis.clips, MAX_HIGHLIGHT_CLIPS)
            if not clips:
                logger.warning("No clips — skipping highlight reel")
                reel.status = "failed"
                await self._store.save_highlight_reel(reel)
                return reel

            # Generate per-clip commentary voices + timeline clip data in parallel
            voices_result, clip_data = await asyncio.gather(
                self._generate_clip_voices(clips),
                self._prepare_timeline_clips(clips),
                return_exceptions=True,
            )
            clip_audio_ids: list[Optional[tuple[str, float]]] = (
                [] if isinstance(voices_result, Exception) else voices_result
            )
            if isinstance(voices_result, Exception):
                logger.warning("Voice generation failed: %s — proceeding without audio", voices_result)
            if isinstance(clip_data, Exception):
                logger.error("Clip prep failed: %s", clip_data)
                reel.status = "failed"
                await self._store.save_highlight_reel(reel)
                return reel

            stream_url = await self._assemble_timeline(clip_data, clip_audio_ids)
            if stream_url:
                reel.stream_url = stream_url
                reel.status     = "complete"
                reel.duration   = sum(c.duration for c in clips)
                # Use the first clip's thumbnail as the reel card thumbnail
                reel.thumbnail_url = next((c.thumbnail_url for c in clips if c.thumbnail_url), None)
                logger.info("Highlight reel complete — url=%s duration=%.1fs", stream_url, reel.duration)

                # Generate vertical (9:16) version in background — non-blocking
                if _REFRAME_AVAILABLE and self._session.video_id:
                    asyncio.create_task(self._generate_vertical(reel, clips))
            else:
                reel.status = "failed"
                logger.warning("Timeline returned no stream URL")

            await self._store.save_highlight_reel(reel)
            return reel

        except Exception as exc:
            logger.error("HighlightAgent failed: %s", exc, exc_info=True)
            reel.status = "failed"
            await self._store.save_highlight_reel(reel)
            raise

    async def stop(self) -> None:
        pass  # runs once

    async def _generate_vertical(self, reel: HighlightReel, clips: list[Clip]) -> None:
        """Generate 9:16 vertical version of the highlight reel using video.reframe()."""
        logger.info("Generating vertical highlight — session=%s", self._session.id)
        try:
            import concurrent.futures
            _daemon_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="vertical")
            vertical_url = await asyncio.get_event_loop().run_in_executor(
                _daemon_pool, lambda: self._vertical_sync(clips)
            )
            if vertical_url:
                reel.vertical_stream_url = vertical_url
                await self._store.save_highlight_reel(reel)
                logger.info("Vertical highlight ready — url=%s", vertical_url)
        except Exception as exc:
            logger.warning("Vertical highlight failed: %s", exc)

    def _vertical_sync(self, clips: list[Clip]) -> Optional[str]:
        """Reframe each clip to 9:16 and assemble vertical timeline. Synchronous."""
        try:
            import videodb
            from videodb import ReframeMode
            from videodb.editor import Timeline, Track, Clip as VClip, VideoAsset

            conn  = videodb.connect(api_key=VIDEO_DB_API_KEY)
            coll  = conn.get_collection()
            video = coll.get_video(self._session.video_id)

            import time as _time
            reframed: list[tuple[str, float]] = []
            for c in clips:
                rv = None
                for attempt in range(1, 4):  # up to 3 attempts with back-off
                    try:
                        rv = video.reframe(
                            start=max(0.0, c.start_time),
                            end=c.end_time,
                            target="vertical",
                            mode=ReframeMode.smart,
                        )
                        break  # success
                    except Exception as exc:
                        wait = attempt * 20  # 20s, 40s, 60s
                        logger.info(
                            "Reframe attempt %d/%d failed (clip=%s): %s — retrying in %ds",
                            attempt, 3, c.id, exc, wait,
                        )
                        _time.sleep(wait)
                if rv:
                    dur = float(rv.length) if getattr(rv, "length", None) else max(1.0, c.end_time - c.start_time)
                    reframed.append((rv.id, dur))
                    logger.debug("Reframed clip — id=%s dur=%.1fs", rv.id, dur)
                else:
                    logger.warning("Skipping clip=%s after 3 reframe attempts", c.id)

            if not reframed:
                return None

            # Single clip: stream directly without Timeline overhead
            if len(reframed) == 1:
                vid_id, _ = reframed[0]
                rv_video = coll.get_video(vid_id)
                return rv_video.generate_stream()

            # Multiple clips: assemble into a vertical timeline
            timeline = Timeline(conn)
            timeline.resolution = "608x1080"
            timeline.background = "#000000"

            track = Track()
            cursor = 0
            for vid_id, dur in reframed:
                track.add_clip(cursor, VClip(asset=VideoAsset(id=vid_id), duration=dur))
                cursor += int(dur) + 1

            timeline.add_track(track)
            url = timeline.generate_stream()
            logger.info("Vertical timeline stream: %s", url)
            return url
        except Exception as exc:
            logger.error("Vertical highlight assembly failed: %s", exc, exc_info=True)
            return None

    async def _generate_clip_voices(self, clips: list[Clip]) -> list[Optional[tuple[str, float]]]:
        """Generate per-clip commentary voices in parallel. Returns list of (audio_id, duration) tuples."""
        logger.info("Generating commentary voices — %d clips", len(clips))
        tasks = [
            asyncio.get_event_loop().run_in_executor(None, lambda c=clip: self._voice_sync(c))
            for clip in clips
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        audio_ids = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning("Voice failed for clip %d: %s", i, r)
                audio_ids.append(None)
            else:
                audio_ids.append(r)
        logger.info("Commentary voices ready — %d/%d succeeded", sum(1 for a in audio_ids if a), len(clips))
        return audio_ids

    def _voice_sync(self, clip: Clip) -> Optional[tuple[str, float]]:
        """Generate voiced commentary for one clip. Returns (audio_id, duration_seconds) or None."""
        try:
            import videodb
            conn  = videodb.connect(api_key=VIDEO_DB_API_KEY)
            coll  = conn.get_collection()
            audio = coll.generate_voice(
                text=clip.commentary,
                config={"instructions": _COMMENTATOR_INSTRUCTIONS},
                wait=True,
            )
            if audio:
                dur = float(getattr(audio, "length", None) or getattr(audio, "duration", None) or 5.0)
                logger.debug("Clip voice ready — audio_id=%s dur=%.1fs clip_type=%s", audio.id, dur, clip.type)
                return (audio.id, dur)
            return None
        except Exception as exc:
            logger.warning("Voice generation failed for clip %s: %s", clip.id, exc)
            return None

    async def _prepare_timeline_clips(self, clips: list[Clip]) -> list[tuple]:
        # Returns (start_seconds, duration_seconds, video_id) — all from the same exported video
        video_id = self._session.video_id
        result = []
        for c in clips:
            start = max(0.0, c.start_time)
            dur   = max(c.end_time - start, 1.0)
            result.append((start, dur, video_id))
        return result

    async def _assemble_timeline(
        self, clip_data: list[tuple], clip_audio_ids: list[Optional[tuple[str, float]]]
    ) -> Optional[str]:
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._timeline_sync(clip_data, clip_audio_ids)
        )

    def _timeline_sync(
        self, clip_data: list[tuple], clip_audio_ids: list[Optional[tuple[str, float]]]
    ) -> Optional[str]:
        try:
            import videodb
            from videodb.editor import Timeline, Track, Clip as VClip, VideoAsset, AudioAsset

            conn     = videodb.connect(api_key=VIDEO_DB_API_KEY)
            timeline = Timeline(conn)
            timeline.resolution = "1280x720"
            timeline.background = "#000000"

            # Build video track, tracking each clip's start position in the timeline
            video_track = Track()
            clip_cursors: list[int] = []
            cursor = 0
            for start, dur, video_id in clip_data:
                if not video_id:
                    continue
                clip_cursors.append(cursor)
                video_track.add_clip(
                    cursor,
                    VClip(asset=VideoAsset(id=video_id, start=int(start)), duration=dur),
                )
                cursor += int(dur) + 1

            timeline.add_track(video_track)

            audio_track = Track()
            for clip_cursor, audio_entry in zip(clip_cursors, clip_audio_ids):
                if audio_entry:
                    audio_id, audio_dur = audio_entry
                    audio_track.add_clip(
                        clip_cursor,
                        VClip(asset=AudioAsset(id=audio_id, volume=1.0), duration=audio_dur),
                    )
                    logger.debug("Audio track clip — t=%ds audio_id=%s dur=%.1fs", clip_cursor, audio_id, audio_dur)

            voiced = sum(1 for a in clip_audio_ids if a)
            if voiced:
                timeline.add_track(audio_track)
            logger.info("Timeline: %d clips, %d commentary tracks", len(clip_cursors), voiced)

            url = timeline.generate_stream()
            logger.info("Timeline stream generated — url=%s", url)
            return url
        except Exception as exc:
            logger.error("Timeline assembly failed: %s", exc, exc_info=True)
            return None
