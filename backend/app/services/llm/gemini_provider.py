"""
Gemini LLM Provider for AccessReaper v2.
Optional fallback provider using Google GenAI SDK (google-genai).
"""

import json
import logging
from typing import Any

from app.core.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.sanitizer import SYSTEM_INSTRUCTION

logger = logging.getLogger("accessreaper.llm.gemini")


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._explicit_key = api_key
        self._explicit_model = model

    @property
    def api_key(self) -> str | None:
        return self._explicit_key if self._explicit_key is not None else settings.GEMINI_API_KEY

    @property
    def model(self) -> str:
        return self._explicit_model if self._explicit_model is not None else settings.GEMINI_MODEL

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_identifier(self) -> str:
        return self.model or "gemini/default"

    def is_configured(self) -> bool:
        key = self.api_key
        model = self.model
        return bool(key and key.strip() and model and model.strip())

    def generate_audit_batch(
        self,
        audit_run_info: dict[str, Any] | None,
        findings: list[dict[str, Any]],
    ) -> tuple[str | None, dict[str, tuple[str, str]], int]:
        if not self.is_configured():
            raise ValueError("Gemini provider is not configured.")

        from google import genai
        from google.genai import types

        payload: dict[str, Any] = {}
        if audit_run_info:
            payload["audit_overview"] = audit_run_info
        payload["findings_to_evaluate"] = findings

        schema_desc = (
            "{\n"
            + ('  "executive_summary": "2-3 concise factual sentences summarizing posture",\n' if audit_run_info else "")
            + '  "findings": [\n'
            '    {"id": "<finding_id>", "explanation": "<1-2 sentence risk explanation>", "recommendation": "<1 sentence action>"}\n'
            "  ]\n"
            "}"
        )
        prompt_text = (
            f"Review the following IAM audit data and return raw JSON conforming to this schema:\n{schema_desc}\n\n"
            f"```json\n{json.dumps(payload, indent=1)}\n```"
        )

        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=prompt_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
            ),
        )

        raw_text = response.text or ""
        cleaned_json = raw_text.strip()
        if cleaned_json.startswith("```json"):
            cleaned_json = cleaned_json[7:]
        if cleaned_json.startswith("```"):
            cleaned_json = cleaned_json[3:]
        if cleaned_json.endswith("```"):
            cleaned_json = cleaned_json[:-3]

        parsed = json.loads(cleaned_json.strip())
        exec_summary = parsed.get("executive_summary")

        findings_map: dict[str, tuple[str, str]] = {}
        for f in parsed.get("findings", []):
            fid = f.get("id")
            expl = f.get("explanation")
            recom = f.get("recommendation", "Review access with resource owner.")
            if fid and expl:
                findings_map[fid] = (expl, recom)

        # Approximate token usage if not provided directly
        tokens_used = 400 + len(findings) * 80
        return exec_summary, findings_map, tokens_used
