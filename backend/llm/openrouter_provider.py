"""
llm/openrouter_provider.py — OpenRouter LLM provider for GameSense.

Uses the OpenAI SDK pointed at OpenRouter's base URL. Supports:
  complete()           — free-form JSON output (json_object mode)
  complete_structured() — JSON Schema enforcement (json_schema mode)
                          Used by MomentAgent, AnalysisAgent, BriefingAgent
                          to guarantee valid field values.

Includes exponential-backoff retry for transient rate limit errors.
"""
import json
import logging
import re
import time

from openai import OpenAI, APIError, RateLimitError, APITimeoutError

from llm.interfaces import BaseLLMProvider
from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
)

logger = logging.getLogger(__name__)

_MAX_RETRIES   = 6
_RETRY_BACKOFF = 30.0  # seconds — free-tier models enforce ~30s rate-limit windows


# ── JSON Schemas for structured output calls ──────────────────────────────────

MOMENT_DETECTION_SCHEMA = {
    "name": "moment_detection",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "is_moment":    {"type": "boolean"},
            "type":         {"anyOf": [{"type": "string", "enum": ["kill", "death", "clutch", "error", "strategy_break", "highlight", "blunder"]}, {"type": "null"}]},
            "description":  {"type": "string"},
            "significance": {"type": "integer"},
            "timestamp_ms": {"type": "integer"},
            "commentary":   {"type": "string"},
        },
        "required": ["is_moment", "type", "description", "significance", "timestamp_ms", "commentary"],
        "additionalProperties": False,
    },
}

ANALYSIS_OUTPUT_SCHEMA = {
    "name": "analysis_output",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "object",
                "properties": {
                    "overall":         {"type": "integer"},
                    "mechanics":       {"type": "integer"},
                    "decision_making": {"type": "integer"},
                    "consistency":     {"type": "integer"},
                },
                "required": ["overall", "mechanics", "decision_making", "consistency"],
                "additionalProperties": False,
            },
            "patterns": {"type": "array", "items": {"type": "string"}},
            "summary":  {"type": "string"},
        },
        "required": ["score", "patterns", "summary"],
        "additionalProperties": False,
    },
}

BRIEFING_OUTPUT_SCHEMA = {
    "name": "briefing_output",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "coaching_paragraph": {"type": "string"},
            "focus_areas":        {"type": "array", "items": {"type": "string"}},
        },
        "required": ["coaching_paragraph", "focus_areas"],
        "additionalProperties": False,
    },
}

# Maps a schema name to the schema dict for routing
_SCHEMAS = {
    "moment_detection": MOMENT_DETECTION_SCHEMA,
    "analysis_output":  ANALYSIS_OUTPUT_SCHEMA,
    "briefing_output":  BRIEFING_OUTPUT_SCHEMA,
}


class OpenRouterProvider(BaseLLMProvider):
    """
    Calls any OpenRouter-hosted model using the OpenAI-compatible SDK.
    Deterministic by default (temperature from config) for reproducible outputs.
    Includes exponential-backoff retry for transient API errors.
    """

    def __init__(self, model: str | None = None):
        self._client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            timeout=30.0,   # fail fast — free-tier queue hangs indefinitely without this
        )
        self._model = model or OPENROUTER_MODEL
        logger.info("OpenRouterProvider initialised — model=%s", self._model)

    @property
    def model_name(self) -> str:
        return self._model

    # ── Internal retry wrapper ────────────────────────────────────────────────

    def _call(self, system: str, user: str, response_format: dict) -> str:
        """Retry loop around the completion API call."""
        last_exc: Exception | None = None
        wait = _RETRY_BACKOFF

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.debug(
                    "LLM call attempt %d/%d — model=%s format=%s",
                    attempt, _MAX_RETRIES, self._model, response_format.get("type"),
                )
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                    temperature=LLM_TEMPERATURE,
                    max_tokens=LLM_MAX_TOKENS,
                    response_format=response_format,
                )
                if not response.choices:
                    raise ValueError(
                        f"LLM returned empty choices (model={self._model})"
                    )
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError(
                        f"LLM returned null content (model={self._model}, "
                        f"finish_reason={response.choices[0].finish_reason})"
                    )
                content = content.strip()
                # Strip markdown code fences some models wrap around JSON
                content = re.sub(r'^```(?:json)?\s*\n?', '', content)
                content = re.sub(r'\n?```\s*$', '', content).strip()
                # Normalise common LLM output defects before repair:
                import json as _json
                # Strip non-printable control chars (keep \t \n \r)
                content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)
                try:
                    _json.loads(content)  # fast-path — already valid
                except Exception:
                    # 1. Strip leading garbage before the first { or [
                    brace = min(
                        (content.find(c) for c in ('{', '[') if c in content),
                        default=-1,
                    )
                    if brace > 0:
                        content = content[brace:]
                    # 2. Unescape double-encoded output (\n, \", \t as literal chars)
                    if '\\"' in content or '\\n' in content:
                        content = (
                            content
                            .replace('\\n', '\n')
                            .replace('\\t', '\t')
                            .replace('\\"', '"')
                        )
                # Repair remaining malformed JSON (single quotes, trailing commas, etc.)
                try:
                    from json_repair import repair_json
                    content = repair_json(content, return_objects=False)
                except Exception:
                    pass
                logger.debug(
                    "LLM response received — tokens_used=%s",
                    getattr(response.usage, "total_tokens", "unknown"),
                )
                return content

            except (RateLimitError, APITimeoutError) as exc:
                last_exc = exc
                logger.warning(
                    "OpenRouter transient error (attempt %d/%d): %s — retrying in %.1fs",
                    attempt, _MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)
                wait = min(wait * 2, 60.0)   # cap backoff at 60s

            except APIError:
                raise

        raise RuntimeError(
            f"OpenRouter API failed after {_MAX_RETRIES} retries: {last_exc}"
        )

    # ── Public interface ──────────────────────────────────────────────────────

    def complete(self, system: str, user: str) -> str:
        """
        Free-form JSON completion (json_object mode).
        Used for general LLM calls where a strict schema isn't needed.
        """
        logger.info("complete() called — model=%s", self._model)
        return self._call(system, user, {"type": "json_object"})

    def complete_structured(self, system: str, user: str, schema_name: str = "moment_detection") -> str:
        """
        Structured output with JSON Schema enforcement.
        The model is constrained to emit only values in the schema.

        Args:
            schema_name: One of 'moment_detection', 'analysis_output', 'briefing_output'.

        Falls back to json_object mode if the model doesn't support json_schema.
        """
        schema = _SCHEMAS.get(schema_name)
        if schema is None:
            logger.warning("Unknown schema_name '%s' — falling back to json_object", schema_name)
            return self.complete(system, user)

        logger.info("complete_structured() called — model=%s schema=%s", self._model, schema_name)
        try:
            return self._call(
                system, user,
                {"type": "json_schema", "json_schema": schema},
            )
        except APIError as exc:
            # Some open-weight models don't support json_schema — fall back gracefully
            logger.warning(
                "json_schema mode not supported for model=%s, falling back to json_object: %s",
                self._model, exc,
            )
            return self._call(system, user, {"type": "json_object"})
