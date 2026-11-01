"""
Deterministic template provider for AccessReaper v2.
Used as guaranteed fallback when all external LLMs are unavailable, rate limited,
timed out, or unconfigured. Produces crisp, accurate audit explanations.
"""

from typing import Any


class TemplateProvider:
    name: str = "template"
    model_identifier: str = "template-fallback"

    def is_configured(self) -> bool:
        return True

    def generate_summary(self, audit_run_info: dict[str, Any]) -> tuple[str, int]:
        sources = audit_run_info.get("sources_text") or "GitHub and Firestore"
        assignments = audit_run_info.get("assignments", 0)
        identities = audit_run_info.get("identities", 0)
        high = audit_run_info.get("high", 0)
        medium = audit_run_info.get("medium", 0)
        healthy = audit_run_info.get("healthy", 0)
        resolved = audit_run_info.get("resolved", 0)

        text = (
            f"The latest audit checked {assignments} access assignments for {identities} identities across {sources}. "
            f"It recorded {high} high-risk and {medium} medium-risk findings, {healthy} healthy assignments, "
            f"and {resolved} reviewed findings."
        )
        return text, 0

    def generate_finding_explanation(self, finding: dict[str, Any]) -> tuple[str, str]:
        reason = finding.get("reason", "")
        repo = finding.get("resource") or "the resource"
        access = finding.get("access") or "Access"
        team = finding.get("team") or ""
        is_former = team == "Former employee" or "former" in reason.lower()
        target = "None" if is_former else "Read"

        if "Separation of Duties" in reason or "conflict" in reason.lower() or "SOD" in reason:
            explanation = (
                f"User holds conflicting elevated privileges ({access}) across sensitive repositories "
                f"including {repo}, violating Separation of Duties safeguards."
            )
            recommendation = f"Enforce separation of duties: reduce privileges on {repo} to {target} or reassign ownership."
        elif "Contractor" in reason or "contractor" in reason.lower() or "External" in team:
            explanation = (
                f"External collaborator holds elevated administrative access on internal resource {repo}, "
                f"exceeding typical vendor boundary constraints."
            )
            recommendation = f"Enforce least-privilege: downgrade access to {target} in accordance with vendor governance policy."
        elif "inactivity" in reason.lower() or "dormant" in reason.lower() or "unused" in reason.lower():
            explanation = (
                f"Account retains elevated {access} permissions on {repo} despite prolonged inactivity, "
                f"increasing potential attack surface."
            )
            recommendation = f"Revoke dormant access or downgrade to {target} after owner confirmation."
        elif "unmatched" in reason.lower() or team == "Unmatched":
            explanation = (
                "GitHub login has not been associated with a verified corporate employee identity in directory records."
            )
            recommendation = "Map account to a verified employee in People directory, classify as a service account, or remove access."
        elif "Bus factor" in reason or "bus factor" in reason.lower():
            explanation = (
                f"Repository {repo} has a critical administrative bus-factor risk with only a single designated administrator."
            )
            recommendation = "Assign at least one backup administrative owner to ensure continuity."
        elif "Archived" in reason or "archived" in reason.lower():
            explanation = (
                f"Account retains active write or admin access on archived repository {repo}."
            )
            recommendation = "Revoke active write/admin access on archived repository to prevent unauthorized modifications."
        else:
            explanation = (
                f"Assignment on {repo} with {access} privileges triggered governance policy check: {reason}."
            )
            recommendation = f"Confirm ongoing business necessity with resource owner; downgrade to {target} if not required."

        return explanation, recommendation
