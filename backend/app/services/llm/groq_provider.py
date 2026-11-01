"""
Groq LLM Provider for AccessReaper v2.
Connects to Groq's high-speed OpenAI-compatible chat completions endpoint (api.groq.com/openai/v1).
Optimized for Groq free-tier constraints:
- Compact JSON prompts
- Request-rate spacing & exponential backoff on 429
- Strict timeouts and token limits
- Absolute secret confidentiality (headers never logged)
"""

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.budget import wait_for_rate_limit
from app.services.llm.sanitizer import SYSTEM_INSTRUCTION

logger = logging.getLogger("accessreaper.llm.groq")

GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._explicit_key = api_key
        self._explicit_model = model

    @property
    def api_key(self) -> str | None:
        return self._explicit_key if self._explicit_key is not None else settings.GROQ_API_KEY

    @property
    def model(self) -> str:
        return self._explicit_model if self._explicit_model is not None else settings.GROQ_MODEL

    @property
    def name(self) -> str:
        return "groq"

    @property
    def model_identifier(self) -> str:
        return self.model or "groq/default"

    def is_configured(self) -> bool:
        key = self.api_key
        model = self.model
        return bool(key and key.strip() and model and model.strip())

    def _build_prompt(self, audit_run_info: dict[str, Any] | None, findings: list[dict[str, Any]]) -> str:
        payload: dict[str, Any] = {}
        if audit_run_info:
            payload["audit_overview"] = {
                "id": audit_run_info.get("id"),
                "assignments_checked": audit_run_info.get("assignments", 0),
                "identities": audit_run_info.get("identities", 0),
                "high_risk": audit_run_info.get("high", 0),
                "medium_risk": audit_run_info.get("medium", 0),
                "healthy": audit_run_info.get("healthy", 0),
                "sources": audit_run_info.get("sources", []),
            }
        payload["findings_to_evaluate"] = findings

        need_summary = audit_run_info is not None
        schema_desc = (
            "{\n"
            + ('  "executive_summary": "2-3 concise factual sentences summarizing posture",\n' if need_summary else "")
            + '  "findings": [\n'
            '    {"id": "<finding_id>", "explanation": "<1-2 sentence plain risk explanation>", "recommendation": "<1 sentence action>"}\n'
            "  ]\n"
            "}"
        )

        return (
            f"Review the following IAM audit data and return raw JSON conforming to this schema:\n{schema_desc}\n\n"
            f"```json\n{json.dumps(payload, indent=1)}\n```"
        )

    def generate_audit_batch(
        self,
        audit_run_info: dict[str, Any] | None,
        findings: list[dict[str, Any]],
    ) -> tuple[str | None, dict[str, tuple[str, str]], int]:
        if not self.is_configured():
            raise ValueError("Groq provider is not configured.")

        wait_for_rate_limit()

        prompt_content = self._build_prompt(audit_run_info, findings)

        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 700,
        }

        # Safe headers: bearer token is read from private attribute
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Execute call with retry on 429
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with httpx.Client(timeout=25.0) as client:
                    resp = client.post(GROQ_BASE_URL, json=request_body, headers=headers)

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    reset_tokens = resp.headers.get("x-ratelimit-reset-tokens")
                    sleep_sec = 2.0 * (attempt + 1)
                    if retry_after and retry_after.replace(".", "").isdigit():
                        sleep_sec = float(retry_after)
                    elif reset_tokens:
                        clean_t = reset_tokens.rstrip("s").strip()
                        try:
                            sleep_sec = min(float(clean_t) + 0.5, 12.0)
                        except ValueError:
                            pass
                    if attempt < max_attempts - 1 and sleep_sec <= 20.0:
                        logger.warning("Groq rate limit (429); backing off for %.1f seconds", sleep_sec)
                        time.sleep(sleep_sec)
                        continue
                    resp.raise_for_status()

                resp.raise_for_status()
                data = resp.json()
                break
            except httpx.HTTPStatusError as http_err:
                status_c = http_err.response.status_code
                logger.warning("Groq API returned HTTP error: status=%d", status_c)
                raise
            except (httpx.ConnectError, httpx.ReadTimeout) as conn_err:
                if attempt < max_attempts - 1:
                    logger.warning("Groq connection glitch (%s); retrying in 1.5s", type(conn_err).__name__)
                    time.sleep(1.5)
                    continue
                logger.warning("Groq API request error: %s", type(conn_err).__name__)
                raise
            except Exception as exc:
                logger.warning("Groq API request error: %s", type(exc).__name__)
                raise

        # Parse response
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("Groq returned empty choices.")

        content_raw = choices[0].get("message", {}).get("content", "").strip()
        # Clean markdown wrappers if any
        if content_raw.startswith("```json"):
            content_raw = content_raw[7:]
        if content_raw.startswith("```"):
            content_raw = content_raw[3:]
        if content_raw.endswith("```"):
            content_raw = content_raw[:-3]

        parsed = json.loads(content_raw.strip())
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
