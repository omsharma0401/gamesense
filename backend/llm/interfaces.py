"""
llm/interfaces.py — Abstract base class for LLM providers.

Implement this to swap in any provider (OpenRouter, Groq, Anthropic, mock)
without changing any agent code. Agents only ever hold a BaseLLMProvider ref.
"""
from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Generates completions from a system + user prompt pair."""

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """
        Call the LLM and return the assistant response as a plain string.

        Args:
            system: System-level instruction prompt.
            user:   User-turn content (events, session data, etc.).

        Returns:
            Raw LLM response string. For unstructured calls this may be
            free-form text; for structured calls it should be valid JSON.
        """
        ...

    def complete_structured(self, system: str, user: str, schema_name: str = "moment_detection") -> str:
        """
        Structured output completion with JSON Schema enforcement.

        Providers that support JSON Schema mode (OpenRouter) override this
        to constrain the model output to a specific schema. Others fall back
        to complete() transparently — the agent receives the same interface.

        Args:
            schema_name: One of 'moment_detection', 'analysis_output', 'briefing_output'.
        """
        return self.complete(system, user)

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable identifier of the underlying model."""
        ...
