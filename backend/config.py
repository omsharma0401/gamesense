"""
config.py — Central configuration for the GameSense backend.

All env vars, paths, and tuneable constants live here.
No other module calls os.getenv(). Import from here instead.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from this directory
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(_ENV_PATH, override=True)

logger = logging.getLogger(__name__)


# ── Helper coercions ──────────────────────────────────────────────────────────

def _int(val: str | None, default: int) -> int:
    try:
        return int(val) if val else default
    except (TypeError, ValueError):
        return default


def _float(val: str | None, default: float) -> float:
    try:
        return float(val) if val else default
    except (TypeError, ValueError):
        return default


# ── VideoDB ───────────────────────────────────────────────────────────────────

VIDEO_DB_API_KEY   = os.getenv("VIDEO_DB_API_KEY", "")
VIDEODB_SANDBOX_ID = os.getenv("VIDEODB_SANDBOX_ID", "")  # written by sandbox_start.py

if not VIDEO_DB_API_KEY:
    logger.warning("VIDEO_DB_API_KEY not set — CaptureAgent and VideoDB calls will fail")

# ── LLM (OpenRouter) ──────────────────────────────────────────────────────────

OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL    = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b")
LLM_TEMPERATURE     = 0.2   # slight creativity for commentary; 0.0 for structured outputs
LLM_MAX_TOKENS      = 512

if not OPENROUTER_API_KEY:
    logger.warning("OPENROUTER_API_KEY not set — all LLM calls will fail")

# ── LLM Judge (Groq — separate provider to avoid self-eval bias) ──────────────

GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL       = "https://api.groq.com/openai/v1"
GROQ_JUDGE_MODEL    = os.getenv("GROQ_JUDGE_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# ── Player / Session ──────────────────────────────────────────────────────────

PLAYER_ID           = os.getenv("PLAYER_ID", "ash")

# ── Agent Tuning ──────────────────────────────────────────────────────────────

MOMENT_POLL_INTERVAL    = _int(os.getenv("MOMENT_POLL_INTERVAL"), 30)   # seconds
MOMENT_CONTEXT_WINDOW   = _int(os.getenv("MOMENT_CONTEXT_WINDOW"), 10)  # last N events
MAX_MOMENTS_FOR_ANALYSIS = _int(os.getenv("MAX_MOMENTS_FOR_ANALYSIS"), 20)
MAX_HIGHLIGHT_CLIPS     = _int(os.getenv("MAX_HIGHLIGHT_CLIPS"), 8)
WS_LISTENER_RESTART_DELAY = _float(os.getenv("WS_LISTENER_RESTART_DELAY"), 3.0)

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT_DIR    = Path(__file__).parent
DATA_DIR    = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SQLITE_DB_PATH  = Path(os.getenv("SQLITE_DB_PATH",  str(DATA_DIR / "gamesense.db")))
KUZU_DB_PATH    = Path(os.getenv("KUZU_DB_PATH",    str(DATA_DIR / "kuzu")))
EVENTS_PATH     = Path(os.getenv("EVENTS_PATH",     "/tmp/videodb_events.jsonl"))
CAPTURE_INFO_PATH = Path("/tmp/videodb_capture_info.json")

# ── Discord ───────────────────────────────────────────────────────────────────

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# ── Indexing model tiers (from .agents/skills/videodb/reference/rtstream-reference.md)
# model_name is a tier string, NOT an enum.
#   "mini"  — fastest, lowest cost
#   "basic" — default, good for most use cases
#   "pro"   — higher accuracy
#   "ultra" — highest accuracy, slowest
VISUAL_INDEX_MODEL = os.getenv("VISUAL_INDEX_MODEL", "basic")
AUDIO_INDEX_MODEL  = os.getenv("AUDIO_INDEX_MODEL",  None)    # None = default

# ── Indexing config ───────────────────────────────────────────────────────────

VISUAL_INDEX_BATCH_SECONDS = 5
VISUAL_INDEX_FRAME_COUNT   = 3
AUDIO_INDEX_BATCH_SECONDS  = 30

VISUAL_INDEX_PROMPT = (
    "You are watching live gameplay. Describe exactly what is happening: "
    "player actions, enemy positions, health/ammo state, map area, and any "
    "significant game events. Be concise and factual."
)
AUDIO_INDEX_PROMPT = (
    "Summarize any important in-game audio: callouts, ability sounds, "
    "kill confirmations, or commentary that indicates a significant game event."
)
