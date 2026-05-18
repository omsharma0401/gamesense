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
            "3-6 recurring behavioural patterns observed across the session. "
            "Be hyper-specific: cite the moment type, how many times it happened, and the outcome. "
            "Example: 'You hit 3 of 4 clutch situations — all late round, all low HP. Ice in your veins.' "
            "not vague generalities like 'You made some mistakes.'"
        ),
    )
    summary: str = Field(
        "",
        description=(
            "One paragraph session summary in second-person coaching voice. "
            "Be specific and vivid. Lead with the session's defining quality in one punchy sentence. "
            "Reference actual moment types and counts. "
            "End with the one thing that, if fixed, would unlock the next level."
        ),
    )
    epic_summary: str = Field(
        "",
        description=(
            "One short, punchy sentence — Spotify Wrapped energy. "
            "Captures the defining vibe of this session. "
            "Examples: 'Pure aggression. Five kills, zero chill.' "
            "'You played the long game — and it paid off.' "
            "'Consistency was your weapon today.' "
            "Do NOT start with 'You'. Make it feel like a headline."
        ),
    )
    persona: str = Field(
        "",
        description=(
            "A 2-4 word player archetype title that captures how the player performed this session. "
            "Arcade Racing examples: 'The Smooth Operator', 'The Overtake Machine', 'The Corner Cutter'. "
            "Tactical Shooter examples: 'The Clutch Artist', 'The Entry Fragger', 'The Support Anchor'. "
            "RTS examples: 'The Macro Mastermind', 'The Micro Mechanic', 'The Rush Specialist'. "
            "Match the persona to the most dominant pattern in the session."
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
    game_name: Optional[str] = Field(None, description="Specific game title, e.g. 'Mario Kart 8'")


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
    game_name: Optional[str] = None
    player_id: str
    status: Literal["active", "processing", "complete", "failed"]
    moments_detected: int = 0
    elapsed_seconds: float = 0.0
    latest_moment: Optional[str] = Field(None, description="Description of the last detected moment")
