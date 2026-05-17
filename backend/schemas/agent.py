"""
schemas/agent.py — Agent input/output Pydantic models.

MomentDetection: what the LLM returns for each poll cycle (MomentAgent).
AnalysisOutput:  what the LLM returns for post-session scoring (AnalysisAgent).
BriefingOutput:  what the LLM returns for coaching brief generation (BriefingAgent).
SessionStartInput / SessionStopInput: API request bodies.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field
from schemas.session import GameGenre


# ── MomentAgent LLM output ────────────────────────────────────────────────────

class MomentDetection(BaseModel):
    """
    Structured output from the LLM when MomentAgent asks:
    'Is anything significant happening in these events?'
    """

    is_moment: bool = Field(..., description="True only if a genuinely significant game event occurred")
    type: Optional[Literal["kill", "death", "clutch", "error", "strategy_break", "highlight", "blunder", "none"]] = Field(
        None,
        description="Required when is_moment=True. The category of the event.",
    )
    description: str = Field(
        ...,
        description=(
            "Concrete description of what happened. "
            "If is_moment=False, explain why this is not significant (e.g. 'loading screen')."
        ),
    )
    significance: int = Field(
        ...,
        ge=0, le=10,
        description="0=no moment, 1=minor, 10=game-changing. Use 0 when is_moment=False.",
    )
    timestamp_ms: int = Field(
        ...,
        description="Approximate timestamp in milliseconds from session start.",
    )
    commentary: str = Field(
        ...,
        description=(
            "One-sentence AI commentary for this moment, written as if for a highlight reel. "
            "Example: 'You held the angle perfectly in a 1v3 — clean clutch.'"
        ),
    )


# ── AnalysisAgent LLM output ──────────────────────────────────────────────────

class ScoreBreakdown(BaseModel):
    """Score sub-components returned by the analysis LLM."""

    overall: int = Field(..., ge=0, le=100)
    mechanics: int = Field(..., ge=0, le=100, description="Aim, movement, execution")
    decision_making: int = Field(..., ge=0, le=100, description="Positioning, strategy, timing")
    consistency: int = Field(..., ge=0, le=100, description="Consistency across the session")


class AnalysisOutput(BaseModel):
    """
    Structured output from the LLM when AnalysisAgent analyses the full session.
    """

    score: ScoreBreakdown
    patterns: list[str] = Field(
        ...,
        description=(
            "Recurring behavioural patterns observed across the session. "
            "Be specific: 'You pushed the same corner 3 times and died each time' "
            "not 'You made some mistakes.'"
        ),
    )
    summary: str = Field(
        ...,
        description=(
            "One paragraph session summary written in second-person coaching voice. "
            "Lead with one genuine strength, then the most important thing to fix."
        ),
    )


# ── BriefingAgent LLM output ─────────────────────────────────────────────────

class BriefingOutput(BaseModel):
    """
    Structured output from the LLM when BriefingAgent generates the pre-session brief.
    """

    coaching_paragraph: str = Field(
        ...,
        description=(
            "Personalised coaching paragraph drawing on session history. "
            "Reference specific trends: 'Over your last 6 sessions, B site has improved...' "
            "End with a concrete actionable focus for today."
        ),
    )
    focus_areas: list[str] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="2–4 specific focus areas for the upcoming session.",
    )


# ── API request schemas ───────────────────────────────────────────────────────

class SessionStartInput(BaseModel):
    genre: GameGenre = Field(..., description="Game genre, e.g. 'tactical-shooter'")
    player_id: str = Field(..., description="Unique player identifier")


class SessionStopInput(BaseModel):
    session_id: str = Field(..., description="ID of the running session to stop")


class DiscordShareInput(BaseModel):
    session_id: str
    moment_id: str
    webhook_url: Optional[str] = Field(
        None,
        description="Override webhook URL. Falls back to DISCORD_WEBHOOK_URL env var.",
    )


# ── Live session status (returned by GET /session/active and GET /session/{id}) ──

class LiveSessionStatus(BaseModel):
    session_id: str
    genre: GameGenre
    player_id: str
    status: Literal["active", "processing", "complete", "failed"]
    moments_detected: int = 0
    elapsed_seconds: float = 0.0
    latest_moment: Optional[str] = Field(None, description="Description of the last detected moment")
