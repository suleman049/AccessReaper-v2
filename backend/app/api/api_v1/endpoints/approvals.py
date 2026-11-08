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
    Setting,
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
    # Exception: Organization Owner (24sw049@gmail.com) holds executive break-glass approval authority
    requester_email = (req.identity.email if req.identity else "").strip().lower()
    approver_email = (user.email or "").strip().lower()
    is_owner = (getattr(user, "role", "") == "owner" or approver_email == "24sw049@gmail.com")

    if requester_email and approver_email and requester_email == approver_email and not is_owner:
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
                        # Auto-fetch user details (real name & public email) from GitHub profile
                        try:
                            gh_profile = gh_client.get_user_profile(github_login)
                            if gh_profile and req.identity:
                                gh_name = gh_profile.get("name")
                                gh_email = gh_profile.get("email")
                                if gh_name and (not req.identity.name or req.identity.name == github_login or req.identity.name == "External Collaborator"):
                                    req.identity.name = gh_name
                                if gh_email and (not req.identity.email or "@payhive.internal" in req.identity.email or "@github.unmatched" in req.identity.email):
                                    req.identity.email = gh_email.lower()
                                    from app.db.models import GitHubIdentityMap
                                    gh_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == github_login).first()
                                    if gh_map:
                                        gh_map.email = gh_email.lower()
                                        db.flush()
                        except Exception as fetch_exc:
                            logger.warning("Could not auto-fetch GitHub profile for @%s: %s", github_login, fetch_exc)

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
                origin=("github" if (db.query(Setting).filter(Setting.key == "dataMode").first() and db.query(Setting).filter(Setting.key == "dataMode").first().value == "live") else ("github" if is_live_github else "sample")),
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

    # Dispatch security webhook alert and user email asynchronously in background
    def _dispatch_alerts(identity_name, identity_email, resource_name, dur_label, note, tgt_acc, act, adm_name, biz_reason, gh_log, dur_hrs):
        try:
            from app.engine.webhook_service import send_security_webhook
            send_security_webhook(
                title=f"Access Request {act}",
                description=f"Administrator **{adm_name}** has **{act.lower()}** the access request for **{identity_name}** on repository **{resource_name}**.",
                color_hex="#16a34a" if act == "Approved" else "#dc2626",
                fields=[
                    {"name": "Resource", "value": resource_name, "inline": True},
                    {"name": "User", "value": identity_name, "inline": True},
                    {"name": "Permission", "value": tgt_acc, "inline": True},
                    {"name": "Duration", "value": dur_label, "inline": True},
                    {"name": "Decision Note", "value": note or "None", "inline": False},
                ],
            )
        except Exception as exc:
            logger.warning("Could not dispatch webhook for approval decision: %s", exc)

        try:
            from app.engine.email_service import send_approval_decision_email_to_user
            if identity_email and not identity_email.endswith("@github.unmatched"):
                send_approval_decision_email_to_user(
                    to_email=identity_email,
                    user_name=identity_name or "Team Member",
                    repo_name=resource_name,
                    action=act,
                    access_level=tgt_acc,
                    admin_name=adm_name,
                    admin_note=note,
                    business_reason=biz_reason,
                    github_login=gh_log,
                    duration_hours=dur_hrs,
                )
        except Exception as exc:
            logger.warning("Could not dispatch approval decision email: %s", exc)

    import threading
    duration_label = f"{int(round(req.duration_hours * 60))} Minutes (JIT)" if (req.duration_hours and req.duration_hours < 1) else (f"{int(req.duration_hours)} Hours (JIT)" if req.duration_hours else "Permanent")
    threading.Thread(
        target=_dispatch_alerts,
        args=(
            req.identity.name if req.identity else "",
            req.identity.email if req.identity else None,
            req.resource.name if req.resource else "",
            duration_label,
            payload.note,
            target_access if action == "Approved" else req.requested_access,
            action,
            user.name or "Administrator",
            req.business_reason,
            github_login,
            req.duration_hours,
        ),
        daemon=True,
    ).start()

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

        # Trigger immediate audit cycle post-approval asynchronously
    if action == "Approved":
        import threading
        def _run_immediate_audit():
            try:
                from app.db.session import SessionLocal
                from app.engine.automation import execute_automatic_cycle
                with SessionLocal() as bg_db:
                    execute_automatic_cycle(bg_db, actor=f"Post-Approval Auto-Audit ({user.email})")
                    logger.info("Immediate audit cycle completed after request approval %s", req.id)
            except Exception as exc:
                logger.warning("Could not execute post-approval audit cycle: %s", exc)
        threading.Thread(target=_run_immediate_audit, daemon=True, name=f"post_approval_audit_{req.id}").start()

    return serialize_approval(req)


