"""
Base interface for LLM Providers in AccessReaper v2.
All providers (Groq, Gemini, OpenAI-compatible, Template) implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider (e.g. 'groq', 'gemini', 'openai', 'template')."""
        pass

    @property
    @abstractmethod
    def model_identifier(self) -> str:
        """Model identifier string recorded in database (e.g. 'openai/gpt-oss-120b')."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """True if the provider has necessary credentials/keys configured."""
        pass

    @abstractmethod
    def generate_audit_batch(
        self,
        audit_run_info: dict[str, Any] | None,
        findings: list[dict[str, Any]],
    ) -> tuple[str | None, dict[str, tuple[str, str]], int]:
        """
        Executes a prompt for executive summary (if audit_run_info provided) and findings batch.
        Returns:
            (executive_summary_or_none, {finding_id: (explanation, recommendation)}, total_tokens_used)
        """
        pass
