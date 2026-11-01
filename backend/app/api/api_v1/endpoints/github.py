"""
GitHub IAM integration management endpoints.
All routes require Admin privileges.
Prefix: /api/integrations/github
"""

import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.security import UserClaims, require_role
from app.core.time import calculate_days_inactive
from app.db.models import (
    Assignment,
    AuditLog,
    Finding,
    GitHubConfig,
    GitHubIdentityMap,
    Identity,
    RuleConfig,
    Setting,
    SyncRun,
)
from app.db.session import get_db
from app.engine.scoring import (
    IdentityContext,
    ResourceContext,
    evaluate_risk,
    get_default_rule_config,
)
from app.integrations.github.client import (
    GitHubAuthError,
    GitHubClient,
    GitHubForbiddenError,
    GitHubIntegrationError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubSSORequiredError,
)
from app.integrations.github.sync import run_github_sync
from app.schemas.github import (
    AutoSuggestItem,
    BulkMapPayload,
    ClassificationPayload,
    DataModePayload,
    GitHubConfigPayload,
    GitHubMapPayload,
    GitHubStatusResponse,
    GitHubSyncRunSummary,
    GitHubTestPayload,
    GitHubTestResponse,
    GitHubUnmatchedItem,
)
from app.schemas.serializers import serialize_assignment

logger = logging.getLogger("accessreaper.api.github")

router = APIRouter(prefix="/integrations/github", tags=["GitHub Integration"])


def _get_data_mode(db: Session) -> str:
    setting = db.query(Setting).filter(Setting.key == "dataMode").first()
    return setting.value if setting and setting.value in ("sample", "live") else "sample"


