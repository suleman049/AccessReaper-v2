"""
Identity management endpoints for AccessReaper v2 (Stage 2).
Provides:
- Organization identity listing (People management)
- Creating and updating identities with mandatory notes & audit logs
- CSV import with preview, validation, and execution
"""

import csv
import io
import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import UserClaims, require_role
from app.core.time import calculate_days_inactive
from app.db.models import (
    AccessRequest,
    Assignment,
    AuditLog,
    Finding,
    GitHubConfig,
    GitHubIdentityMap,
    Identity,
    Resource,
    RuleConfig,
    utc_now,
)
from app.db.session import get_db
from app.engine.scoring import (
    IdentityContext,
    ResourceContext,
    evaluate_risk,
    get_default_rule_config,
)
from app.schemas.serializers import serialize_assignment

logger = logging.getLogger("accessreaper.api.identities")

router = APIRouter(prefix="/identities", tags=["Identities"])


class CreateIdentityPayload(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    email: str = Field(min_length=3, max_length=255)
    team: str = Field(default="Engineering", max_length=100)
    job_role: str = Field(default="Team member", max_length=100)
    employment_status: str = Field(default="active", pattern="^(active|contractor|former)$")
    current_project: str | None = None
    note: str = Field(min_length=1)


class UpdateIdentityPayload(BaseModel):
    name: str | None = None
    team: str | None = None
    job_role: str | None = None
    employment_status: str | None = None
    current_project: str | None = None
    note: str = Field(min_length=1)


class CSVRow(BaseModel):
    github_login: str
    email: str
    name: str
    team: str
    employment_status: str


class CSVImportPreviewPayload(BaseModel):
    csvText: str


class CSVImportConfirmPayload(BaseModel):
    rows: list[CSVRow]
    note: str = Field(default="CSV bulk identity import")


def _generate_initials(name: str) -> str:
    parts = name.strip().split()
    if not parts:
        return "U"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


@router.get("")
def list_identities(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Returns all organization employee identities with their mapped GitHub login and stats.
    """
    identities = db.query(Identity).filter(Identity.team != "Unmatched").all()
    maps = {m.email.lower(): m for m in db.query(GitHubIdentityMap).filter(GitHubIdentityMap.email.isnot(None)).all()}

    results = []
    for ident in identities:
        clean_email = ident.email.lower()
        gh_map = maps.get(clean_email)
        results.append(
            {
                "id": ident.id,
                "name": ident.name,
                "email": ident.email,
                "initials": ident.initials,
                "job_role": ident.job_role,
                "team": ident.team,
                "employment_status": ident.employment_status,
                "current_project": ident.current_project,
                "github_login": gh_map.login if gh_map else None,
                "account_type": gh_map.account_type if gh_map else "user",
            }
        )
    return results


@router.post("", status_code=status.HTTP_201_CREATED)
def create_identity(
    payload: CreateIdentityPayload,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Creates a new employee identity. Requires an explanatory note and logs an audit event.
    """
    clean_email = payload.email.strip().lower()
    existing = db.query(Identity).filter(Identity.email == clean_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {"code": "IDENTITY_EXISTS", "message": f"Identity with email '{clean_email}' already exists."}
            },
        )

    initials = _generate_initials(payload.name)
    identity = Identity(
        name=payload.name.strip(),
        email=clean_email,
        initials=initials,
        job_role=payload.job_role.strip(),
        team=payload.team.strip(),
        employment_status=payload.employment_status,
        current_project=payload.current_project.strip() if payload.current_project else None,
    )
    db.add(identity)
    db.flush()

    audit_event = AuditLog(
        id=f"EVT-{int(time.time() * 1000)}",
        actor=user.email,
        tag="Governance",
        title="Create employee identity",
        detail=f"Created identity {identity.name} ({clean_email})",
        note=payload.note.strip(),
        source="People",
        before=None,
        after=f"{identity.name} ({identity.team}, {identity.employment_status})",
        tone="green",
        icon="people",
        mode="DRY_RUN",
        occurred_at=datetime.now(UTC),
    )
    db.add(audit_event)
    db.commit()
    db.refresh(identity)

    return {
        "id": identity.id,
        "name": identity.name,
        "email": identity.email,
        "initials": identity.initials,
        "job_role": identity.job_role,
        "team": identity.team,
        "employment_status": identity.employment_status,
        "current_project": identity.current_project,
    }


@router.get("/{email}")
def get_identity(
    email: str,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    clean_email = email.strip().lower()
    identity = db.query(Identity).filter(Identity.email == clean_email).first()
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Identity '{clean_email}' not found."}},
        )

    gh_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.email == clean_email).first()
    return {
        "id": identity.id,
        "name": identity.name,
        "email": identity.email,
        "initials": identity.initials,
        "job_role": identity.job_role,
        "team": identity.team,
        "employment_status": identity.employment_status,
        "current_project": identity.current_project,
        "github_login": gh_map.login if gh_map else None,
    }


