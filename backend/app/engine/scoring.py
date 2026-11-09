"""
Risk engine for AccessReaper v2.
Pure, deterministic, rule-based scoring without database access.
"""

import fnmatch
from dataclasses import dataclass
from typing import Any

from app.core.time import calculate_days_inactive


def get_default_rule_config() -> dict[str, Any]:
    return {
        "dormantDays": 90,
        "unknownActivityCountsAsDormant": False,
        "inactiveOutsideCollaboratorDays": 30,
        "dormantIdentityDays": 90,
        "sodConflicts": [
            {
                "id": "sod-default-infra-billing",
                "pattern_a": "*terraform*",
                "access_a": "Admin",
                "pattern_b": "*payment*",
                "access_b": "Admin",
                "description": "Separation of Duties: Infrastructure Admin and Payment/Billing Admin conflict",
                "points": 50,
                "enabled": True,
            }
        ],
        "thresholds": {
            "highMin": 70,
            "mediumMin": 40,
        },
        "points": {
            "dormant": 40,
            "projectMismatch": 30,
            "elevatedAccess": 20,
            "sensitiveResource": 10,
            "formerEmployee": 80,
            "contractorAdmin": 50,
            "firestoreAdmin": 50,
            "directAdminBypass": 40,
            "privilegedInactive": 40,
            "unmatchedAccount": 40,
            "unmatchedAccountElevated": 70,
            "sodConflict": 50,
            "busFactor": 30,
            "archivedRepo": 40,
            "inactiveOutsideCollaborator": 50,
            "dormantIdentity": 30,
        },
        "rulesEnabled": {
            "dormant": True,
            "projectMismatch": True,
            "elevatedAccess": True,
            "sensitiveResource": True,
            "formerEmployee": True,
            "contractorAdmin": True,
            "firestoreAdmin": True,
            "directAdminBypass": True,
            "privilegedInactive": True,
            "unmatchedAccount": True,
            "sodConflict": True,
            "busFactor": True,
            "archivedRepo": True,
            "inactiveOutsideCollaborator": True,
            "dormantIdentity": True,
        },
    }


@dataclass
class IdentityContext:
    name: str
    email: str
    job_role: str
    team: str
    employment_status: str  # "active", "former", "contractor"
    current_project: str | None = None
    is_unmatched: bool = False
    github_login: str | None = None
    account_type: str = "user"  # "user", "bot", "service", "ignored"
    is_outside_collaborator: bool = False
    active_assignment_count: int | None = None


@dataclass
class ResourceContext:
    name: str
    source: str  # "GitHub", "Firestore"
    is_sensitive: bool = False
    project: str | None = None
    is_archived: bool = False
    admin_count: int | None = None


@dataclass
class FindingContext:
    direct_admin_bypass: bool = False
    privileged_inactive: bool = False
    custom_reason: str | None = None


@dataclass
class FiredRule:
    code: str
    name: str
    points: int
    reason: str


@dataclass
class RiskEvaluation:
    score: int
    risk_level: str  # "High", "Medium", "Low"
    primary_reason: str
    recommended_target: str  # "Admin", "Write", "Read", "Editor", "Viewer", "None"
    action_label: str  # "Revoke access", "Reduce access", "Keep access", "Reviewed"
    fired_rules: list[FiredRule]
    evidence: list[str]
    recommendation: dict


