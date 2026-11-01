"""
Access assignments and finding review endpoints.
Implements filtering, detail view, remediation, and dismissal in strict transactions.
"""

import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger("accessreaper.assignments")

from app.core.config import settings
from app.core.crypto import decrypt_secret
from app.core.security import UserClaims, require_role
from app.core.time import KARACHI_TZ, calculate_days_inactive
from app.db.models import (
    AccessRequest,
    AIExplanation,
    Assignment,
    AuditLog,
    AuditSnapshot,
    GitHubConfig,
    Identity,
    Setting,
    utc_now,
)
from app.db.session import get_db
from app.engine.scoring import (
    FindingContext,
    IdentityContext,
    ResourceContext,
    evaluate_risk,
)
from app.schemas.iam import (
    NoteRequest,
    PersonSchema,
)
from app.schemas.serializers import (
    serialize_approval,
    serialize_assignment,
    serialize_audit_log,
)

router = APIRouter()


def create_snapshot_entry(db: Session, label: str):
    """Creates a new audit snapshot reflecting latest counts."""
    assignments = db.query(Assignment).all()
    high = sum(1 for a in assignments if not a.resolved and a.current_risk == "High")
    medium = sum(1 for a in assignments if not a.resolved and a.current_risk == "Medium")
    healthy = sum(1 for a in assignments if not a.resolved and a.current_risk == "Low")
    resolved = sum(1 for a in assignments if a.resolved and a.finding and a.finding.original_severity != "Low")
    remediated_count = db.query(AuditLog).filter(AuditLog.tag == "Remediated").count()

    snapshot = AuditSnapshot(
        at=utc_now(),
        label=label,
        high=high,
        medium=medium,
        healthy=healthy,
        resolved=resolved,
        assignments=len(assignments),
        remediated=remediated_count,
    )
    db.add(snapshot)


