"""
agents/analysis_agent.py — Post-session analysis agent.

Runs once after the session ends. Responsibilities:
  1. Read all detected moments from SQLite
  2. Score the session via LLM (overall + sub-scores + patterns + summary)
  3. For each moment: search the VideoAsset and compile a clip
     - Handles InvalidRequestError: No results found → skip silently
     - Clamps timestamps: max(0, ts/1000 - 5) to avoid broken streams
     - Compiles all clips in parallel (asyncio.gather with return_exceptions)
  4. Caps at MAX_MOMENTS_FOR_ANALYSIS to avoid oversized LLM prompts
  5. Returns a complete AnalysisResult
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional

from agents.interfaces import BaseAgent
from llm.interfaces import BaseLLMProvider
from memory.interfaces import BaseSessionStore
from schemas.session import (
    Session, Moment, Score, Clip, AnalysisResult,
)
from schemas.agent import AnalysisOutput
from config import (
    VIDEO_DB_API_KEY,
    VIDEODB_SANDBOX_ID,
    MAX_MOMENTS_FOR_ANALYSIS,
    VISUAL_INDEX_PROMPT,
)

logger = logging.getLogger(__name__)


_ANALYSIS_SYSTEM_PROMPT = """You are an expert FPS/competitive gaming coach.
You have been given the key moments detected during a player's gaming session.
Analyse their overall performance and provide:
  - Scores (0-100) for mechanics, decision_making, consistency, and an overall score
  - A list of specific recurring patterns (not vague — cite concrete behaviours)
  - A summary paragraph written in second-person coaching voice

Be honest and specific. Do not inflate scores. A good session is 70+.
Return valid JSON matching the schema exactly."""


def _build_analysis_prompt(session: Session, moments: list[Moment]) -> str:
    moment_lines = "\n".join(
        f"  [{i+1}] [{m.type.upper()}] sig={m.significance}/10 ts={m.timestamp_ms}ms: {m.description}"
        for i, m in enumerate(moments)
    )
    return f"""Session to analyse:
Game: {session.game}
Player: {session.player_id}
Duration: {_format_duration(session)}
Total moments detected: {len(moments)}

Key moments (sorted by significance, top {len(moments)} shown):
{moment_lines}