def evaluate_risk(
    identity: IdentityContext,
    resource: ResourceContext,
    access_level: str,
    last_active_days: int | None = None,
    last_activity_text: str = "Not recorded",
    finding_context: FindingContext | None = None,
    resolved: bool = False,
    finding_status: str = "Open",
    rule_config: dict[str, Any] | None = None,
    other_assignments: list[tuple[str, str]] | None = None,
    sod_conflicts: list[dict[str, Any]] | None = None,
) -> RiskEvaluation:
    """
    Evaluates permission risk deterministically based on rules and context.
    Optionally accepts a rule configuration payload; defaults to standard rules.
    """
    config = rule_config or get_default_rule_config()
    points_map = config.get("points", {})
    rules_enabled = config.get("rulesEnabled", {})
    thresholds = config.get("thresholds", {})
    dormant_days_thresh = config.get("dormantDays", 90)
    unknown_as_dormant = config.get("unknownActivityCountsAsDormant", False)

    ctx = finding_context or FindingContext()
    fired_rules: list[FiredRule] = []
    score = 0

    # 1. Base rule: Access level is Admin or Write (+20)
    if rules_enabled.get("elevatedAccess", True) and access_level in ("Admin", "Write"):
        pts = int(points_map.get("elevatedAccess", 20))
        score += pts
        fired_rules.append(
            FiredRule(
                code="ELEVATED_ACCESS",
                name="Access level is Admin or Write",
                points=pts,
                reason="Elevated permission level assigned",
            )
        )

    # 2. Base rule: Resource is marked sensitive (+10)
    if rules_enabled.get("sensitiveResource", True) and resource.is_sensitive:
        pts = int(points_map.get("sensitiveResource", 10))
        score += pts
        fired_rules.append(
            FiredRule(
                code="SENSITIVE_RESOURCE",
                name="Resource is marked sensitive",
                points=pts,
                reason="Target resource contains sensitive infrastructure or production data",
            )
        )

    # 3. Base rule: Permission unused for dormant_days_thresh+ days (+40)
    if rules_enabled.get("dormant", True):
        if last_active_days is not None and last_active_days >= dormant_days_thresh:
            pts = int(points_map.get("dormant", 40))
            score += pts
            fired_rules.append(
                FiredRule(
                    code="UNUSED_90_DAYS",
                    name=f"Permission unused for {dormant_days_thresh}+ days",
                    points=pts,
                    reason=f"Permission inactive for {last_active_days} days (threshold is {dormant_days_thresh} days)",
                )
            )
        elif last_active_days is None and unknown_as_dormant:
            pts = int(points_map.get("dormant", 40))
            score += pts
            fired_rules.append(
                FiredRule(
                    code="UNUSED_90_DAYS",
                    name=f"Permission unused for {dormant_days_thresh}+ days",
                    points=pts,
                    reason="Permission has no recorded activity (treated as dormant by rule option)",
                )
            )

    # 4. Base rule: Permission's project differs from user's current project/team (+30)
    is_team_mismatch = False
    if resource.project and identity.team:
        if resource.project.lower() != identity.team.lower():
            is_team_mismatch = True
    elif identity.team == "Design" and "customer-portal" in resource.name:
        is_team_mismatch = True

    if rules_enabled.get("projectMismatch", True) and is_team_mismatch:
        pts = int(points_map.get("projectMismatch", 30))
        score += pts
        fired_rules.append(
            FiredRule(
                code="PROJECT_MISMATCH",
                name="Permission's project differs from current project/team",
                points=pts,
                reason="Assigned repository does not match identity team focus",
            )
        )

    # --- Named frontend-visible rules ---

    # 5. Former employee still holding access (High, +80)
    is_former_employee = identity.employment_status == "former" or identity.team.lower() == "former employee"
    if rules_enabled.get("formerEmployee", True) and is_former_employee and access_level != "None":
        pts = int(points_map.get("formerEmployee", 80))
        score += pts
        fired_rules.append(
            FiredRule(
                code="FORMER_EMPLOYEE_ACTIVE",
                name="Former employee still holding access",
                points=pts,
                reason="Former employee account is still active",
            )
        )

    # 6. External contractor with Admin (High, +50)
    is_contractor = (
        identity.employment_status == "contractor"
        or identity.team.lower() == "external"
        or "contractor" in identity.job_role.lower()
    )
    # If temporary/JIT contractor admin (e.g. project manager on fixed lease), do not flag as perpetual high-risk
    is_temporary_lease = getattr(assignment_ctx, "is_temporary", False) if "assignment_ctx" in locals() else False
    if rules_enabled.get("contractorAdmin", True) and is_contractor and access_level == "Admin" and not is_temporary_lease:
        pts = int(points_map.get("contractorAdmin", 50))
        score += pts
        fired_rules.append(
            FiredRule(
                code="CONTRACTOR_ADMIN",
                name="External contractor with Admin",
                points=pts,
                reason="External account has administrator access",
            )
        )

    # 7. Firestore app admin beyond duties (High, +50)
    if (
        rules_enabled.get("firestoreAdmin", True)
        and resource.source == "Firestore"
        and access_level == "Admin"
        and identity.team in ("Support", "Customer Support")
    ):
        pts = int(points_map.get("firestoreAdmin", 50))
        score += pts
        fired_rules.append(
            FiredRule(
                code="FIRESTORE_ADMIN_EXCESS",
                name="Firestore app admin beyond duties",
                points=pts,
                reason="Application admin role exceeds support duties",
            )
        )

    # 8. Direct admin grant bypasses team policy (+40)
    if rules_enabled.get("directAdminBypass", True) and ctx.direct_admin_bypass and access_level == "Admin":
        pts = int(points_map.get("directAdminBypass", 40))
        score += pts
        fired_rules.append(
            FiredRule(
                code="DIRECT_ADMIN_POLICY_BYPASS",
                name="Direct admin grant bypasses team policy",
                points=pts,
                reason="Direct admin grant bypasses team policy",
            )
        )

    # 9. Privileged access with no recent activity (+40)
    if rules_enabled.get("privilegedInactive", True) and ctx.privileged_inactive and access_level == "Admin":
        pts = int(points_map.get("privilegedInactive", 40))
        score += pts
        fired_rules.append(
            FiredRule(
                code="PRIVILEGED_INACTIVE_30_DAYS",
                name="Privileged access with no recent activity",
                points=pts,
                reason="Privileged access with no recent activity",
            )
        )

    # 10. Unmatched GitHub account rule (Medium severity, High if Admin or Write)
    # Excludes accounts classified as bot, service, or ignored (accepted risk)
    is_unmatched = getattr(identity, "is_unmatched", False) and getattr(identity, "account_type", "user") not in (
        "bot",
        "service",
        "ignored",
    )
    if rules_enabled.get("unmatchedAccount", True) and is_unmatched and access_level != "None":
        if access_level in ("Admin", "Write"):
            pts = int(points_map.get("unmatchedAccountElevated", 70))
            score += pts
            fired_rules.append(
                FiredRule(
                    code="UNMATCHED_GITHUB_ACCOUNT_ELEVATED",
                    name="Unmatched GitHub account with elevated access",
                    points=pts,
                    reason="GitHub account not linked to a known employee holds elevated access",
                )
            )
        else:
            pts = int(points_map.get("unmatchedAccount", 40))
            score += pts
            fired_rules.append(
                FiredRule(
                    code="UNMATCHED_GITHUB_ACCOUNT",
                    name="GitHub account not linked to a known employee",
                    points=pts,
                    reason="GitHub account is not linked to a known employee",
                )
            )

    # Helper for SoD matching
    def _matches_sod_pair(res_name: str, acc: str, pat: str, req_acc: str) -> bool:
        patterns = [p.strip() for p in pat.split(",") if p.strip()]
        name_matched = any(fnmatch.fnmatchcase(res_name.lower(), p.lower()) for p in patterns)
        if not name_matched:
            return False
        if req_acc == "*" or req_acc.lower() == "any":
            return True
        return acc.lower() == req_acc.lower()

    # 11. Separation of Duties conflicting access pairs (+50)
    active_sod_rules = sod_conflicts if sod_conflicts is not None else config.get("sodConflicts", [])
    is_owner_or_root = (
        identity.email in ("msulee110@gmail.com", "24sw049@gmail.com")
        or identity.job_role in ("Workspace Administrator", "Owner", "Organization Owner", "Lead Platform Architect")
        or getattr(identity, "github_login", "") in ("suleman049", "MisbahHub")
    )
    if is_owner_or_root:
        active_sod_rules = []
    sod_conflict_found = False
    sod_conflict_target = None
    if rules_enabled.get("sodConflict", True) and other_assignments and active_sod_rules:
        for sod in active_sod_rules:
            if not sod.get("enabled", True):
                continue
            pat_a = sod.get("pattern_a", "")
            acc_a = sod.get("access_a", "Admin")
            pat_b = sod.get("pattern_b", "")
            acc_b = sod.get("access_b", "Admin")

            curr_match_a = _matches_sod_pair(resource.name, access_level, pat_a, acc_a)
            curr_match_b = _matches_sod_pair(resource.name, access_level, pat_b, acc_b)

            if curr_match_a:
                for other_name, other_acc in other_assignments:
                    if _matches_sod_pair(other_name, other_acc, pat_b, acc_b):
                        sod_conflict_found = True
                        sod_conflict_target = (other_name, other_acc)
                        break
            elif curr_match_b:
                for other_name, other_acc in other_assignments:
                    if _matches_sod_pair(other_name, other_acc, pat_a, acc_a):
                        sod_conflict_found = True
                        sod_conflict_target = (other_name, other_acc)
                        break

            if sod_conflict_found and sod_conflict_target:
                pts = int(sod.get("points") or points_map.get("sodConflict", 50))
                score += pts
                fired_rules.append(
                    FiredRule(
                        code="SOD_CONFLICT",
                        name="Separation of duties conflict",
                        points=pts,
                        reason=f"Separation of duties conflict: holds {access_level} on '{resource.name}' and {sod_conflict_target[1]} on '{sod_conflict_target[0]}'",
                    )
                )
                break

    # 12. Archived repository still granting Write/Admin access (+40)
    if (
        rules_enabled.get("archivedRepo", True)
        and getattr(resource, "is_archived", False)
        and access_level in ("Admin", "Write")
    ):
        pts = int(points_map.get("archivedRepo", 40))
        score += pts
        fired_rules.append(
            FiredRule(
                code="ARCHIVED_REPO_ACTIVE_ACCESS",
                name="Archived repository still grants Write/Admin access",
                points=pts,
                reason="Archived repository still grants Write/Admin access",
            )
        )

    # 13. Inactive outside collaborator with elevated access (+50)
    is_outside_collab = (
        getattr(identity, "is_outside_collaborator", False)
        or identity.employment_status == "contractor"
        or identity.team.lower() == "external"
    )
    inactive_collab_thresh = config.get("inactiveOutsideCollaboratorDays", 30)
    is_collab_inactive = last_active_days is None or last_active_days >= inactive_collab_thresh
    if (
        rules_enabled.get("inactiveOutsideCollaborator", True)
        and is_outside_collab
        and access_level in ("Admin", "Write")
        and is_collab_inactive
    ):
        pts = int(points_map.get("inactiveOutsideCollaborator", 50))
        score += pts
        fired_rules.append(
            FiredRule(
                code="INACTIVE_OUTSIDE_COLLABORATOR",
                name="Inactive outside collaborator with elevated access",
                points=pts,
                reason="Inactive outside collaborator holds elevated access",
            )
        )

    # 14. Repository has single point of failure (<= 1 admin) (+30)
    admin_count = getattr(resource, "admin_count", None)
    if (
        rules_enabled.get("busFactor", True)
        and admin_count is not None
        and admin_count <= 1
        and access_level == "Admin"
    ):
        pts = int(points_map.get("busFactor", 30))
        score += pts
        fired_rules.append(
            FiredRule(
                code="BUS_FACTOR_SINGLE_ADMIN",
                name="Repository has single point of failure (<= 1 admin)",
                points=pts,
                reason="Repository has single point of failure (<= 1 admin)",
            )
        )

    # 15. Active identity with zero assignments (+30)
    active_assignments_count = getattr(identity, "active_assignment_count", None)
    if (
        rules_enabled.get("dormantIdentity", True)
        and identity.employment_status == "active"
        and (active_assignments_count == 0 or access_level == "None")
    ):
        pts = int(points_map.get("dormantIdentity", 30))
        score += pts
        fired_rules.append(
            FiredRule(
                code="DORMANT_ACTIVE_IDENTITY",
                name="Active employee holds no active assignments",
                points=pts,
                reason="Active employee identity holds no active permission assignments",
            )
        )

    # Determine risk level from thresholds
    high_min = int(thresholds.get("highMin", 70))
    medium_min = int(thresholds.get("mediumMin", 40))

    if score >= high_min:
        risk_level = "High"
    elif score >= medium_min:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    # Primary reason selection
    if ctx.custom_reason:
        primary_reason = ctx.custom_reason
    elif any(r.code in ("UNMATCHED_GITHUB_ACCOUNT", "UNMATCHED_GITHUB_ACCOUNT_ELEVATED") for r in fired_rules):
        primary_reason = "GitHub account not linked to a known employee"
    elif any(r.code == "FORMER_EMPLOYEE_ACTIVE" for r in fired_rules):
        primary_reason = "Former employee account is still active"
    elif any(r.code == "SOD_CONFLICT" for r in fired_rules):
        primary_reason = "Separation of duties conflict"
    elif any(r.code == "ARCHIVED_REPO_ACTIVE_ACCESS" for r in fired_rules):
        primary_reason = "Archived repository still grants Write/Admin access"
    elif any(r.code == "CONTRACTOR_ADMIN" for r in fired_rules):
        primary_reason = "External account has administrator access"
    elif any(r.code == "INACTIVE_OUTSIDE_COLLABORATOR" for r in fired_rules):
        primary_reason = "Inactive outside collaborator holds elevated access"
    elif any(r.code == "FIRESTORE_ADMIN_EXCESS" for r in fired_rules):
        primary_reason = "Application admin role exceeds support duties"
    elif any(r.code == "DIRECT_ADMIN_POLICY_BYPASS" for r in fired_rules):
        primary_reason = "Direct admin grant bypasses team policy"
    elif any(r.code == "PRIVILEGED_INACTIVE_30_DAYS" for r in fired_rules):
        primary_reason = "Privileged access with no recent activity"
    elif any(r.code == "UNUSED_90_DAYS" for r in fired_rules):
        if last_active_days is not None:
            primary_reason = f"Elevated access unused for {last_active_days} days"
        else:
            primary_reason = "Elevated access has no recorded activity"
    elif any(r.code == "BUS_FACTOR_SINGLE_ADMIN" for r in fired_rules):
        primary_reason = "Repository has single point of failure (<= 1 admin)"
    elif any(r.code == "DORMANT_ACTIVE_IDENTITY" for r in fired_rules):
        primary_reason = "Active employee identity holds no active permission assignments"
    elif any(r.code == "PROJECT_MISMATCH" for r in fired_rules):
        primary_reason = "Team mismatch for repository access"
    elif risk_level == "Low":
        if resource.source == "Firestore":
            if access_level == "Editor":
                primary_reason = "Application role matches current responsibilities"
            else:
                primary_reason = "Read-only application role matches current responsibilities"
        else:
            if access_level == "Read":
                primary_reason = "Read access matches current role"
            else:
                primary_reason = "Access matches current role"
    else:
        primary_reason = "Policy check flagged assignment for review"

    # Target calculation
    is_bus_factor_primary = any(r.code == "BUS_FACTOR_SINGLE_ADMIN" for r in fired_rules) and not any(
        r.code
        in (
            "FORMER_EMPLOYEE_ACTIVE",
            "SOD_CONFLICT",
            "ARCHIVED_REPO_ACTIVE_ACCESS",
            "INACTIVE_OUTSIDE_COLLABORATOR",
            "UNUSED_90_DAYS",
            "DIRECT_ADMIN_POLICY_BYPASS",
            "PRIVILEGED_INACTIVE_30_DAYS",
            "UNMATCHED_GITHUB_ACCOUNT_ELEVATED",
        )
        for r in fired_rules
    )

    if is_former_employee:
        recommended_target = "None"
    elif any(r.code == "ARCHIVED_REPO_ACTIVE_ACCESS" for r in fired_rules):
        recommended_target = "None"
    elif any(r.code == "INACTIVE_OUTSIDE_COLLABORATOR" for r in fired_rules) and not any(
        r.code == "CONTRACTOR_ADMIN" for r in fired_rules
    ):
        recommended_target = "None"
    elif is_unmatched:
        recommended_target = "None" if risk_level == "High" else "Read"
    elif is_bus_factor_primary:
        recommended_target = access_level
    elif resource.source == "Firestore":
        recommended_target = "Viewer" if risk_level != "Low" else access_level
    else:
        recommended_target = "Read" if risk_level != "Low" else access_level

    # Action label
    if resolved:
        action_label = "Reviewed"
    elif is_bus_factor_primary and risk_level != "Low":
        action_label = "Assign owner"
    elif risk_level == "Low":
        action_label = "Keep access"
    elif recommended_target == "None":
        action_label = "Revoke access"
    else:
        action_label = "Reduce access"

    # Employment description
    if is_unmatched:
        emp_desc = "unmatched GitHub account"
    elif is_former_employee:
        emp_desc = "employment ended"
    elif is_contractor:
        emp_desc = "external contractor"
    else:
        emp_desc = "active employee"

    # Format activity text for evidence:
    # Prompt: "If unknown, store last_active_at = null and the engine must treat null as "unknown" (add an evidence line "no recorded activity found")"
    if last_active_days is None or not last_activity_text or last_activity_text in ("Not recorded", "None"):
        formatted_activity_text = "no recorded activity found"
    else:
        formatted_activity_text = last_activity_text

    # Evidence construction
    if is_unmatched:
        identity_evidence = (
            f"Identity: GitHub login @{identity.github_login or identity.name} is not linked to a known employee."
        )
    else:
        identity_evidence = f"Identity: {identity.job_role}, {identity.team}; {emp_desc}."

    evidence = [
        f"Assignment: {access_level} on {resource.name} ({resource.source}).",
        identity_evidence,
        f"Last recorded resource activity: {formatted_activity_text}.",
    ]

    # Recommendation object matching frontend Governance.recommendation(p)
    is_open = not resolved and risk_level != "Low"
    if not is_open:
        rec_title = "Decision recorded" if resolved else "Keep current access"
        rec_body = (
            f"The original finding is preserved above. Current access is {access_level}; outcome: {finding_status}."
            if resolved
            else "The sample policy check found no mismatch with the recorded responsibilities."
        )
        recommendation = {
            "title": rec_title,
            "body": rec_body,
            "target": access_level,
            "outcome": "No permission change required.",
        }
    else:
        if action_label == "Assign owner":
            justification = "Repository has only one administrator, presenting a single point of failure risk."
            rec_title = "Assign secondary repository owner"
            rec_outcome = "Ensure repository redundancy with at least two administrators."
        elif any(r.code == "SOD_CONFLICT" for r in fired_rules):
            justification = "Separation of duties conflict: holding elevated privileges across sensitive domain boundaries violates governance policy."
            rec_title = f"Reduce {access_level} to {recommended_target}"
            rec_outcome = f"Retain {recommended_target.lower()} visibility and eliminate conflicting elevated permissions; the finding will be marked Remediated."
        elif any(r.code == "ARCHIVED_REPO_ACTIVE_ACCESS" for r in fired_rules):
            justification = "The repository is archived and read-only. Retaining elevated Write/Admin permissions introduces unnecessary access risk."
            rec_title = "Revoke access on archived repository"
            rec_outcome = "Remove this resource assignment; the finding will be marked Remediated."
        elif any(r.code == "INACTIVE_OUTSIDE_COLLABORATOR" for r in fired_rules):
            justification = (
                "External contractor has had no recorded activity for over 30 days while holding elevated access."
            )
            rec_title = "Revoke inactive contractor access"
            rec_outcome = "Remove this resource assignment; the finding will be marked Remediated."
        elif is_unmatched:
            justification = (
                f"GitHub login @{identity.github_login or identity.name} is not linked to a recognized employee record."
            )
            rec_title = (
                "Revoke access or link GitHub account" if recommended_target == "None" else "Link GitHub account"
            )
            rec_outcome = (
                "Remove this resource assignment; the finding will be marked Remediated."
                if recommended_target == "None"
                else f"Retain {recommended_target.lower()} visibility and remove elevated privileges; the finding will be marked Remediated."
            )
        elif is_former_employee:
            justification = "Employment has ended; the assignment should not remain active."
            rec_title = "Revoke the former employee's access"
            rec_outcome = "Remove this resource assignment; the finding will be marked Remediated."
        elif resource.source == "Firestore":
            justification = (
                f"A {identity.job_role.lower()} does not need application administration for the recorded duties."
            )
            rec_title = f"Reduce {access_level} to {recommended_target}"
            rec_outcome = f"Retain {recommended_target.lower()} visibility and remove elevated privileges; the finding will be marked Remediated."
        elif is_contractor:
            justification = "External contractor access should be limited to the documented engagement."
            rec_title = (
                "Revoke the contractor's access"
                if recommended_target == "None"
                else f"Reduce {access_level} to {recommended_target}"
            )
            rec_outcome = (
                "Remove this resource assignment; the finding will be marked Remediated."
                if recommended_target == "None"
                else f"Retain {recommended_target.lower()} visibility and remove elevated privileges; the finding will be marked Remediated."
            )
        elif "unused" in primary_reason.lower() or "activity" in primary_reason.lower():
            justification = "The recorded inactivity indicates elevated access may no longer be needed."
            rec_title = f"Reduce {access_level} to {recommended_target}"
            rec_outcome = f"Retain {recommended_target.lower()} visibility and remove elevated privileges; the finding will be marked Remediated."
        else:
            justification = (
                f"The assignment conflicts with the recorded role or permission policy: {primary_reason.lower()}."
            )
            rec_title = (
                "Revoke access" if recommended_target == "None" else f"Reduce {access_level} to {recommended_target}"
            )
            rec_outcome = (
                "Remove this resource assignment; the finding will be marked Remediated."
                if recommended_target == "None"
                else f"Retain {recommended_target.lower()} visibility and remove elevated privileges; the finding will be marked Remediated."
            )

        rec_body = justification + " Confirm the business need with the resource owner before proceeding."
        recommendation = {
            "title": rec_title,
            "body": rec_body,
            "target": recommended_target,
            "outcome": rec_outcome,
        }

    return RiskEvaluation(
        score=score,
        risk_level=risk_level,
        primary_reason=primary_reason,
        recommended_target=recommended_target,
        action_label=action_label,
        fired_rules=fired_rules,
        evidence=evidence,
        recommendation=recommendation,
    )