@router.get("/status", response_model=GitHubStatusResponse)
def get_github_status(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Returns connection status, configured org, masked token, last sync metadata, and data mode.
    """
    config = db.query(GitHubConfig).first()
    data_mode = _get_data_mode(db)

    if not config or not config.connected:
        return GitHubStatusResponse(
            connected=False,
            org_name=config.org_name if config else None,
            token_last4=None,
            scopes=[],
            last_sync=None,
            sync_before_audit=config.sync_before_audit if config else False,
            data_mode=data_mode,
        )

    last_sync_record = db.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    last_sync_summary = None
    if last_sync_record:
        last_sync_summary = GitHubSyncRunSummary(
            id=last_sync_record.id,
            started_at=last_sync_record.started_at,
            finished_at=last_sync_record.finished_at,
            status=last_sync_record.status,
            request_count=last_sync_record.request_count,
            repos_count=last_sync_record.repos_count,
            members_count=last_sync_record.members_count,
            collaborators_count=last_sync_record.collaborators_count,
            assignments_created=last_sync_record.assignments_created,
            assignments_updated=last_sync_record.assignments_updated,
            assignments_revoked=last_sync_record.assignments_revoked,
            error_summary=last_sync_record.error_summary,
        )

    return GitHubStatusResponse(
        connected=config.connected,
        org_name=config.org_name,
        token_last4=config.token_last4,
        scopes=["read:org", "repo"],
        last_sync=last_sync_summary,
        sync_before_audit=config.sync_before_audit,
        data_mode=data_mode,
    )


@router.put("/config", response_model=GitHubStatusResponse)
def configure_github(
    payload: GitHubConfigPayload,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Validates token and org with GitHub, encrypts token at rest, updates config, and writes audit event.
    """
    org = payload.org.strip()
    token = payload.token.strip()

    # 1. Validate connection before saving
    try:
        with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as client:
            client.test_connection(org)
    except GitHubAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except GitHubNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Organization '{org}' not found.")
    except GitHubSSORequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except GitHubForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission denied for org '{org}': {exc}")
    except GitHubRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
    except GitHubIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    encrypted = encrypt_secret(token)
    token_last4 = token[-4:] if len(token) >= 4 else token

    config = db.query(GitHubConfig).first()
    if not config:
        config = GitHubConfig(id=1)
        db.add(config)

    before_org = config.org_name

    config.org_name = org
    config.encrypted_token = encrypted
    config.token_last4 = token_last4
    config.connected = True
    if payload.sync_before_audit is not None:
        config.sync_before_audit = payload.sync_before_audit

    audit_event = AuditLog(
        id=f"EVT-{int(time.time() * 1000)}",
        actor=user.email,
        tag="Integration",
        title="Configure GitHub integration",
        detail=f"Configured integration for org '{org}'",
        note=f"Configured GitHub integration for organization '{org}' (token ending in ...{token_last4}).",
        source="GitHub",
        before=before_org,
        after=org,
        tone="blue",
        icon="repo",
        mode="DRY_RUN",
        occurred_at=datetime.now(UTC),
    )
    db.add(audit_event)
    db.commit()

    # Trigger immediate automated background sync on connection
    try:
        from app.core.scheduler import trigger_background_github_sync

        trigger_background_github_sync(actor=user.email, trigger="connect")
    except Exception as sync_exc:
        logger.warning("Could not spawn background sync thread: %s", sync_exc)

    return get_github_status(db=db, user=user)


@router.delete("/config", response_model=GitHubStatusResponse)
def disconnect_github(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Disconnects GitHub integration (removes token). Preserves existing imported data.
    """
    config = db.query(GitHubConfig).first()
    if not config or not config.connected:
        return get_github_status(db=db, user=user)

    before_org = config.org_name

    config.connected = False
    config.encrypted_token = None
    config.token_last4 = None

    audit_event = AuditLog(
        id=f"EVT-{int(time.time() * 1000)}",
        actor=user.email,
        tag="Integration",
        title="Disconnect GitHub integration",
        detail=f"Disconnected integration for org '{before_org}'",
        note=f"Disconnected GitHub integration for organization '{before_org}'.",
        source="GitHub",
        before=before_org,
        after=None,
        tone="gray",
        icon="repo",
        mode="DRY_RUN",
        occurred_at=datetime.now(UTC),
    )
    db.add(audit_event)
    db.commit()

    return get_github_status(db=db, user=user)


@router.post("/test", response_model=GitHubTestResponse)
def test_github_connection(
    payload: GitHubTestPayload | None = None,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Tests GitHub connection using provided or stored credentials.
    """
    config = db.query(GitHubConfig).first()
    org = payload.org if payload and payload.org else (config.org_name if config else None)
    token = None

    if payload and payload.token:
        token = payload.token
    elif config and config.encrypted_token:
        try:
            token = decrypt_secret(config.encrypted_token)
        except Exception:
            return GitHubTestResponse(ok=False, message="Corrupted secret token stored on server.")

    if not org or not token:
        return GitHubTestResponse(ok=False, message="Missing organization or token.")

    try:
        with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as client:
            res = client.test_connection(org)
            return GitHubTestResponse(
                ok=True,
                message=f"Successfully connected to organization '{res.get('org')}' as @{res.get('user')}.",
                user=res.get("user"),
                org=res.get("org"),
                scopes=res.get("scopes", []),
            )
    except GitHubAuthError:
        return GitHubTestResponse(ok=False, message="Bad credentials: The provided token is invalid or expired.")
    except GitHubNotFoundError:
        return GitHubTestResponse(ok=False, message=f"Organization '{org}' not found, or token lacks read access.")
    except GitHubSSORequiredError:
        return GitHubTestResponse(
            ok=False, message=f"Organization '{org}' requires SAML/SSO authorization for this token."
        )
    except GitHubForbiddenError as e:
        return GitHubTestResponse(ok=False, message=f"Permission denied: {e}")
    except GitHubRateLimitError as e:
        return GitHubTestResponse(ok=False, message=f"Rate limit exceeded: {e}")
    except GitHubIntegrationError as e:
        return GitHubTestResponse(ok=False, message=f"Integration error: {e}")


@router.post("/sync", response_model=GitHubSyncRunSummary)
def trigger_github_sync(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Executes synchronization of GitHub members, teams, repos, and collaborators.
    """
    try:
        run = run_github_sync(db, actor_email=user.email, trigger="manual")
        return GitHubSyncRunSummary(
            id=run.id,
            started_at=run.started_at,
            finished_at=run.finished_at,
            status=run.status,
            request_count=run.request_count,
            repos_count=run.repos_count,
            members_count=run.members_count,
            collaborators_count=run.collaborators_count,
            assignments_created=run.assignments_created,
            assignments_updated=run.assignments_updated,
            assignments_revoked=run.assignments_revoked,
            error_summary=run.error_summary,
        )
    except GitHubIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/unmatched", response_model=list[GitHubUnmatchedItem])
def get_unmatched_accounts(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Returns GitHub logins not mapped to any organization employee.
    """
    unmatched_maps = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.email.is_(None)).all()
    results: list[GitHubUnmatchedItem] = []

    for item in unmatched_maps:
        login = item.login
        assignments = (
            db.query(Assignment)
            .filter(
                Assignment.origin == "github",
                Assignment.github_login == login,
                Assignment.external_status == "active",
            )
            .all()
        )

        highest_risk = "Low"
        for a in assignments:
            if a.current_risk == "High":
                highest_risk = "High"
                break
            elif a.current_risk == "Medium" and highest_risk != "High":
                highest_risk = "Medium"

        results.append(
            GitHubUnmatchedItem(
                login=login,
                name=login,
                assignments_count=len(assignments),
                highest_risk=highest_risk,
                account_type=item.account_type,
                note=item.note,
                assignments=[
                    {
                        "id": a.id,
                        "resource": a.resource.name,
                        "access_level": a.access_level,
                        "risk": a.current_risk,
                    }
                    for a in assignments
                ],
            )
        )

    return results


@router.put("/map/{login}")
def map_github_account(
    login: str,
    payload: GitHubMapPayload,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Links a GitHub login to an employee email, updates assignments, re-evaluates risk, and writes audit event.
    """
    target_email = payload.email.strip().lower()
    employee = db.query(Identity).filter(Identity.email == target_email).first()
    if not employee:
        # Automatically create the employee identity for this manually entered email
        employee = Identity(
            name=login.replace("-", " ").replace("_", " ").title(),
            email=target_email,
            initials=login[:2].upper(),
            job_role="Engineer",
            team="Engineering",
            employment_status="active",
        )
        db.add(employee)
        db.flush()

    id_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == login).first()
    old_email = id_map.email if id_map else None

    if not id_map:
        id_map = GitHubIdentityMap(login=login, email=target_email, source="manual", mapped_by=user.email)
        db.add(id_map)
    else:
        id_map.email = target_email
        id_map.source = "manual"
        id_map.mapped_by = user.email
        id_map.mapped_at = datetime.now(UTC)

    # Re-link existing GitHub assignments for this login
    assignments = db.query(Assignment).filter(Assignment.origin == "github", Assignment.github_login == login).all()
    for a in assignments:
        a.identity_id = employee.id

    db.flush()

    # Re-evaluate risk on these assignments
    active_rule_config_row = db.query(RuleConfig).filter(RuleConfig.is_active == True).first()  # noqa: E712
    rule_config_payload = active_rule_config_row.payload if active_rule_config_row else get_default_rule_config()

    for a in assignments:
        if a.external_status != "active":
            continue

        existing_finding = db.query(Finding).filter(Finding.assignment_id == a.id).first()
        if existing_finding and existing_finding.status in ("Remediated", "Dismissed", "Approved change"):
            continue

        id_ctx = IdentityContext(
            name=employee.name,
            email=employee.email,
            job_role=employee.job_role,
            team=employee.team,
            employment_status=employee.employment_status,
            current_project=employee.current_project,
            is_unmatched=False,
            github_login=login,
        )
        res_ctx = ResourceContext(
            name=a.resource.name,
            source=a.resource.source,
            is_sensitive=a.resource.is_sensitive,
            project=a.resource.project,
        )
        last_active_days = calculate_days_inactive(a.last_active_at)

        eval_res = evaluate_risk(
            identity=id_ctx,
            resource=res_ctx,
            access_level=a.access_level,
            last_active_days=last_active_days,
            last_activity_text=a.last_active_text or "no recorded activity found",
            resolved=a.resolved,
            finding_status=existing_finding.status if existing_finding else "Open",
            rule_config=rule_config_payload,
        )

        a.current_risk = eval_res.risk_level
        a.reason = eval_res.primary_reason

        snapshot = serialize_assignment(a).model_dump(by_alias=True)
        if existing_finding:
            existing_finding.original_reason = eval_res.primary_reason
            existing_finding.original_severity = eval_res.risk_level
            existing_finding.evidence = eval_res.evidence
            existing_finding.status = "Healthy" if eval_res.risk_level == "Low" else "Open"
            existing_finding.snapshot = snapshot

    audit_event = AuditLog(
        id=f"EVT-{int(time.time() * 1000)}",
        actor=user.email,
        tag="Integration",
        title="Map GitHub account",
        detail=f"Mapped GitHub login @{login} to {target_email}",
        note=f"Mapped GitHub login @{login} to {target_email} ({len(assignments)} assignments updated).",
        source="GitHub",
        before=old_email,
        after=target_email,
        tone="blue",
        icon="people",
        mode="DRY_RUN",
        occurred_at=datetime.now(UTC),
    )
    db.add(audit_event)
    db.commit()

    return {"ok": True, "login": login, "email": target_email, "updated_assignments": len(assignments)}


@router.get("/mode")
def get_data_mode(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """Returns the current data mode (sample | live)."""
    return {"data_mode": _get_data_mode(db)}


@router.put("/mode")
def set_data_mode(
    payload: DataModePayload,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Switches workspace data mode between 'sample' and 'live'.
    Writes an audit event.
    """
    mode = payload.data_mode
    setting = db.query(Setting).filter(Setting.key == "dataMode").first()
    old_mode = setting.value if setting else "sample"

    if not setting:
        setting = Setting(key="dataMode", value=mode)
        db.add(setting)
    else:
        setting.value = mode

    audit_event = AuditLog(
        id=f"EVT-{int(time.time() * 1000)}",
        actor=user.email,
        tag="Workspace",
        title="Switch data mode",
        detail=f"Switched data mode from '{old_mode}' to '{mode}'",
        note=f"Switched data mode from '{old_mode}' to '{mode}'.",
        source="Workspace",
        before=old_mode,
        after=mode,
        tone="blue",
        icon="settings",
        mode="DRY_RUN",
        occurred_at=datetime.now(UTC),
    )
    db.add(audit_event)
    db.commit()

    if mode == "live":
        try:
            from app.core.scheduler import trigger_background_github_sync

            trigger_background_github_sync(actor=user.email, trigger="mode_switch")
        except Exception as sync_exc:
            logger.warning("Could not spawn background sync thread on mode switch: %s", sync_exc)

    return {"data_mode": mode}


@router.post("/bulk-map")
def bulk_map_github_accounts(
    payload: BulkMapPayload,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Bulk maps multiple GitHub logins to employee emails in a single database transaction.
    Records an append-only audit log event for each mapped link.
    """
    mapped_count = 0
    active_rule_config_row = db.query(RuleConfig).filter(RuleConfig.is_active == True).first()  # noqa: E712
    rule_config_payload = active_rule_config_row.payload if active_rule_config_row else get_default_rule_config()

    for item in payload.mappings:
        login = item.login.strip()
        target_email = item.email.strip().lower()
        if not login or not target_email:
            continue

        employee = db.query(Identity).filter(Identity.email == target_email).first()
        if not employee:
            continue

        id_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == login).first()
        old_email = id_map.email if id_map else None

        if not id_map:
            id_map = GitHubIdentityMap(login=login, email=target_email, source="manual", mapped_by=user.email)
            db.add(id_map)
        else:
            id_map.email = target_email
            id_map.source = "manual"
            id_map.mapped_by = user.email
            id_map.mapped_at = datetime.now(UTC)

        assignments = db.query(Assignment).filter(Assignment.origin == "github", Assignment.github_login == login).all()
        for a in assignments:
            a.identity_id = employee.id

        db.flush()

        for a in assignments:
            if a.external_status != "active":
                continue
            existing_finding = db.query(Finding).filter(Finding.assignment_id == a.id).first()
            if existing_finding and existing_finding.status in ("Remediated", "Dismissed", "Approved change"):
                continue

            id_ctx = IdentityContext(
                name=employee.name,
                email=employee.email,
                job_role=employee.job_role,
                team=employee.team,
                employment_status=employee.employment_status,
                current_project=employee.current_project,
                is_unmatched=False,
                github_login=login,
                account_type=id_map.account_type,
            )
            res_ctx = ResourceContext(
                name=a.resource.name,
                source=a.resource.source,
                is_sensitive=a.resource.is_sensitive,
                project=a.resource.project,
            )
            last_active_days = calculate_days_inactive(a.last_active_at)

            eval_res = evaluate_risk(
                identity=id_ctx,
                resource=res_ctx,
                access_level=a.access_level,
                last_active_days=last_active_days,
                last_activity_text=a.last_active_text or "no recorded activity found",
                resolved=a.resolved,
                finding_status=existing_finding.status if existing_finding else "Open",
                rule_config=rule_config_payload,
            )

            a.current_risk = eval_res.risk_level
            a.reason = eval_res.primary_reason

            snapshot = serialize_assignment(a).model_dump(by_alias=True)
            if existing_finding:
                existing_finding.original_reason = eval_res.primary_reason
                existing_finding.original_severity = eval_res.risk_level
                existing_finding.evidence = eval_res.evidence
                existing_finding.status = "Healthy" if eval_res.risk_level == "Low" else "Open"
                existing_finding.snapshot = snapshot

        audit_event = AuditLog(
            id=f"EVT-{int(time.time() * 1000)}-{mapped_count}",
            actor=user.email,
            tag="Integration",
            title="Map GitHub account",
            detail=f"Bulk-mapped GitHub login @{login} to {target_email}",
            note=f"Bulk identity linking: @{login} mapped to {target_email}.",
            source="GitHub",
            before=old_email,
            after=target_email,
            tone="green",
            icon="link",
            mode="DRY_RUN",
            occurred_at=datetime.now(UTC),
        )
        db.add(audit_event)
        mapped_count += 1

    db.commit()
    return {"mappedCount": mapped_count, "success": True}


@router.get("/auto-suggest", response_model=list[AutoSuggestItem])
def get_mapping_auto_suggestions(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Computes suggestions matching unlinked GitHub logins to organization employee identities
    by username exact match and display name similarity.
    Never auto-applied; returned as suggestions the admin confirms.
    """
    unmatched_maps = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.email.is_(None)).all()
    identities = db.query(Identity).filter(Identity.team != "Unmatched").all()

    suggestions = []
    for m in unmatched_maps:
        login_clean = m.login.lower().strip()
        best_match = None
        best_score = 0.0

        for ident in identities:
            email_user = ident.email.split("@")[0].lower().strip()
            name_parts = [p.lower() for p in ident.name.split()]

            # 1. Exact match with email local-part: score 1.0
            if login_clean == email_user:
                score = 1.0
            # 2. Email user starts with login or login starts with email user: score 0.85
            elif login_clean.startswith(email_user) or email_user.startswith(login_clean):
                score = 0.85
            # 3. Login matches name parts: score 0.75
            elif any(part in login_clean or login_clean in part for part in name_parts if len(part) > 2):
                score = 0.75
            # 4. Partial substring: score 0.5
            elif len(login_clean) >= 4 and (
                login_clean in ident.email.lower() or ident.email.split("@")[0].lower() in login_clean
            ):
                score = 0.5
            else:
                score = 0.0

            if score > best_score:
                best_score = score
                best_match = ident

        if best_match and best_score >= 0.5:
            suggestions.append(
                AutoSuggestItem(
                    login=m.login,
                    suggestedEmail=best_match.email,
                    suggestedName=best_match.name,
                    confidence=best_score,
                )
            )

    return suggestions


@router.put("/accounts/{login}/classification")
def classify_github_account(
    login: str,
    payload: ClassificationPayload,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Classifies a GitHub login as bot, service, ignored (accepted risk), or standard user.
    A note is required for non-user classifications.
    Excludes the account from unmatched findings while keeping it visible and audited.
    """
    id_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == login).first()
    if not id_map:
        id_map = GitHubIdentityMap(login=login, email=None, source="manual", mapped_by=user.email)
        db.add(id_map)

    account_type = payload.accountType
    note = (payload.note or "").strip()

    if account_type in ("bot", "service", "ignored") and not note:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "NOTE_REQUIRED",
                    "message": f"A note explaining the reason for classifying @{login} as '{account_type}' is required.",
                }
            },
        )

    old_type = id_map.account_type
    id_map.account_type = account_type
    id_map.note = note
    db.flush()

    # Re-evaluate all assignments for this login
    assignments = db.query(Assignment).filter(Assignment.origin == "github", Assignment.github_login == login).all()
    active_rule_config_row = db.query(RuleConfig).filter(RuleConfig.is_active == True).first()  # noqa: E712
    rule_config_payload = active_rule_config_row.payload if active_rule_config_row else get_default_rule_config()

    for a in assignments:
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
                github_login=login,
                account_type=account_type,
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
            resolved=a.resolved,
            rule_config=rule_config_payload,
        )
        a.current_risk = eval_res.risk_level
        a.reason = eval_res.primary_reason

        existing_finding = db.query(Finding).filter(Finding.assignment_id == a.id).first()
        if existing_finding:
            existing_finding.original_reason = eval_res.primary_reason
            existing_finding.original_severity = eval_res.risk_level
            existing_finding.evidence = eval_res.evidence
            existing_finding.status = "Healthy" if eval_res.risk_level == "Low" else "Open"

    audit_event = AuditLog(
        id=f"EVT-{int(time.time() * 1000)}",
        actor=user.email,
        tag="Governance",
        title=f"GitHub account classified as {account_type}",
        detail=f"Classified GitHub login @{login} as '{account_type}'",
        note=note or f"Account @{login} classification set to {account_type}",
        source="GitHub",
        before=old_type,
        after=account_type,
        tone="gray",
        icon="tag",
        mode="DRY_RUN",
        occurred_at=datetime.now(UTC),
    )
    db.add(audit_event)
    db.commit()

    return {"login": login, "accountType": account_type, "note": note, "updatedAssignments": len(assignments)}