def _process_access_request(
    payload: CreateApprovalRequest,
    db: Session,
    actor: str,
    is_public: bool = False,
    current_user: UserClaims | None = None,
) -> ApprovalSchema:
    login_clean = payload.github_login.strip().lstrip("@") if payload.github_login else None

    # Pre-fetch profile from GitHub if login is provided to get real name & email
    gh_config = db.query(GitHubConfig).first()
    gh_profile = None
    if login_clean and gh_config and gh_config.connected and gh_config.encrypted_token:
        try:
            from app.core.crypto import decrypt_secret
            from app.integrations.github.client import GitHubClient
            token = decrypt_secret(gh_config.encrypted_token)
            with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as gh_client:
                gh_profile = gh_client.get_user_profile(login_clean)
                if gh_profile:
                    if gh_profile.get("name") and (not payload.name or payload.name == login_clean):
                        payload.name = gh_profile["name"]
                    if gh_profile.get("email") and (not payload.email or "@payhive.internal" in payload.email):
                        payload.email = gh_profile["email"].lower()
        except Exception as exc:
            logger.warning("Could not pre-fetch GitHub profile for @%s: %s", login_clean, exc)

    identity = None
    if payload.identity_id:
        identity = db.query(Identity).filter(Identity.id == payload.identity_id).first()
    elif payload.email:
        identity = db.query(Identity).filter(Identity.email == payload.email.strip().lower()).first()

    if not identity and login_clean:
        from app.db.models import GitHubIdentityMap
        gh_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == login_clean).first()
        if gh_map and gh_map.email:
            identity = db.query(Identity).filter(Identity.email == gh_map.email.lower()).first()

    if not identity:
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
    else:
        # Existing identity: enrich with latest fetched info if currently placeholder
        if gh_profile:
            if gh_profile.get("name") and (not identity.name or identity.name == login_clean or identity.name == "External Collaborator"):
                identity.name = gh_profile["name"]
            if gh_profile.get("email") and ("@payhive.internal" in identity.email or "@github.unmatched" in identity.email):
                identity.email = gh_profile["email"].lower()
                db.flush()

    # If identity is resolved but login_clean was not supplied, auto-lookup from mappings or past assignments
    if identity and not login_clean:
        from app.db.models import GitHubIdentityMap
        gh_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.email == identity.email.lower()).first()
        if gh_map and gh_map.login:
            login_clean = gh_map.login
        else:
            prev_a = db.query(Assignment).filter(Assignment.identity_id == identity.id, Assignment.github_login.isnot(None)).first()
            if prev_a and prev_a.github_login:
                login_clean = prev_a.github_login

    if not identity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_IDENTITY", "message": "Valid employee email or GitHub username is required."}},
        )

    # -------------------------------------------------------------------------
    # Separation of Duties (SoD) Integrity Check on Admin Direct Onboarding:
    # Administrators CANNOT directly onboard or grant repository access to themselves!
    # -------------------------------------------------------------------------
    if not is_public and current_user:
        current_email = (current_user.email or "").strip().lower()
        target_email = (identity.email or "").strip().lower() if identity else (payload.email or "").strip().lower()
        
        is_self_onboard = False
        if current_email and target_email and current_email == target_email:
            is_self_onboard = True
        elif login_clean and current_email:
            from app.db.models import GitHubIdentityMap
            admin_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.email == current_email).first()
            if admin_map and admin_map.login and admin_map.login.lower() == login_clean.lower():
                is_self_onboard = True
            elif current_email.split("@")[0].lower() == login_clean.lower():
                is_self_onboard = True

        if is_self_onboard:
            blocked_event = AuditLog(
                id=f"EVT-BLOCKED-{int(time.time() * 1000)}",
                actor=current_user.name or current_user.email,
                tag="Request",
                title="Self-onboarding attempt blocked",
                detail=f"Admin {current_user.email} attempted to directly onboard/grant access to themselves on {payload.repo_name}",
                note="Blocked by Separation of Duties policy: administrators cannot directly onboard or grant repository permissions to themselves.",
                source="AccessReaper",
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
                        "code": "SOD_SELF_ONBOARD_FORBIDDEN",
                        "message": "Separation of Duties violation: administrators cannot directly onboard or grant repository access to themselves. Another administrator must review this request.",
                    }
                },
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
        last_activity_text="New onboard" if not is_public else "New request",
    )

    now_karachi = datetime.now(KARACHI_TZ)
    reviewed_at_str = now_karachi.strftime("%b %d, %Y, %I:%M %p").replace(" 0", " ")

    if not is_public:
        # ---------------------------------------------------------------------
        # ADMIN DIRECT ONBOARDING / PROVISIONING
        # Directly approved, live provisioned on GitHub, and recorded immediately
        # ---------------------------------------------------------------------
        is_live_github = False
        target_access = payload.access_level
        is_github_resource = (resource.source == "GitHub" or "/" in resource.name)

        if is_github_resource and login_clean:
            if gh_config and gh_config.connected and gh_config.encrypted_token and getattr(settings, "ENABLE_LIVE_GITHUB_REVOCATION", True):
                try:
                    from app.core.crypto import decrypt_secret
                    from app.integrations.github.client import GitHubClient
                    token = decrypt_secret(gh_config.encrypted_token)
                    owner = gh_config.org_name
                    repo_full = resource.name
                    repo_short = repo_full.split("/")[-1] if "/" in repo_full else repo_full
                    with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as gh_client:
                        gh_client.update_repository_collaborator_permission(
                            org=owner, repo=repo_short, username=login_clean, permission=target_access
                        )
                    is_live_github = True
                    logger.info("Admin onboarded @%s on %s/%s to '%s'", login_clean, owner, repo_short, target_access)
                except Exception as exc:
                    logger.error("Live GitHub collaborator direct provisioning error for @%s: %s", login_clean, exc)

        # Assignment resolution & update
        assignment = (
            db.query(Assignment)
            .options(joinedload(Assignment.finding))
            .filter(
                Assignment.identity_id == identity.id,
                Assignment.resource_id == resource.id,
            )
            .with_for_update()
            .first()
        )

        before_access = assignment.access_level if assignment else "None"

        if not assignment:
            existing_ids = db.query(Assignment.id).all()
            max_num = 2840
            for (eid,) in existing_ids:
                if eid.startswith("FND-"):
                    try:
                        max_num = max(max_num, int(eid[4:]))
                    except ValueError:
                        pass
            new_id = f"FND-{max_num + 1}"

            assignment = Assignment(
                id=new_id,
                identity_id=identity.id,
                resource_id=resource.id,
                access_level=target_access,
                origin=("github" if (db.query(Setting).filter(Setting.key == "dataMode").first() and db.query(Setting).filter(Setting.key == "dataMode").first().value == "live") else ("github" if is_live_github else "sample")),
                github_login=login_clean,
                external_status="active",
                last_active_at=utc_now(),
                last_active_text="Onboarded by admin",
                resolved=target_access != "Admin",
                reviewed_at=reviewed_at_str,
                current_risk="High" if target_access == "Admin" else "Low",
                reason="Approved elevated access requires periodic review"
                if target_access == "Admin"
                else "Directly onboarded by admin",
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
                    "role": identity.job_role,
                    "team": identity.team,
                    "source": resource.source,
                    "lastActiveAt": utc_now().isoformat(),
                    "lastActivity": "Onboarded by admin",
                },
                evidence=eval_res.evidence,
            )
            db.add(finding)
        else:
            assignment.access_level = target_access
            assignment.external_status = "active"
            assignment.reviewed_at = reviewed_at_str
            if login_clean and not assignment.github_login:
                assignment.github_login = login_clean
            if target_access == "Admin" and before_access != "Admin":
                assignment.resolved = False
                assignment.current_risk = "High"
                if assignment.finding:
                    assignment.finding.status = "Open"
            elif target_access != "Admin":
                assignment.resolved = True
                if assignment.finding:
                    assignment.finding.status = "Approved change"

        expires_at = None
        if payload.duration_hours and payload.duration_hours > 0 and target_access != "None":
            from datetime import timedelta
            expires_at = utc_now() + timedelta(hours=payload.duration_hours)
            assignment.is_temporary = True
            assignment.expires_at = expires_at
            assignment.warning_email_sent_at = None
        else:
            assignment.is_temporary = False
            assignment.expires_at = None

        # Directly Approved AccessRequest record
        req = AccessRequest(
            id=req_id,
            identity_id=identity.id,
            resource_id=resource.id,
            requested_access=payload.access_level,
            type=payload.type or "Admin Onboarding / Direct Grant",
            duration_hours=payload.duration_hours,
            business_reason=payload.business_reason,
            risk="High" if target_access == "Admin" else "Low",
            status="Approved",
            requested_at=utc_now(),
            requested_text="Just now",
            decided_by=actor,
            decided_at=utc_now(),
            expires_at=expires_at,
        )
        db.add(req)

        # Audit log entry for direct grant
        event_id = f"EVT-{int(time.time() * 1000)}"
        log_entry = AuditLog(
            id=event_id,
            actor=actor,
            tag="Approved",
            title="Employee onboarded & access granted",
            detail=f"{identity.name} · {resource.name}{f' (Live GitHub: @{login_clean})' if is_live_github else ''}",
            note=payload.business_reason or "Direct admin onboarding & permission grant",
            source=resource.source,
            assignment_id=assignment.id,
            request_id=req_id,
            before=before_access,
            after=target_access,
            tone="green",
            icon="✓",
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
            label="Employee onboarded & access granted",
            high=high,
            medium=medium,
            healthy=healthy,
            resolved=resolved,
            assignments=len(assignments_all),
            remediated=remediated_count,
        )
        db.add(snapshot)

        # Dispatch security webhook alert
        try:
            from app.engine.webhook_service import send_security_webhook
            duration_label = f"{int(round(payload.duration_hours * 60))} Minutes (JIT)" if (payload.duration_hours and payload.duration_hours < 1) else (f"{int(payload.duration_hours)} Hours (JIT)" if payload.duration_hours else "Permanent")
            send_security_webhook(
                title="Employee Onboarded & Access Granted",
                description=f"Administrator **{actor}** directly onboarded **{identity.name}** and granted **{payload.access_level}** access on repository **{resource.name}**.",
                color_hex="#16a34a",
                fields=[
                    {"name": "Resource", "value": resource.name, "inline": True},
                    {"name": "User", "value": identity.name, "inline": True},
                    {"name": "GitHub Login", "value": f"@{login_clean}" if login_clean else "N/A", "inline": True},
                    {"name": "Permission", "value": payload.access_level, "inline": True},
                    {"name": "Duration", "value": duration_label, "inline": True},
                    {"name": "Admin Justification", "value": payload.business_reason or "Direct admin onboarding", "inline": False},
                ],
            )
        except Exception as exc:
            logger.warning("Could not dispatch webhook for direct admin onboarding: %s", exc)

        # Dispatch welcome/access granted email to user
        try:
            from app.engine.email_service import send_approval_decision_email_to_user
            recipient_email = identity.email
            if recipient_email and not recipient_email.endswith("@github.unmatched"):
                send_approval_decision_email_to_user(
                    to_email=recipient_email,
                    user_name=identity.name,
                    repo_name=resource.name,
                    action="Approved",
                    access_level=payload.access_level,
                    admin_name=actor,
                    admin_note=payload.business_reason,
                    business_reason=payload.business_reason,
                    github_login=login_clean,
                    duration_hours=payload.duration_hours,
                )
        except Exception as exc:
            logger.warning("Could not dispatch onboarding email to user: %s", exc)

        db.commit()
        db.refresh(req)

        # In-app broadcast notification for live UI updates
        try:
            from app.engine.notification_service import broadcast_notification
            broadcast_notification(
                db=db,
                event_type="approval_decided",
                title=f"Employee onboarded: {identity.name}",
                message=f"{identity.name} was granted {payload.access_level} access to {resource.name} directly by {actor}.",
                link="#people",
            )
        except Exception as exc:
            logger.warning("Could not dispatch onboarding in-app notification: %s", exc)

        return serialize_approval(req)

    # -------------------------------------------------------------------------
    # PUBLIC SELF-SERVICE REQUEST (Pending Review)
    # External requests wait in the approvals queue for administrator review
    # -------------------------------------------------------------------------
    req = AccessRequest(
        id=req_id,
        identity_id=identity.id,
        resource_id=resource.id,
        requested_access=payload.access_level,
        type=payload.type or "Self-service access request",
        duration_hours=payload.duration_hours,
        business_reason=payload.business_reason,
        risk=eval_res.risk_level,
        status="Pending",
        requested_at=utc_now(),
        requested_text="Just now",
    )
    db.add(req)

    # Dispatch security webhook alert for public request
    try:
        from app.engine.webhook_service import send_security_webhook
        duration_str = f"{int(round(payload.duration_hours * 60))} Minutes (JIT)" if (payload.duration_hours and payload.duration_hours < 1) else (f"{int(payload.duration_hours)} Hours (JIT)" if payload.duration_hours else "Permanent")
        send_security_webhook(
            title="New Public Access Request Submitted",
            description=f"External user **{identity.name}** requested **{payload.access_level}** access on **{resource.name}**.",
            color_hex="#3b82f6",
            fields=[
                {"name": "User", "value": identity.name, "inline": True},
                {"name": "GitHub Login", "value": f"@{login_clean}" if login_clean else "N/A", "inline": True},
                {"name": "Resource", "value": resource.name, "inline": True},
                {"name": "Permission", "value": payload.access_level, "inline": True},
                {"name": "Duration", "value": duration_str, "inline": True},
                {"name": "Business Justification", "value": payload.business_reason, "inline": False},
            ],
        )
    except Exception as exc:
        logger.warning("Could not dispatch webhook for public access request: %s", exc)

    event_id = f"EVT-{int(time.time() * 1000)}"
    log_entry = AuditLog(
        id=event_id,
        actor=actor,
        tag="Request",
        title="Public self-service access request submitted",
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
        user_tag = f"@{login_clean}" if login_clean else identity.name
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
    return _process_access_request(payload=payload, db=db, actor=user.name or user.email, is_public=False, current_user=user)


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