@router.get("/assignments")
def list_assignments(
    risk: str | None = "All risks",
    access: str | None = "All access levels",
    source: str | None = "All sources",
    user_email: str | None = Query(None, alias="user"),
    resource_name: str | None = Query(None, alias="resource"),
    action: str | None = "All actions",
    q: str | None = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(6, ge=1, le=100, alias="pageSize"),
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    setting = db.query(Setting).filter(Setting.key == "dataMode").first()
    data_mode = setting.value if setting and setting.value in ("sample", "live") else "sample"

    query = db.query(Assignment).options(
        joinedload(Assignment.identity),
        joinedload(Assignment.resource),
        joinedload(Assignment.finding),
    )
    if data_mode == "live":
        query = query.filter(Assignment.origin == "github", Assignment.external_status != "revoked_externally")
    else:
        query = query.filter(Assignment.origin == "sample")

    all_assignments = query.all()

    # Apply in-memory filtering to match frontend Governance logic exactly
    filtered = []
    q_lower = (q or "").strip().lower()

    for a in all_assignments:
        is_unmatched = a.identity.team == "Unmatched" or (
            a.identity.email and a.identity.email.endswith("@github.unmatched")
        )
        eval_res = evaluate_risk(
            identity=IdentityContext(
                name=a.identity.name,
                email=a.identity.email,
                job_role=a.identity.job_role,
                team=a.identity.team,
                employment_status=a.identity.employment_status,
                current_project=a.identity.current_project,
                is_unmatched=is_unmatched,
                github_login=a.github_login,
            ),
            resource=ResourceContext(
                name=a.resource.name,
                source=a.resource.source,
                is_sensitive=a.resource.is_sensitive,
                project=a.resource.project,
            ),
            access_level=a.access_level,
            last_active_days=calculate_days_inactive(a.last_active_at),
            last_activity_text=a.last_active_text or "",
            finding_context=FindingContext(
                direct_admin_bypass=a.direct_admin_bypass,
                privileged_inactive=a.privileged_inactive,
            ),
            resolved=a.resolved,
            finding_status=a.finding.status if a.finding else "Open",
        )

        # Risk filter
        if risk and risk != "All risks":
            if a.resolved or a.current_risk != risk:
                continue

        # Access filter
        if access and access != "All access levels":
            if a.access_level != access:
                continue

        # Source filter
        if source and source != "All sources":
            if a.resource.source != source:
                continue

        # User filter
        if user_email and user_email != "All users":
            if a.identity.email != user_email:
                continue

        # Resource filter
        if resource_name and resource_name != "All resources":
            if a.resource.name != resource_name:
                continue

        # Action filter
        if action and action != "All actions":
            if eval_res.action_label != action:
                continue

        # Query filter
        if q_lower:
            text = f"{a.identity.name} {a.identity.email} {a.resource.name} {a.identity.team} {a.reason} {a.resource.source}".lower()
            if q_lower not in text:
                continue

        filtered.append(a)

    total = len(filtered)
    start = (page - 1) * page_size
    items = [serialize_assignment(a) for a in filtered[start : start + page_size]]

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.get("/assignments/{id}")
def get_assignment_detail(
    id: str,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    assignment = (
        db.query(Assignment)
        .options(
            joinedload(Assignment.identity),
            joinedload(Assignment.resource),
            joinedload(Assignment.finding),
        )
        .filter((Assignment.id == id) | (Assignment.identity.has(Identity.email == id)))
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Assignment not found."}},
        )

    eval_res = evaluate_risk(
        identity=IdentityContext(
            name=assignment.identity.name,
            email=assignment.identity.email,
            job_role=assignment.identity.job_role,
            team=assignment.identity.team,
            employment_status=assignment.identity.employment_status,
        ),
        resource=ResourceContext(
            name=assignment.resource.name,
            source=assignment.resource.source,
            is_sensitive=assignment.resource.is_sensitive,
            project=assignment.resource.project,
        ),
        access_level=assignment.access_level,
        last_active_days=calculate_days_inactive(assignment.last_active_at),
        last_activity_text=assignment.last_active_text or "",
        finding_context=FindingContext(
            direct_admin_bypass=assignment.direct_admin_bypass,
            privileged_inactive=assignment.privileged_inactive,
        ),
        resolved=assignment.resolved,
        finding_status=assignment.finding.status if assignment.finding else "Open",
    )

    # Timeline events for this assignment
    events = (
        db.query(AuditLog).filter(AuditLog.assignment_id == assignment.id).order_by(AuditLog.occurred_at.desc()).all()
    )

    # Related access requests
    requests = (
        db.query(AccessRequest)
        .filter(
            AccessRequest.identity_id == assignment.identity_id,
            AccessRequest.resource_id == assignment.resource_id,
        )
        .order_by(AccessRequest.requested_at.desc())
        .all()
    )

    ai_exp = (
        db.query(AIExplanation)
        .filter(AIExplanation.finding_id == assignment.id)
        .order_by(AIExplanation.generated_at.desc())
        .first()
    )

    return {
        "assignment": serialize_assignment(assignment, ai_exp),
        "recommendation": eval_res.recommendation,
        "timeline": [serialize_audit_log(e) for e in events],
        "relatedRequests": [serialize_approval(r) for r in requests],
    }


@router.post("/assignments/{id}/remediate", response_model=PersonSchema)
def remediate_finding(
    id: str,
    payload: NoteRequest,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    assignment = (
        db.query(Assignment)
        .options(
            joinedload(Assignment.identity),
            joinedload(Assignment.resource),
            joinedload(Assignment.finding),
        )
        .filter(Assignment.id == id)
        .with_for_update()
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Assignment finding not found.",
                }
            },
        )

    # Check if finding is open (not resolved and not low risk)
    if assignment.resolved or assignment.current_risk == "Low":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "ALREADY_DECIDED",
                    "message": "Finding has already been reviewed or is healthy.",
                }
            },
        )

    eval_res = evaluate_risk(
        identity=IdentityContext(
            name=assignment.identity.name,
            email=assignment.identity.email,
            job_role=assignment.identity.job_role,
            team=assignment.identity.team,
            employment_status=assignment.identity.employment_status,
        ),
        resource=ResourceContext(
            name=assignment.resource.name,
            source=assignment.resource.source,
            is_sensitive=assignment.resource.is_sensitive,
            project=assignment.resource.project,
        ),
        access_level=assignment.access_level,
        last_active_days=calculate_days_inactive(assignment.last_active_at),
        last_activity_text=assignment.last_active_text or "",
        finding_context=FindingContext(
            direct_admin_bypass=assignment.direct_admin_bypass,
            privileged_inactive=assignment.privileged_inactive,
        ),
    )

    before_access = assignment.access_level
    if payload.target_access is not None:
        target_access = payload.target_access
    elif payload.action == "revoke":
        target_access = "None"
    else:
        target_access = eval_res.recommended_target

    now_karachi = datetime.now(KARACHI_TZ)
    reviewed_at_str = now_karachi.strftime("%b %d, %Y, %I:%M %p").replace(" 0", " ")

    # Handle Live GitHub management (Revocation or Permission Reduction)
    is_live_github = False
    if assignment.origin == "github" and assignment.github_login:
        gh_config = db.query(GitHubConfig).first()
        if gh_config and gh_config.connected and gh_config.encrypted_token and getattr(settings, "ENABLE_LIVE_GITHUB_REVOCATION", True):
            try:
                from app.integrations.github.client import GitHubClient
                token = decrypt_secret(gh_config.encrypted_token)
                owner = gh_config.org_name
                repo_full = assignment.resource.name
                repo_short = repo_full.split("/")[-1] if "/" in repo_full else repo_full
                with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as gh_client:
                    if target_access == "None":
                        gh_client.remove_repository_collaborator(org=owner, repo=repo_short, username=assignment.github_login)
                        assignment.external_status = "revoked_externally"
                        logger.info("Executed live GitHub collaborator revocation: @%s from %s/%s", assignment.github_login, owner, repo_short)
                    else:
                        gh_client.update_repository_collaborator_permission(org=owner, repo=repo_short, username=assignment.github_login, permission=target_access)
                        logger.info("Executed live GitHub collaborator permission update: @%s on %s/%s to '%s'", assignment.github_login, owner, repo_short, target_access)
                is_live_github = True
            except Exception as exc:
                logger.error("Live GitHub collaborator management error for @%s: %s", assignment.github_login, exc)

    # Dispatch automated email notice to user upon access revocation or permission reduction
    try:
        from app.engine.email_service import send_revocation_email_to_user
        recipient_email = assignment.identity.email
        if recipient_email and not recipient_email.endswith("@github.unmatched"):
            send_revocation_email_to_user(
                to_email=recipient_email,
                user_name=assignment.identity.name,
                repo_name=assignment.resource.name,
                previous_access=before_access,
                reason=assignment.reason or (assignment.finding.original_reason if assignment.finding else "IAM access governance review"),
                admin_note=payload.note,
                new_access=target_access,
            )
    except Exception as exc:
        logger.warning("Could not dispatch user access notice email: %s", exc)

    # Update assignment & finding in one transaction
    assignment.access_level = target_access
    assignment.resolved = True
    if assignment.finding:
        assignment.finding.status = "Remediated"
    assignment.reviewed_at = reviewed_at_str

    # Create append-only audit log entry
    event_id = f"EVT-{int(time.time() * 1000)}"
    mode_str = "LIVE_GITHUB" if is_live_github else "DRY_RUN"
    detail_str = f"{assignment.identity.name} · {assignment.resource.name}"
    if is_live_github:
        detail_str += f" (Live GitHub Revocation Executed: @{assignment.github_login})"

    log_entry = AuditLog(
        id=event_id,
        actor=user.name,
        tag="Remediated",
        title="Permission changed" if target_access != "None" else "Access revoked",
        detail=detail_str,
        note=payload.note,
        source=assignment.resource.source,
        assignment_id=assignment.id,
        request_id=None,
        audit_id=None,
        before=before_access,
        after=target_access,
        tone="green",
        icon="✓",
        mode=mode_str,
        occurred_at=utc_now(),
    )
    db.add(log_entry)

    create_snapshot_entry(db, "Permission changed")
    db.commit()
    db.refresh(assignment)

    ai_exp = (
        db.query(AIExplanation)
        .filter(AIExplanation.finding_id == assignment.id)
        .order_by(AIExplanation.generated_at.desc())
        .first()
    )

    return serialize_assignment(assignment, ai_exp)


