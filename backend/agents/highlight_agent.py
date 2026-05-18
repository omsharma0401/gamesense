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
    """Mix positive + 1-2 negative moments for emotional arc, sorted chronologically."""
    positive = [c for c in clips if c.type in ("clutch", "kill", "highlight")]
    negative = [c for c in clips if c.type in ("blunder", "death", "error")]
    n_neg = min(2, len(negative))
    n_pos = min(max_clips - n_neg, len(positive))
    selected = positive[:n_pos] + negative[:n_neg]
    selected.sort(key=lambda c: c.start_time)
    logger.info("Clip selection — pos=%d neg=%d total=%d", n_pos, n_neg, len(selected))
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
            clip_audio_ids: list[Optional[str]] = (
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
            vertical_url = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._vertical_sync(clips)
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

            reframed: list[tuple[str, float]] = []
            for c in clips:
                try:
                    rv = video.reframe(
                        start=max(0.0, c.start_time),
                        end=c.end_time,
                        target="vertical",
                        mode=ReframeMode.smart,
                    )
                    if rv:
                        # rv.length defaults to 0.0 when not returned; fall back to clip duration
                        dur = float(rv.length) if rv.length else max(1.0, c.end_time - c.start_time)
                        reframed.append((rv.id, dur))
                        logger.debug("Reframed clip — id=%s dur=%.1fs", rv.id, dur)
                except Exception as exc:
                    logger.warning("Reframe failed for clip=%s: %s", c.id, exc)

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

    async def _generate_clip_voices(self, clips: list[Clip]) -> list[Optional[str]]:
        """Generate per-clip commentary voices in parallel. Returns list of audio IDs."""
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

    def _voice_sync(self, clip: Clip) -> Optional[str]:
        """Generate voiced commentary for one clip. Returns audio ID or None."""
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
                logger.debug("Clip voice ready — audio_id=%s clip_type=%s", audio.id, clip.type)
                return audio.id
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
        self, clip_data: list[tuple], clip_audio_ids: list[Optional[str]]
    ) -> Optional[str]:
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._timeline_sync(clip_data, clip_audio_ids)
        )

    def _timeline_sync(
        self, clip_data: list[tuple], clip_audio_ids: list[Optional[str]]
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
            for clip_cursor, audio_id in zip(clip_cursors, clip_audio_ids):
                if audio_id:
                    audio_track.add_clip(
                        clip_cursor,
                        VClip(asset=AudioAsset(id=audio_id, volume=1.0), duration=5),
                    )
                    logger.debug("Audio track clip — t=%ds audio_id=%s", clip_cursor, audio_id)

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
