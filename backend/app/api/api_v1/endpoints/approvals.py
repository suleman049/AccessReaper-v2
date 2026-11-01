"""
Access approval decision queue endpoints.
Enforces optimistic double-submit protection (409 Conflict) and updates assignments
according to governance rules.
"""

import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.security import UserClaims, require_role
from app.core.time import KARACHI_TZ
from app.db.models import (
    AccessRequest,
    Assignment,
    AuditLog,
    AuditSnapshot,
    Finding,
    GitHubConfig,
    Identity,
    Resource,
    utc_now,
)
from app.db.session import get_db
from app.engine.scoring import (
    IdentityContext,
    ResourceContext,
    evaluate_risk,
)
from app.schemas.iam import ApprovalDecisionRequest, ApprovalSchema, CreateApprovalRequest
from app.schemas.serializers import serialize_approval

logger = logging.getLogger("accessreaper.approvals")

router = APIRouter()


@router.get("/approvals", response_model=list[ApprovalSchema])
def list_approvals(
    status_filter: str | None = Query("Pending", alias="status"),
    q: str | None = "",
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    query = db.query(AccessRequest).options(
        joinedload(AccessRequest.identity),
        joinedload(AccessRequest.resource),
    )

    if status_filter and status_filter != "All requests":
        query = query.filter(AccessRequest.status == status_filter)

    requests = query.order_by(AccessRequest.requested_at.desc()).all()

    q_lower = (q or "").strip().lower()
    if q_lower:
        requests = [
            r for r in requests if q_lower in f"{r.identity.name} {r.resource.name} {r.id} {r.business_reason}".lower()
        ]

    return [serialize_approval(r) for r in requests]


@router.post("/approvals/{id}/decision", response_model=ApprovalSchema)
def decide_approval_request(
    id: str,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    req = (
        db.query(AccessRequest)
        .options(
            joinedload(AccessRequest.identity),
            joinedload(AccessRequest.resource),
        )
        .filter(AccessRequest.id == id)
        .with_for_update()
        .first()
    )
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Approval request not found."}},
        )

    # Optimistic double-submit check: only Pending can be decided
    if req.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "ALREADY_DECIDED",
                    "message": f"Request {id} is already in '{req.status}' state.",
                }
            },
        )

    # SoD approval integrity: a person can never approve or reject their own access request
    requester_email = (req.identity.email if req.identity else "").strip().lower()
    approver_email = (user.email or "").strip().lower()
    if requester_email and approver_email and requester_email == approver_email:
        blocked_event = AuditLog(
            id=f"EVT-BLOCKED-{int(time.time() * 1000)}",
            actor=user.name or user.email,
            tag="Request",
            title="Self-approval attempt blocked",
            detail=f"Admin {user.email} attempted to {payload.action.lower()} own request {id} for {req.resource.name if req.resource else 'resource'}",
            note=payload.note or "Blocked by Separation of Duties policy: cannot approve or reject own request.",
            source="AccessReaper",
            request_id=req.id,
            tone="orange",
            icon="−",
            mode="DRY_RUN",
            occurred_at=utc_now(),
        )
        db.add(blocked_event)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "SOD_SELF_APPROVAL_FORBIDDEN",
                    "message": "Separation of Duties violation: administrators cannot approve or reject their own access requests. Another administrator must review this request.",
                }
            },
        )

    # Check for existing assignment
    assignment = (
        db.query(Assignment)
        .options(joinedload(Assignment.finding))
        .filter(
            Assignment.identity_id == req.identity_id,
            Assignment.resource_id == req.resource_id,
        )
        .with_for_update()
        .first()
    )

    before_access = assignment.access_level if assignment else "None"
    action = payload.action
    now_karachi = datetime.now(KARACHI_TZ)
    reviewed_at_str = now_karachi.strftime("%b %d, %Y, %I:%M %p").replace(" 0", " ")

    # Resolve GitHub login for this identity if applicable
    github_login = None
    if assignment and assignment.github_login:
        github_login = assignment.github_login
    elif req.identity:
        other_a = (
            db.query(Assignment)
            .filter(Assignment.identity_id == req.identity_id, Assignment.github_login.isnot(None))
            .first()
        )
        if other_a:
            github_login = other_a.github_login
        elif req.identity.email:
            a_by_email = (
                db.query(Assignment)
                .join(Identity)
                .filter(Identity.email == req.identity.email, Assignment.github_login.isnot(None))
                .first()
            )
            if a_by_email:
                github_login = a_by_email.github_login

    if not github_login and req.identity:
        from app.db.models import GitHubIdentityMap
        gh_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.email == req.identity.email.lower()).first()
        if gh_map:
            github_login = gh_map.login

    is_live_github = False

    if action == "Approved":
        target_access = "None" if req.type == "Access removal" else req.requested_access

        # Execute Live GitHub Collaborator Permission Update if connected
        is_github_resource = (req.resource.source == "GitHub" or "/" in req.resource.name)
        if is_github_resource and github_login:
            gh_config = db.query(GitHubConfig).first()
            if gh_config and gh_config.connected and gh_config.encrypted_token and getattr(settings, "ENABLE_LIVE_GITHUB_REVOCATION", True):
                try:
                    from app.core.crypto import decrypt_secret
                    from app.integrations.github.client import GitHubClient
                    token = decrypt_secret(gh_config.encrypted_token)
                    owner = gh_config.org_name
                    repo_full = req.resource.name
                    repo_short = repo_full.split("/")[-1] if "/" in repo_full else repo_full
                    with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as gh_client:
                        if target_access == "None":
                            gh_client.remove_repository_collaborator(org=owner, repo=repo_short, username=github_login)
                            if assignment:
                                assignment.external_status = "revoked_externally"
                            logger.info("Executed live GitHub collaborator revocation via approval: @%s from %s/%s", github_login, owner, repo_short)
                        else:
                            gh_client.update_repository_collaborator_permission(org=owner, repo=repo_short, username=github_login, permission=target_access)
                            if assignment:
                                assignment.external_status = "active"
                            logger.info("Executed live GitHub collaborator permission update via approval: @%s on %s/%s to '%s'", github_login, owner, repo_short, target_access)
                    is_live_github = True
                except Exception as exc:
                    logger.error("Live GitHub collaborator approval execution error for @%s: %s", github_login, exc)

        if not assignment and target_access != "None":
            # Create new assignment for this user & resource
            existing_ids = db.query(Assignment.id).all()
            max_num = 2840
            for (eid,) in existing_ids:
                if eid.startswith("FND-"):
                    try:
                        max_num = max(max_num, int(eid[4:]))
                    except ValueError:
                        pass
            new_id = f"FND-{max_num + 1}"

            eval_res = evaluate_risk(
                identity=IdentityContext(
                    name=req.identity.name,
                    email=req.identity.email,
                    job_role=req.identity.job_role,
                    team=req.identity.team,
                    employment_status=req.identity.employment_status,
                ),
                resource=ResourceContext(
                    name=req.resource.name,
                    source=req.resource.source,
                    is_sensitive=req.resource.is_sensitive,
                ),
                access_level=target_access,
                last_activity_text="Approved access",
            )

            assignment = Assignment(
                id=new_id,
                identity_id=req.identity_id,
                resource_id=req.resource_id,
                access_level=target_access,
                origin="github" if is_github_resource else "sample",
                github_login=github_login,
                last_active_at=utc_now(),
                last_active_text="Approved access",
                resolved=target_access != "Admin",
                reviewed_at=reviewed_at_str,
                current_risk="High" if target_access == "Admin" else "Low",
                reason="Approved elevated access requires periodic review"
                if target_access == "Admin"
                else "Access matches approved request",
            )
            db.add(assignment)

            finding = Finding(
                id=new_id,
                assignment_id=new_id,
                original_reason=assignment.reason,
                original_severity=assignment.current_risk,
                original_access=target_access,
                detected_at=utc_now(),
                status="Open" if target_access == "Admin" else "Approved change",
                snapshot={
                    "role": req.identity.job_role,
                    "team": req.identity.team,
                    "source": req.resource.source,
                    "lastActiveAt": utc_now().isoformat(),
                    "lastActivity": "Approved access",
                },
                evidence=eval_res.evidence,
            )
            db.add(finding)
        elif assignment:
            assignment.access_level = target_access
            assignment.reviewed_at = reviewed_at_str
            if github_login and not assignment.github_login:
                assignment.github_login = github_login
            if target_access == "Admin" and before_access != "Admin":
                assignment.resolved = False
                assignment.current_risk = "High"
                if assignment.finding:
                    assignment.finding.status = "Open"
            elif target_access != "Admin":
                assignment.resolved = True
                if assignment.finding:
                    assignment.finding.status = "Approved change"

        if req.duration_hours and req.duration_hours > 0 and target_access != "None":
            from datetime import timedelta
            expires_at = utc_now() + timedelta(hours=req.duration_hours)
            req.expires_at = expires_at
            if assignment:
                assignment.is_temporary = True
                assignment.expires_at = expires_at
                assignment.warning_email_sent_at = None

        after_access = target_access
    else:
        # Declined: revoke direct grant if this was an unapproved direct GitHub grant review
        if req.type == "Direct GitHub Grant Review":
            target_access = "None"
            is_github_resource = (req.resource.source == "GitHub" or "/" in req.resource.name)
            if is_github_resource and github_login:
                gh_config = db.query(GitHubConfig).first()
                if gh_config and gh_config.connected and gh_config.encrypted_token and getattr(settings, "ENABLE_LIVE_GITHUB_REVOCATION", True):
                    try:
                        from app.core.crypto import decrypt_secret
                        from app.integrations.github.client import GitHubClient
                        token = decrypt_secret(gh_config.encrypted_token)
                        owner = gh_config.org_name
                        repo_full = req.resource.name
                        repo_short = repo_full.split("/")[-1] if "/" in repo_full else repo_full
                        with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as gh_client:
                            gh_client.remove_repository_collaborator(org=owner, repo=repo_short, username=github_login)
                        if assignment:
                            assignment.access_level = "None"
                            assignment.external_status = "revoked_externally"
                            assignment.resolved = True
                        logger.info("Revoked unapproved direct GitHub grant for @%s on %s/%s", github_login, owner, repo_short)
                    except Exception as exc:
                        logger.error("Could not revoke direct GitHub grant on decline: %s", exc)
            after_access = "None"
        else:
            after_access = before_access

    # Update request record
    req.status = action
    req.decided_by = user.name
    req.decided_at = utc_now()

    # Dispatch security webhook alert
    try:
        from app.engine.webhook_service import send_security_webhook
        duration_label = f"{int(round(req.duration_hours * 60))} Minutes (JIT)" if (req.duration_hours and req.duration_hours < 1) else (f"{int(req.duration_hours)} Hours (JIT)" if req.duration_hours else "Permanent")
        send_security_webhook(
            title=f"Access Request {action}",
            description=f"Administrator **{user.name}** has **{action.lower()}** the access request for **{req.identity.name}** on repository **{req.resource.name}**.",
            color_hex="#16a34a" if action == "Approved" else "#dc2626",
            fields=[
                {"name": "Resource", "value": req.resource.name, "inline": True},
                {"name": "User", "value": req.identity.name, "inline": True},
                {"name": "Permission", "value": target_access if action == "Approved" else req.requested_access, "inline": True},
                {"name": "Duration", "value": duration_label, "inline": True},
                {"name": "Decision Note", "value": payload.note or "None", "inline": False},
            ],
        )
    except Exception as exc:
        logger.warning("Could not dispatch webhook for approval decision: %s", exc)

    # Dispatch automated email notice to user
    try:
        from app.engine.email_service import send_approval_decision_email_to_user
        recipient_email = req.identity.email if req.identity else None
        if recipient_email and not recipient_email.endswith("@github.unmatched"):
            send_approval_decision_email_to_user(
                to_email=recipient_email,
                user_name=req.identity.name if req.identity else "Team Member",
                repo_name=req.resource.name,
                action=action,
                access_level=target_access if action == "Approved" else req.requested_access,
                admin_name=user.name or "Administrator",
                admin_note=payload.note,
                business_reason=req.business_reason,
            )
    except Exception as exc:
        logger.warning("Could not dispatch approval decision email: %s", exc)

    # Append to audit log
    event_id = f"EVT-{int(time.time() * 1000)}"
    log_entry = AuditLog(
        id=event_id,
        actor=user.name,
        tag=action,
        title=f"Access request {'approved' if action == 'Approved' else 'rejected'}",
        detail=f"{req.identity.name} · {req.resource.name}{f' (Live GitHub: @{github_login})' if is_live_github else ''}",
        note=payload.note,
        source=req.resource.source,
        assignment_id=assignment.id if assignment else None,
        request_id=req.id,
        audit_id=None,
        before=before_access,
        after=after_access,
        tone="green" if action == "Approved" else "gray",
        icon="✓" if action == "Approved" else "−",
        mode="LIVE_GITHUB" if is_live_github else "DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(log_entry)

    # Take snapshot
    assignments_all = db.query(Assignment).all()
    high = sum(1 for a in assignments_all if not a.resolved and a.current_risk == "High")
    medium = sum(1 for a in assignments_all if not a.resolved and a.current_risk == "Medium")
    healthy = sum(1 for a in assignments_all if not a.resolved and a.current_risk == "Low")
    resolved = sum(1 for a in assignments_all if a.resolved and a.finding and a.finding.original_severity != "Low")
    remediated_count = db.query(AuditLog).filter(AuditLog.tag == "Remediated").count()

    snapshot = AuditSnapshot(
        at=utc_now(),
        label=f"Access request {action.lower()}",
        high=high,
        medium=medium,
        healthy=healthy,
        resolved=resolved,
        assignments=len(assignments_all),
        remediated=remediated_count,
    )
    db.add(snapshot)

    db.commit()
    db.refresh(req)

    # In-app broadcast notification for live UI updates
    try:
        from app.engine.notification_service import broadcast_notification
        broadcast_notification(
            db=db,
            event_type="approval_decided",
            title=f"Access request {action.lower()}",
            message=f"Request {req.id} for {req.identity.name} ({req.requested_access} on {req.resource.name}) was {action.lower()} by {user.name or user.email}.",
            link="#approvals",
        )
    except Exception as exc:
        logger.warning("Could not dispatch decision in-app notification: %s", exc)

    return serialize_approval(req)


def _process_access_request(
    payload: CreateApprovalRequest,
    db: Session,
    actor: str,
    is_public: bool = False,
) -> ApprovalSchema:
    identity = None
    if payload.identity_id:
        identity = db.query(Identity).filter(Identity.id == payload.identity_id).first()
    elif payload.email:
        identity = db.query(Identity).filter(Identity.email == payload.email.strip().lower()).first()

    if not identity and payload.github_login:
        login_clean = payload.github_login.strip().lstrip("@")
        from app.db.models import GitHubIdentityMap
        gh_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == login_clean).first()
        if gh_map and gh_map.email:
            identity = db.query(Identity).filter(Identity.email == gh_map.email.lower()).first()

    if not identity:
        login_clean = (payload.github_login or "").strip().lstrip("@")
        email_clean = payload.email.strip().lower() if payload.email else (f"{login_clean}@payhive.internal" if login_clean else None)
        if email_clean:
            name = payload.name or (login_clean if login_clean else email_clean.split("@")[0].replace(".", " ").title())
            initials = "".join([part[0].upper() for part in name.split()[:2]]) or (login_clean[:2].upper() if login_clean else "U")
            identity = Identity(
                id=str(uuid.uuid4()),
                name=name,
                email=email_clean,
                initials=initials,
                job_role="External Collaborator" if is_public else "Developer",
                team="External" if is_public else "Engineering",
                employment_status="contractor" if is_public else "active",
            )
            db.add(identity)
            db.flush()

            if login_clean:
                from app.db.models import GitHubIdentityMap
                gh_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == login_clean).first()
                if not gh_map:
                    gh_map = GitHubIdentityMap(login=login_clean, email=email_clean, source="auto", account_type="user")
                    db.add(gh_map)
                    db.flush()
                elif not gh_map.email:
                    gh_map.email = email_clean
                    db.flush()

    if not identity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_IDENTITY", "message": "Valid employee email or GitHub username is required."}},
        )

    repo_clean = payload.repo_name.strip()
    resource = db.query(Resource).filter(Resource.name == repo_clean).first()
    if not resource:
        resource = Resource(
            id=str(uuid.uuid4()),
            name=repo_clean,
            source="GitHub",
            is_sensitive=any(kw in repo_clean.lower() for kw in ["prod", "infra", "auth", "payment", "gateway", "billing"]),
        )
        db.add(resource)
        db.flush()

    existing_reqs = db.query(AccessRequest.id).all()
    max_req_num = 1045
    for (rid,) in existing_reqs:
        if rid.startswith("REQ-"):
            try:
                max_req_num = max(max_req_num, int(rid[4:]))
            except ValueError:
                pass
    req_id = f"REQ-{max_req_num + 1}"

    eval_res = evaluate_risk(
        identity=IdentityContext(
            name=identity.name,
            email=identity.email,
            job_role=identity.job_role,
            team=identity.team,
            employment_status=identity.employment_status,
        ),
        resource=ResourceContext(
            name=resource.name,
            source=resource.source,
            is_sensitive=resource.is_sensitive,
        ),
        access_level=payload.access_level,
        last_activity_text="New request",
    )

    req = AccessRequest(
        id=req_id,
        identity_id=identity.id,
        resource_id=resource.id,
        requested_access=payload.access_level,
        type=payload.type or ("Self-service access request" if is_public else "Access request"),
        duration_hours=payload.duration_hours,
        business_reason=payload.business_reason,
        risk=eval_res.risk_level,
        status="Pending",
        requested_at=utc_now(),
        requested_text="Just now",
    )
    db.add(req)

    # Dispatch security webhook alert for new request
    try:
        from app.engine.webhook_service import send_security_webhook
        duration_str = f"{int(round(payload.duration_hours * 60))} Minutes (JIT)" if (payload.duration_hours and payload.duration_hours < 1) else (f"{int(payload.duration_hours)} Hours (JIT)" if payload.duration_hours else "Permanent")
        send_security_webhook(
            title="New Access Request Submitted" if not is_public else "New Public Access Request Submitted",
            description=f"**{identity.name}** submitted an access request for **{payload.access_level}** access on **{resource.name}**.",
            color_hex="#3b82f6",
            fields=[
                {"name": "User", "value": identity.name, "inline": True},
                {"name": "GitHub Login", "value": f"@{payload.github_login.strip().lstrip('@')}" if payload.github_login else "N/A", "inline": True},
                {"name": "Resource", "value": resource.name, "inline": True},
                {"name": "Permission", "value": payload.access_level, "inline": True},
                {"name": "Duration", "value": duration_str, "inline": True},
                {"name": "Business Justification", "value": payload.business_reason, "inline": False},
            ],
        )
    except Exception as exc:
        logger.warning("Could not dispatch webhook for new access request: %s", exc)

    event_id = f"EVT-{int(time.time() * 1000)}"
    log_entry = AuditLog(
        id=event_id,
        actor=actor,
        tag="Request",
        title="New access request submitted" if not is_public else "Public self-service access request submitted",
        detail=f"{identity.name} · {resource.name} · {payload.access_level}",
        note=payload.business_reason,
        source=resource.source,
        request_id=req_id,
        tone="orange",
        icon="+",
        mode="LIVE_GITHUB" if resource.source == "GitHub" else "DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(req)

    # In-app broadcast notification for live UI updates
    try:
        from app.engine.notification_service import broadcast_notification
        user_tag = f"@{payload.github_login.strip().lstrip('@')}" if payload.github_login else identity.name
        broadcast_notification(
            db=db,
            event_type="access_requested",
            title=f"Access requested: {user_tag}",
            message=f"{identity.name} ({user_tag}) requested {payload.access_level} access to {resource.name}.",
            link="#approvals",
        )
    except Exception as exc:
        logger.warning("Could not dispatch access requested in-app notification: %s", exc)

    return serialize_approval(req)


@router.post("/approvals", response_model=ApprovalSchema)
def create_approval_request(
    payload: CreateApprovalRequest,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Submits a new access request for an identity on a target repository (Admin-initiated).
    """
    return _process_access_request(payload=payload, db=db, actor=user.name or user.email, is_public=False)


@router.post("/requests/public", response_model=ApprovalSchema)
@router.post("/approvals/public-request", response_model=ApprovalSchema)
def create_public_access_request(
    payload: CreateApprovalRequest,
    db: Session = Depends(get_db),
):
    """
    Public self-service access request endpoint for external friends, contractors, or team members.
    No admin authentication required. Submissions immediately create an AccessRequest and trigger
    real-time in-app broadcast alerts for administrators.
    """
    actor_label = f"@{payload.github_login.strip().lstrip('@')}" if payload.github_login else (payload.name or "Self-service requester")
    return _process_access_request(payload=payload, db=db, actor=actor_label, is_public=True)


@router.get("/requests/public/repositories", response_model=list[str])
def list_public_repositories(
    db: Session = Depends(get_db),
):
    """
    Returns repository names available for public self-service access requests.
    """
    repos = db.query(Resource.name).filter(Resource.is_archived.is_(False)).distinct().all()
    repo_names = [r[0] for r in repos if "/" in r[0] or "repo" in r[0].lower() or "payhive" in r[0].lower()]
    if not repo_names:
        repo_names = ["payhive-eng/payment-gateway", "payhive-eng/auth-service", "payhive-eng/billing-engine", "payhive-eng/mobile-app"]
    return sorted(list(set(repo_names)))