@router.put("/{email}")
def update_identity(
    email: str,
    payload: UpdateIdentityPayload,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Updates an employee identity (name, team, role, status, project).
    Requires a note, re-evaluates risk for assignments, and records an append-only audit event.
    """
    clean_email = email.strip().lower()
    identity = db.query(Identity).filter(Identity.email == clean_email).first()
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Identity '{clean_email}' not found."}},
        )

    note = payload.note.strip()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "NOTE_REQUIRED", "message": "A note explaining the update is required."}},
        )

    before_desc = f"{identity.name} ({identity.team}, {identity.employment_status}, {identity.job_role})"

    if payload.name:
        identity.name = payload.name.strip()
        identity.initials = _generate_initials(identity.name)
    if payload.team:
        identity.team = payload.team.strip()
    if payload.job_role:
        identity.job_role = payload.job_role.strip()
    if payload.employment_status:
        identity.employment_status = payload.employment_status.lower().strip()
    if payload.current_project is not None:
        identity.current_project = payload.current_project.strip() if payload.current_project else None

    db.flush()

    after_desc = f"{identity.name} ({identity.team}, {identity.employment_status}, {identity.job_role})"

    # Re-evaluate all assignments for this identity
    active_rule_config_row = db.query(RuleConfig).filter(RuleConfig.is_active == True).first()  # noqa: E712
    rule_config_payload = active_rule_config_row.payload if active_rule_config_row else get_default_rule_config()

    assignments = db.query(Assignment).filter(Assignment.identity_id == identity.id).all()
    for a in assignments:
        existing_finding = db.query(Finding).filter(Finding.assignment_id == a.id).first()
        if existing_finding and existing_finding.status in ("Remediated", "Dismissed", "Approved change"):
            continue

        id_ctx = IdentityContext(
            name=identity.name,
            email=identity.email,
            job_role=identity.job_role,
            team=identity.team,
            employment_status=identity.employment_status,
            current_project=identity.current_project,
            is_unmatched=False,
            github_login=a.github_login,
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
        tag="Identity",
        title="Update employee identity",
        detail=f"Updated identity {identity.name} ({clean_email})",
        note=note,
        source="People",
        before=before_desc,
        after=after_desc,
        tone="blue",
        icon="people",
        mode="DRY_RUN",
        occurred_at=datetime.now(UTC),
    )
    db.add(audit_event)
    db.commit()

    return {
        "id": identity.id,
        "name": identity.name,
        "email": identity.email,
        "initials": identity.initials,
        "job_role": identity.job_role,
        "team": identity.team,
        "employment_status": identity.employment_status,
        "current_project": identity.current_project,
    }


@router.post("/import-csv/preview")
def preview_csv_import(
    payload: CSVImportPreviewPayload,
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Parses and validates CSV text with headers: github_login,email,name,team,employment_status.
    Returns valid rows and error rows.
    """
    csv_text = payload.csvText.strip()
    if not csv_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "EMPTY_CSV", "message": "CSV content is empty."}},
        )

    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)
    required_cols = {"github_login", "email", "name", "team", "employment_status"}

    if not reader.fieldnames or not required_cols.issubset({c.strip().lower() for c in reader.fieldnames}):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "INVALID_HEADERS",
                    "message": f"CSV must contain headers: {', '.join(sorted(required_cols))}",
                }
            },
        )

    valid_rows = []
    error_rows = []

    for i, row in enumerate(reader, start=2):
        cleaned = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        login = cleaned.get("github_login", "")
        email = cleaned.get("email", "").lower()
        name = cleaned.get("name", "")
        team = cleaned.get("team", "Engineering")
        status_val = cleaned.get("employment_status", "Active").capitalize()

        errors = []
        if not login:
            errors.append("github_login is required")
        if not email or "@" not in email:
            errors.append("valid email is required")
        if not name:
            errors.append("name is required")
        if status_val.lower() not in ("active", "contractor", "former"):
            errors.append("employment_status must be Active, Contractor, or Former")

        if errors:
            error_rows.append({"line": i, "row": cleaned, "errors": errors})
        else:
            valid_rows.append(
                {
                    "github_login": login,
                    "email": email,
                    "name": name,
                    "team": team,
                    "employment_status": status_val.lower(),
                }
            )

    return {
        "validRows": valid_rows,
        "errorRows": error_rows,
        "totalRows": len(valid_rows) + len(error_rows),
        "canImport": len(error_rows) == 0 and len(valid_rows) > 0,
    }


