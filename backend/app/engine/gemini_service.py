"""
Backward-compatibility adapter for AI explanation service in AccessReaper v2.
Delegates to the unified LLMProvider subsystem in app.services.llm (Groq primary, Gemini fallback).
"""


from sqlalchemy.orm import Session

from app.db.models import AIExplanation, Assignment, AuditRun
from app.services.llm.manager import llm_manager
from app.services.llm.sanitizer import (
    clean_untrusted_text,
    pseudonymize,
)
from app.services.llm.template_provider import TemplateProvider

_template = TemplateProvider()
_clean_untrusted_text = clean_untrusted_text
_pseudonymize = pseudonymize


def generate_fallback_executive_summary(run: AuditRun) -> str:
    sources_text = " and ".join(s.get("source", "") for s in (run.sources or []) if s.get("source") != "Firestore") or "GitHub"
    info = {
        "assignments": run.assignments,
        "identities": run.identities,
        "high": run.high,
        "medium": run.medium,
        "healthy": run.healthy,
        "resolved": run.resolved,
        "sources_text": sources_text,
    }
    summary, _ = _template.generate_summary(info)
    return summary


def generate_fallback_finding_explanation(assignment: Assignment) -> tuple[str, str]:
    finding_dict = {
        "reason": assignment.reason or (assignment.finding.original_reason if assignment.finding else ""),
        "resource": assignment.resource.name if assignment.resource else "the resource",
        "access": assignment.access_level,
        "team": assignment.identity.team if assignment.identity else "",
    }
    return _template.generate_finding_explanation(finding_dict)


def generate_audit_explanations(
    db: Session,
    audit_run: AuditRun,
    assignments: list[Assignment],
) -> tuple[AIExplanation, list[AIExplanation]]:
    """
    Unified entry point: generates executive summary & finding explanations
    using the configured LLM provider chain (Groq primary, Gemini fallback, Template fallback).
    """
    return llm_manager.generate_explanations(db, audit_run, assignments)


def get_cached_audit_summary(db: Session, run_id: str) -> AIExplanation | None:
    return (
        db.query(AIExplanation)
        .filter(AIExplanation.run_id == run_id, AIExplanation.finding_id.is_(None))
        .first()
    )


def get_cached_finding_explanation(db: Session, finding_id: str) -> AIExplanation | None:
    return (
        db.query(AIExplanation)
        .filter(AIExplanation.finding_id == finding_id)
        .order_by(AIExplanation.generated_at.desc())
        .first()
    )