Score this session and provide your coaching analysis."""


def _format_duration(session: Session) -> str:
    if session.ended_at and session.started_at:
        secs = int((session.ended_at - session.started_at).total_seconds())
        return f"{secs // 60}m {secs % 60}s"
    return "unknown"


class AnalysisAgent(BaseAgent):
    """
    Post-session analysis: scoring + clip compilation.

    Injects:
        llm:   LLM provider for scoring
        store: Session store to read moments and save analysis
    """

    def __init__(
        self,
        session: Session,
        llm: BaseLLMProvider,
        store: BaseSessionStore,
    ):
        self._session = session
        self._llm     = llm
        self._store   = store
        self._running = False
        logger.info("AnalysisAgent created — session=%s", session.id)

    async def run(self) -> AnalysisResult:
        """Run the full analysis pipeline. Returns AnalysisResult."""
        self._running = True
        logger.info("AnalysisAgent starting — session=%s", self._session.id)

        try:
            # 1. Fetch moments from SQLite
            all_moments = await self._store.get_moments(self._session.id)
            logger.info("Fetched %d moments for analysis", len(all_moments))

            # 2. Cap to top N by significance (avoid oversized prompts)
            moments = sorted(all_moments, key=lambda m: m.significance, reverse=True)
            moments = moments[:MAX_MOMENTS_FOR_ANALYSIS]
            logger.info("Using top %d moments for LLM analysis", len(moments))

            # 3. Score via LLM
            score, patterns, summary = await self._score_session(moments)

            # 4. Index the exported video for scene search (uses sandbox)
            scene_index_id = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._ensure_video_indexed(self._session.video_id)
            ) if self._session.video_id else None

            # 5. Compile clips in parallel
            clips = await self._compile_clips(moments, scene_index_id)
            logger.info("Compiled %d/%d clips successfully", len(clips), len(moments))

            # 6. Build and return the result — MemoryAgent handles persistence
            result = AnalysisResult(
                session_id=self._session.id,
                score=score,
                moments=all_moments,
                clips=clips,
                patterns=patterns,
                summary=summary,
                status="complete",
            )
            logger.info(
                "Analysis complete — session=%s score=%d clips=%d patterns=%d",
                self._session.id, score.overall, len(clips), len(patterns),
            )
            return result

        except Exception as exc:
            logger.error("AnalysisAgent failed: %s", exc, exc_info=True)
            # Save a failed result so the frontend doesn't hang
            result = AnalysisResult(
                session_id=self._session.id,
                score=Score(overall=0, mechanics=0, decision_making=0, consistency=0),
                summary="Analysis failed — see backend logs.",
                status="failed",
            )
            await self._store.save_analysis(result)
            raise
        finally:
            self._running = False

    async def stop(self) -> None:
        """No-op — analysis runs once and terminates naturally."""
        self._running = False

    # ── Internal — LLM scoring ────────────────────────────────────────────────

    async def _score_session(
        self, moments: list[Moment]
    ) -> tuple[Score, list[str], str]:
        """Ask the LLM to score the session. Returns (Score, patterns, summary)."""
        logger.info("Requesting LLM session analysis — model=%s", self._llm.model_name)

        raw = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._llm.complete_structured(
                system=_ANALYSIS_SYSTEM_PROMPT,
                user=_build_analysis_prompt(self._session, moments),
                schema_name="analysis_output",
            ),
        )

        try:
            output = AnalysisOutput.model_validate_json(raw)
        except Exception as exc:
            logger.error("Failed to parse AnalysisOutput: %s | raw=%s", exc, raw[:300])
            raise

        score = Score(
            overall=output.score.overall,
            mechanics=output.score.mechanics,
            decision_making=output.score.decision_making,
            consistency=output.score.consistency,
        )
        logger.info(
            "LLM scores — overall=%d mechanics=%d decisions=%d consistency=%d",
            score.overall, score.mechanics, score.decision_making, score.consistency,
        )
        return score, output.patterns, output.summary

    # ── Internal — clip compilation ───────────────────────────────────────────

    async def _compile_clips(self, moments: list[Moment], scene_index_id: Optional[str]) -> list[Clip]:
        """Compile a clip for each moment in parallel. Skips failures silently."""
        if not moments:
            return []

        video_id = self._session.video_id
        if not video_id:
            logger.warning("Session has no video_id — skipping clip compilation")
            return []

        tasks = [
            self._compile_single_clip(moment, video_id, scene_index_id)
            for moment in moments
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        clips = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "Clip compilation failed for moment %d (%s): %s",
                    i, moments[i].type, result,
                )
            elif result is not None:
                clips.append(result)

        return clips

    async def _compile_single_clip(
        self, moment: Moment, video_id: str, scene_index_id: Optional[str]
    ) -> Optional[Clip]:
        """
        Search the video for a moment and compile a clip.
        Returns None if no matching segment is found (handles InvalidRequestError).
        """
        # Clamp start time — negative timestamps silently produce broken streams
        start_time = max(0.0, moment.timestamp_ms / 1000.0 - 5.0)
        end_time   = max(start_time + 5.0, moment.timestamp_ms / 1000.0 + 10.0)

        logger.debug(
            "Compiling clip — moment=%s type=%s start=%.1fs end=%.1fs",
            moment.id, moment.type, start_time, end_time,
        )

        try:
            stream_url = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._search_and_compile(
                    video_id=video_id,
                    query=moment.description,
                    start_time=start_time,
                    end_time=end_time,
                    scene_index_id=scene_index_id,
                ),
            )

            if not stream_url:
                logger.debug("No stream URL returned for moment=%s — skipping", moment.id)
                return None

            clip = Clip(
                moment_id=moment.id,
                session_id=moment.session_id,
                stream_url=stream_url,
                start_time=start_time,
                end_time=end_time,
                commentary=moment.commentary or moment.description,
                type=moment.type,
            )
            logger.info(
                "Clip compiled — moment=%s type=%s duration=%.1fs",
                moment.id, moment.type, clip.duration,
            )
            return clip

        except Exception as exc:
            logger.warning(
                "Clip compilation skipped — moment=%s: %s", moment.id, exc
            )
            return None

    def _ensure_video_indexed(self, video_id: str) -> Optional[str]:
        """
        Index the exported video for scene search using the sandbox.
        Returns scene_index_id. If already indexed, extracts the existing ID from the error.
        Synchronous — intended to run in a thread executor.
        """
        import re
        try:
            import videodb
            from videodb import SceneExtractionType

            conn  = videodb.connect(api_key=VIDEO_DB_API_KEY)
            coll  = conn.get_collection()
            video = coll.get_video(video_id)

            kwargs = dict(
                extraction_type=SceneExtractionType.time_based,
                extraction_config={"time": 10, "select_frames": ["first"], "frame_count": 1},
                prompt=VISUAL_INDEX_PROMPT,
            )
            if VIDEODB_SANDBOX_ID:
                kwargs["sandbox_id"] = VIDEODB_SANDBOX_ID

            scene_index_id = video.index_scenes(**kwargs)
            logger.info("Video indexed — video=%s scene_index_id=%s", video_id, scene_index_id)
            return scene_index_id

        except Exception as e:
            match = re.search(r"id\s+([a-f0-9]+)", str(e))
            if match:
                scene_index_id = match.group(1)
                logger.info("Reusing existing scene index — id=%s", scene_index_id)
                return scene_index_id
            logger.warning("Could not index video %s: %s — clips may be missing", video_id, e)
            return None

    def _search_and_compile(
        self,
        video_id: str,
        query: str,
        start_time: float,
        end_time: float,
        scene_index_id: Optional[str],
    ) -> Optional[str]:
        """
        Synchronous VideoDB search + compile (runs in thread executor).
        Handles the 'No results found' error by returning None.
        Falls back to time-based stream if no scene index is available.
        """
        try:
            import videodb
            from videodb import IndexType, SearchType
            from videodb.exceptions import InvalidRequestError

            conn  = videodb.connect(api_key=VIDEO_DB_API_KEY)
            coll  = conn.get_collection()
            video = coll.get_video(video_id)

            if scene_index_id:
                try:
                    results = video.search(
                        query=query,
                        index_type=IndexType.scene,
                        search_type=SearchType.semantic,
                        scene_index_id=scene_index_id,
                        score_threshold=0.3,
                    )
                    shots = results.get_shots()
                except InvalidRequestError as exc:
                    if "No results found" in str(exc):
                        logger.debug("No scene results for query='%s'", query[:60])
                        shots = []
                    else:
                        raise

                if not shots:
                    logger.debug("No shots matched — falling back to time-based clip")

            # Generate clip using pre-calculated time window (works with or without search results)
            stream_url = video.generate_stream(timeline=[(start_time, end_time)])
            return stream_url

        except Exception as exc:
            raise RuntimeError(f"VideoDB compile failed: {exc}") from exc