def calculate_security_health_score(assignments: list[Any], pending_count: int = 0) -> dict[str, Any]:
    """
    Calculates organization-wide Security Health Score (0-100),
    letter grade (A+, A, B, C, D, Critical), and risk posture status.
    """
    total = len(assignments)
    if total == 0:
        return {
            "score": 100,
            "grade": "A+",
            "status": "Optimal",
            "activeJitCount": 0,
            "dormantCount": 0,
            "summary": "No active assignments to audit.",
        }

    high_unresolved = sum(1 for a in assignments if not a.resolved and a.current_risk == "High")
    medium_unresolved = sum(1 for a in assignments if not a.resolved and a.current_risk == "Medium")
    resolved_count = sum(1 for a in assignments if a.resolved)

    active_jit = sum(
        1
        for a in assignments
        if getattr(a, "is_temporary", False) and getattr(a, "access_level", "None") != "None"
    )

    dormant_count = 0
    for a in assignments:
        if getattr(a, "privileged_inactive", False):
            dormant_count += 1
        else:
            days = calculate_days_inactive(getattr(a, "last_active_at", None), getattr(a, "origin", None))
            if days is not None and days >= 80 and getattr(a, "access_level", "None") != "None":
                dormant_count += 1

    # Base score = 100
    penalty = (high_unresolved * 15) + (medium_unresolved * 5) + (min(pending_count, 10) * 2)
    bonus = min(10, resolved_count * 2)

    raw_score = 100 - penalty + bonus
    score = max(0, min(100, raw_score))

    if score >= 95:
        grade = "A+"
        status_text = "Optimal"
    elif score >= 85:
        grade = "A"
        status_text = "Good"
    elif score >= 75:
        grade = "B"
        status_text = "Fair"
    elif score >= 60:
        grade = "C"
        status_text = "Needs Review"
    elif score >= 40:
        grade = "D"
        status_text = "Elevated Risk"
    else:
        grade = "Critical"
        status_text = "Critical Exposure"

    return {
        "score": score,
        "grade": grade,
        "status": status_text,
        "activeJitCount": active_jit,
        "dormantCount": dormant_count,
        "summary": f"{grade} ({score}/100) - {status_text}",
    }