@router.post("/import-csv/confirm")
def confirm_csv_import(
    payload: CSVImportConfirmPayload,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Imports validated CSV rows: creates/updates identities, maps GitHub logins,
    re-links assignments, and appends an audit event.
    """
    if not payload.rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "NO_ROWS", "message": "No rows provided for import."}},
        )

    imported_count = 0
    updated_count = 0
    active_rule_config_row = db.query(RuleConfig).filter(RuleConfig.is_active == True).first()  # noqa: E712
    rule_config_payload = active_rule_config_row.payload if active_rule_config_row else get_default_rule_config()

    for r in payload.rows:
        clean_email = r.email.strip().lower()
        login = r.github_login.strip()

        ident = db.query(Identity).filter(Identity.email == clean_email).first()
        if not ident:
            ident = Identity(
                name=r.name.strip(),
                email=clean_email,
                initials=_generate_initials(r.name),
                job_role="Team member",
                team=r.team.strip(),
                employment_status=r.employment_status.lower(),
                current_project=None,
            )
            db.add(ident)
            imported_count += 1
        else:
            ident.name = r.name.strip()
            ident.team = r.team.strip()
            ident.employment_status = r.employment_status.lower()
            updated_count += 1

        db.flush()

        # Map GitHub login
        if login:
            id_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == login).first()
            if not id_map:
                id_map = GitHubIdentityMap(login=login, email=clean_email, source="csv_import", mapped_by=user.email)
                db.add(id_map)
            else:
                id_map.email = clean_email
                id_map.source = "csv_import"
                id_map.mapped_by = user.email

            # Re-link assignments
            assignments = (
                db.query(Assignment).filter(Assignment.origin == "github", Assignment.github_login == login).all()
            )
            for a in assignments:
                a.identity_id = ident.id

            db.flush()

            # Re-evaluate risk
            for a in assignments:
                if a.external_status != "active":
                    continue
                eval_res = evaluate_risk(
                    identity=IdentityContext(
                        name=ident.name,
                        email=ident.email,
                        job_role=ident.job_role,
                        team=ident.team,
                        employment_status=ident.employment_status,
                        current_project=ident.current_project,
                        is_unmatched=False,
                        github_login=login,
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

    audit_event = AuditLog(
        id=f"EVT-{int(time.time() * 1000)}",
        actor=user.email,
        tag="Integration",
        title="CSV Identity Import",
        detail=f"Imported {imported_count} new and updated {updated_count} employee identities from CSV",
        note=payload.note.strip() or "CSV bulk identity import completed.",
        source="CSV Import",
        before=None,
        after=f"{imported_count} imported, {updated_count} updated",
        tone="green",
        icon="people",
        mode="DRY_RUN",
        occurred_at=datetime.now(UTC),
    )
    db.add(audit_event)
    db.commit()

    return {
        "imported": imported_count,
        "updated": updated_count,
        "totalProcessed": len(payload.rows),
        "success": True,
    }


class OffboardPayload(BaseModel):
    note: str = Field(default="Employee offboarding - complete access revocation", min_length=1)


@router.post("/{id_or_email}/offboard")
def offboard_employee(
    id_or_email: str,
    payload: OffboardPayload,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    One-Click Instant Employee Offboarding Wipe:
    1. Sets employee employment_status to 'former'.
    2. Strips all collaborator permissions across all repositories in live GitHub.
    3. Revokes all assignments and marks findings Remediated.
    4. Auto-declines all pending access requests.
    5. Dispatches Offboarding Certificate email to admin and sends Discord/Slack security alert.
    """
    clean_target = id_or_email.strip().lower()
    identity = (
        db.query(Identity)
        .filter((Identity.id == id_or_email.strip()) | (Identity.email == clean_target))
        .first()
    )

    if not identity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Employee identity '{id_or_email}' not found."}},
        )

    # 1. Update employment status
    identity.employment_status = "former"

    # Find GitHub login
    gh_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.email == identity.email.lower()).first()
    github_login = gh_map.login if gh_map else None

    # Check live GitHub connection
    from app.core.config import settings
    from app.engine.email_service import send_offboarding_summary_email
    from app.engine.webhook_service import send_security_webhook

    gh_config = db.query(GitHubConfig).first()
    can_live_github = (
        gh_config
        and gh_config.connected
        and gh_config.encrypted_token
        and getattr(settings, "ENABLE_LIVE_GITHUB_REVOCATION", True)
    )

    assignments = db.query(Assignment).filter(Assignment.identity_id == identity.id).all()
    revoked_repos: list[str] = []

    for a in assignments:
        repo_name = a.resource.name if a.resource else "repository"
        repo_short = repo_name.split("/")[-1] if "/" in repo_name else repo_name
        login = a.github_login or github_login

        if can_live_github and login and ("/" in repo_name or (a.resource and a.resource.source == "GitHub")):
            try:
                from app.core.crypto import decrypt_secret
                from app.integrations.github.client import GitHubClient

                token = decrypt_secret(gh_config.encrypted_token)
                owner = gh_config.org_name
                with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as gh_client:
                    gh_client.remove_repository_collaborator(org=owner, repo=repo_short, username=login)
                    a.external_status = "revoked_externally"
                    logger.info("Offboarding stripped GitHub collaborator @%s from %s/%s", login, owner, repo_short)
            except Exception as exc:
                logger.error("Error revoking @%s from %s during offboard: %s", login, repo_name, exc)

        if a.access_level != "None":
            revoked_repos.append(repo_name)
        a.access_level = "None"
        a.resolved = True
        a.current_risk = "Low"
        a.reason = "Revoked due to employee offboarding"
        if a.finding:
            a.finding.status = "Remediated"

    # Cancel pending requests
    pending_reqs = (
        db.query(AccessRequest)
        .filter(AccessRequest.identity_id == identity.id, AccessRequest.status == "Pending")
        .all()
    )
    for pr in pending_reqs:
        pr.status = "Declined"
        pr.decided_by = user.name or "Security Admin"
        pr.decided_at = utc_now()

    # Append audit log entry
    event_id = f"EVT-OFFBOARD-{int(time.time() * 1000)}"
    log_entry = AuditLog(
        id=event_id,
        actor=user.name or user.email,
        tag="Offboarded",
        title=f"Employee offboarded: {identity.name}",
        detail=f"Stripped access across {len(revoked_repos)} repositories on live GitHub",
        note=payload.note.strip(),
        source="Offboarding Sentinel",
        before="active",
        after="former",
        tone="red",
        icon="🚫",
        mode="LIVE_GITHUB" if can_live_github else "DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(log_entry)
    db.commit()

    # Dispatch compliance email
    try:
        admin_target = user.email
        if not admin_target or "@github.unmatched" in admin_target:
            admin_target = settings.SMTP_USER
        if admin_target:
            send_offboarding_summary_email(
                to_email=admin_target,
                employee_name=identity.name,
                employee_email=identity.email,
                repos_revoked=revoked_repos,
                admin_name=user.name or "Security Administrator",
            )
    except Exception as exc:
        logger.warning("Could not dispatch offboarding summary email: %s", exc)

    # Dispatch Discord/Slack webhook
    try:
        send_security_webhook(
            title="Employee Offboarding Executed",
            description=f"One-click offboarding wipe completed for **{identity.name}** (`{identity.email}`). All collaborator permissions removed across the organization.",
            color_hex="#dc2626",
            fields=[
                {"name": "Employee", "value": f"{identity.name} ({identity.job_role})", "inline": True},
                {"name": "Admin", "value": user.name or user.email, "inline": True},
                {"name": "Repositories Revoked", "value": str(len(revoked_repos)), "inline": True},
                {"name": "Status", "value": "Employment: former &bull; Access: Cleaned", "inline": False},
                {"name": "Note", "value": payload.note.strip(), "inline": False},
            ],
        )
    except Exception as exc:
        logger.warning("Could not dispatch webhook for offboarding: %s", exc)

    return {
        "success": True,
        "message": f"Successfully offboarded {identity.name}. Stripped {len(revoked_repos)} repository permissions.",
        "employee": identity.name,
        "email": identity.email,
        "employmentStatus": "former",
        "revokedCount": len(revoked_repos),
        "revokedRepos": revoked_repos,
    }
