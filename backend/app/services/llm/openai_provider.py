"""
Generic OpenAI-compatible LLM Provider for AccessReaper v2.
Can connect to any OpenAI-compatible API endpoint (e.g. self-hosted vLLM, Ollama, OpenAI).
Configured via LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL.
"""

import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.sanitizer import SYSTEM_INSTRUCTION

logger = logging.getLogger("accessreaper.llm.openai")


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self._base_url = (base_url or settings.LLM_BASE_URL or "").rstrip("/")
        self._api_key = api_key or settings.LLM_API_KEY or ""
        self._model = model or settings.LLM_MODEL or ""

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model_identifier(self) -> str:
        return self._model or "openai/default"

    def is_configured(self) -> bool:
        return bool(self._base_url and self._model)

    def generate_audit_batch(
        self,
        audit_run_info: dict[str, Any] | None,
        findings: list[dict[str, Any]],
    ) -> tuple[str | None, dict[str, tuple[str, str]], int]:
        if not self.is_configured():
            raise ValueError("OpenAI-compatible provider is not configured.")

        url = f"{self._base_url}/chat/completions"
        payload: dict[str, Any] = {}
        if audit_run_info:
            payload["audit_overview"] = audit_run_info
        payload["findings_to_evaluate"] = findings

        schema_desc = (
            "{\n"
            + ('  "executive_summary": "2-3 concise sentences summarizing posture",\n' if audit_run_info else "")
            + '  "findings": [\n'
            '    {"id": "<finding_id>", "explanation": "<1-2 sentence risk explanation>", "recommendation": "<1 sentence action>"}\n'
            "  ]\n"
            "}"
        )
        prompt = (
            f"Review the following IAM audit data and return raw JSON conforming to this schema:\n{schema_desc}\n\n"
            f"```json\n{json.dumps(payload, indent=1)}\n```"
        )

        request_body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 1200,
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        with httpx.Client(timeout=25.0) as client:
            resp = client.post(url, json=request_body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            raise ValueError("Empty choices from OpenAI-compatible provider.")

        raw_text = choices[0].get("message", {}).get("content", "").strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        parsed = json.loads(raw_text.strip())
        exec_summary = parsed.get("executive_summary")

        findings_map: dict[str, tuple[str, str]] = {}
        for f in parsed.get("findings", []):
            fid = f.get("id")
            expl = f.get("explanation")
            recom = f.get("recommendation", "Review access with resource owner.")
            if fid and expl:
                findings_map[fid] = (expl, recom)

        usage = data.get("usage", {})
        total_tokens = int(usage.get("total_tokens", 0))
        return exec_summary, findings_map, total_tokens