@router.post("/assignments/{id}/dismiss", response_model=PersonSchema)
def dismiss_finding(
    id: str,
    payload: NoteRequest,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    assignment = (
        db.query(Assignment)
        .options(
            joinedload(Assignment.identity),
            joinedload(Assignment.resource),
            joinedload(Assignment.finding),
        )
        .filter(Assignment.id == id)
        .with_for_update()
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Assignment finding not found.",
                }
            },
        )

    if assignment.resolved or assignment.current_risk == "Low":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "ALREADY_DECIDED",
                    "message": "Finding has already been reviewed or is healthy.",
                }
            },
        )

    before_access = assignment.access_level
    now_karachi = datetime.now(KARACHI_TZ)
    reviewed_at_str = now_karachi.strftime("%b %d, %Y, %I:%M %p").replace(" 0", " ")

    # Update assignment & finding in one transaction
    assignment.resolved = True
    if assignment.finding:
        assignment.finding.status = "Dismissed"
    assignment.reviewed_at = reviewed_at_str

    event_id = f"EVT-{int(time.time() * 1000)}"
    log_entry = AuditLog(
        id=event_id,
        actor=user.name,
        tag="Dismissed",
        title="Risk finding dismissed",
        detail=f"{assignment.identity.name} · {assignment.resource.name}",
        note=payload.note,
        source=assignment.resource.source,
        assignment_id=assignment.id,
        request_id=None,
        audit_id=None,
        before=before_access,
        after=before_access,
        tone="gray",
        icon="✓",
        mode="DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(log_entry)

    create_snapshot_entry(db, "Risk finding dismissed")
    db.commit()
    db.refresh(assignment)

    ai_exp = (
        db.query(AIExplanation)
        .filter(AIExplanation.finding_id == assignment.id)
        .order_by(AIExplanation.generated_at.desc())
        .first()
    )

    return serialize_assignment(assignment, ai_exp)
