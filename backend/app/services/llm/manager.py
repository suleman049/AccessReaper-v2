"""
LLM Manager for AccessReaper v2.
Orchestrates provider fallback chains (Groq -> Gemini -> Template), enforces
strict daily token budgets, handles finding batching (max 6 per call),
caches explanations, and defends against prompt injections.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AIExplanation, Assignment, AuditRun
from app.services.llm.base import LLMProvider
from app.services.llm.budget import (
    get_daily_token_usage,
    is_budget_exceeded,
    record_token_usage,
)
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.groq_provider import GroqProvider
from app.services.llm.openai_provider import OpenAICompatibleProvider
from app.services.llm.sanitizer import (
    clean_untrusted_text,
    prepare_sanitized_finding,
)
from app.services.llm.template_provider import TemplateProvider

logger = logging.getLogger("accessreaper.llm.manager")


class LLMManager:
    def __init__(self):
        self._groq = GroqProvider()
        self._gemini = GeminiProvider()
        self._openai = OpenAICompatibleProvider()
        self._template = TemplateProvider()

    def get_provider(self, name: str) -> LLMProvider | None:
        name_clean = name.strip().lower()
        if name_clean == "groq":
            return self._groq
        if name_clean == "gemini":
            return self._gemini
        if name_clean in ("openai", "custom"):
            return self._openai
        if name_clean == "template":
            return self._template
        return None

    def get_provider_order(self) -> list[str]:
        raw = settings.LLM_PROVIDER_ORDER or "groq,gemini"
        return [p.strip().lower() for p in raw.split(",") if p.strip()]

    def get_status(self, db: Session) -> dict[str, Any]:
        """
        Returns safe, read-only status for UI and health checking.
        Zero credentials or keys are ever returned.
        """
        order = self.get_provider_order()
        usage_today = get_daily_token_usage(db)
        budget = settings.LLM_DAILY_TOKEN_BUDGET

        active_provider = "template"
        for p_name in order:
            prov = self.get_provider(p_name)
            if prov and prov.is_configured():
                if not is_budget_exceeded(db, estimated_tokens=100):
                    active_provider = prov.name
                    break

        return {
            "provider_order": order,
            "active_provider": active_provider,
            "groq": {
                "configured": self._groq.is_configured(),
                "model": self._groq.model_identifier if self._groq.is_configured() else "",
            },
            "gemini": {
                "configured": self._gemini.is_configured(),
                "model": self._gemini.model_identifier if self._gemini.is_configured() else "",
            },
            "openai": {
                "configured": self._openai.is_configured(),
                "model": self._openai.model_identifier if self._openai.is_configured() else "",
            },
            "daily_token_usage": usage_today,
            "daily_token_budget": budget,
            "send_real_names": bool(settings.LLM_SEND_REAL_NAMES or settings.GEMINI_SEND_REAL_NAMES),
        }

    def generate_explanations(
        self,
        db: Session,
        audit_run: AuditRun,
        assignments: list[Assignment],
    ) -> tuple[AIExplanation, list[AIExplanation]]:
        """
        Main entry point for generating executive summary & finding explanations.
        Checks database cache first: never regenerates if already recorded.
        Batches findings into groups of at most LLM_MAX_FINDINGS_PER_CALL.
        Executes provider fallback sequence on quota/429/timeout/error.
        Always returns (summary_explanation, list_of_finding_explanations).
        """
        now_utc = datetime.now(UTC)

        # 1. Check cache: do not regenerate if already cached for this run
        existing_summary = (
            db.query(AIExplanation)
            .filter(AIExplanation.run_id == audit_run.id, AIExplanation.finding_id.is_(None))
            .first()
        )
        if existing_summary:
            existing_findings = (
                db.query(AIExplanation)
                .filter(AIExplanation.run_id == audit_run.id, AIExplanation.finding_id.isnot(None))
                .all()
            )
            logger.info("Using cached AI explanations for audit run %s", audit_run.id)
            return existing_summary, existing_findings

        # 2. Filter target assignments (High and Medium findings)
        target_assignments = [
            a for a in assignments
            if not a.resolved and a.current_risk in ("High", "Medium")
        ][: settings.GEMINI_MAX_CALLS_PER_RUN]

        # 3. Prepare sanitized facts and pseudonyms
        identity_map: dict[str, str] = {}
        send_real_names = bool(settings.LLM_SEND_REAL_NAMES or settings.GEMINI_SEND_REAL_NAMES)
        sanitized_findings = [
            prepare_sanitized_finding(a, identity_map, send_real_names=send_real_names)
            for a in target_assignments
        ]

        # Audit run overview payload
        sources_text = " and ".join(s.get("source", "") for s in (audit_run.sources or [])) or "GitHub and Firestore"
        run_overview = {
            "id": audit_run.id,
            "assignments": audit_run.assignments,
            "identities": audit_run.identities,
            "high": audit_run.high,
            "medium": audit_run.medium,
            "healthy": audit_run.healthy,
            "resolved": audit_run.resolved,
            "sources": audit_run.sources or [],
            "sources_text": sources_text,
        }

        # 4. Chunk findings into batches of max LLM_MAX_FINDINGS_PER_CALL
        batch_size = max(1, settings.LLM_MAX_FINDINGS_PER_CALL)
        finding_chunks = [
            sanitized_findings[i : i + batch_size]
            for i in range(0, len(sanitized_findings), batch_size)
        ] if sanitized_findings else []

        order = self.get_provider_order()
        chosen_summary: str | None = None
        chosen_findings_map: dict[str, tuple[str, str]] = {}
        active_model_label: str = "template-fallback"
        explanation_status: str = "fallback"

        # 5. Try configured providers in order
        for provider_name in order:
            provider = self.get_provider(provider_name)
            if not provider or not provider.is_configured():
                continue

            if is_budget_exceeded(db, estimated_tokens=400):
                logger.warning(
                    "Daily LLM token budget exceeded (%d / %d); skipping %s",
                    get_daily_token_usage(db),
                    settings.LLM_DAILY_TOKEN_BUDGET,
                    provider_name,
                )
                continue

            try:
                logger.info("Attempting AI explanation generation via %s (%s)", provider.name, provider.model_identifier)
                total_tokens_consumed = 0

                if not finding_chunks:
                    # No findings to evaluate, only executive summary needed
                    summary_text, findings_map, tokens = provider.generate_audit_batch(run_overview, [])
                    total_tokens_consumed += tokens
                    chosen_summary = summary_text
                else:
                    # Process first chunk together with executive summary
                    first_chunk = finding_chunks[0]
                    summary_text, first_map, tokens = provider.generate_audit_batch(run_overview, first_chunk)
                    total_tokens_consumed += tokens
                    chosen_summary = summary_text
                    chosen_findings_map.update(first_map)

                    # Process remaining finding chunks
                    for subsequent_chunk in finding_chunks[1:]:
                        if is_budget_exceeded(db, estimated_tokens=200):
                            logger.warning("Token budget reached midway through batches; falling back for remaining findings")
                            break
                        _, chunk_map, c_tokens = provider.generate_audit_batch(None, subsequent_chunk)
                        total_tokens_consumed += c_tokens
                        chosen_findings_map.update(chunk_map)

                record_token_usage(db, total_tokens_consumed)
                active_model_label = provider.model_identifier
                explanation_status = "success"
                logger.info(
                    "Successfully generated AI explanations via %s (tokens used: %d)",
                    provider.name,
                    total_tokens_consumed,
                )
                break
            except Exception as exc:
                logger.warning(
                    "Provider %s failed (%s); falling through to next provider",
                    provider_name,
                    type(exc).__name__,
                )
                chosen_summary = None
                chosen_findings_map.clear()
                continue

        # 6. Fallback to deterministic template if needed
        if not chosen_summary:
            template_summary, _ = self._template.generate_summary(run_overview)
            chosen_summary = template_summary
            active_model_label = self._template.model_identifier
            explanation_status = "fallback"

        # 7. Create AIExplanation database entities
        summary_obj = AIExplanation(
            id=f"EXP-{uuid.uuid4().hex[:12]}",
            run_id=audit_run.id,
            finding_id=None,
            summary_text=clean_untrusted_text(chosen_summary, max_len=600),
            recommendation_text=None,
            model=active_model_label,
            status=explanation_status,
            generated_at=now_utc,
        )
        db.add(summary_obj)

        finding_objs: list[AIExplanation] = []
        for a in target_assignments:
            if a.id in chosen_findings_map:
                expl, recom = chosen_findings_map[a.id]
                model_used = active_model_label
                stat_used = explanation_status
            else:
                f_data = next((sf for sf in sanitized_findings if sf["id"] == a.id), {})
                expl, recom = self._template.generate_finding_explanation(f_data)
                model_used = "template-fallback"
                stat_used = "fallback"

            f_obj = AIExplanation(
                id=f"EXP-{uuid.uuid4().hex[:12]}",
                run_id=audit_run.id,
                finding_id=a.id,
                summary_text=clean_untrusted_text(expl, max_len=400),
                recommendation_text=clean_untrusted_text(recom, max_len=300),
                model=model_used,
                status=stat_used,
                generated_at=now_utc,
            )
            db.add(f_obj)
            finding_objs.append(f_obj)

        db.flush()
        return summary_obj, finding_objs


llm_manager = LLMManager()
