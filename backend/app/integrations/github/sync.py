"""
GitHub Synchronization Engine for AccessReaper v2.

Responsibilities:
1. Orchestrates read-only synchronization of GitHub organization members, teams, repositories, and collaborators.
2. Performs permission translation (admin -> Admin, maintain/push -> Write, triage/pull -> Read).
3. Resolves employee identities via `github_identity_map` or auto-detection.
4. Identifies unmatched GitHub accounts and flags them.
5. Captures commit activity for elevated accounts while respecting the request cap.
6. Implements idempotent updates:
   - Updates assignments in place.
   - Marks disappeared assignments as `revoked_externally` (preserving audit history).
7. Evaluates risk using `app.engine.scoring` without overwriting reviewed findings.
8. Writes an append-only audit log entry and creates a `SyncRun` record.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt_secret
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
    SyncRun,
)
from app.engine.scoring import (
    FindingContext,
    IdentityContext,
    ResourceContext,
    evaluate_risk,
    get_default_rule_config,
)
from app.integrations.github.client import (
    GitHubClient,
    GitHubIntegrationError,
    RequestCapExceededError,
)
from app.integrations.github.mapping import map_github_permission
from app.schemas.serializers import serialize_assignment

logger = logging.getLogger("accessreaper.github.sync")



def _normalize_utc(dt: datetime | None) -> datetime | None:
    """Guarantees a datetime is comparable against UTC-aware datetimes."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def _get_next_assignment_id(db: Session) -> str:
    """Finds the highest numeric FND-XXXX id and increments it."""
    assignments = db.query(Assignment.id).all()
    max_num = 2850
    for (a_id,) in assignments:
        match = re.search(r"FND-(\d+)", a_id)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"FND-{max_num + 1}"


def run_github_sync(
    db: Session,
    actor_email: str = "system",
    trigger: str = "manual",
) -> SyncRun:
    """
    Executes synchronization against the configured GitHub organization.
    Safe, idempotent, and read-only.
    """
    config = db.query(GitHubConfig).first()
    if not config or not config.connected or not config.encrypted_token or not config.org_name:
        raise GitHubIntegrationError("GitHub integration is not connected. Configure an org and token first.")

    token = decrypt_secret(config.encrypted_token)
    org_name = config.org_name

    now = datetime.now(UTC)
    sync_id = f"SYNC-{now.strftime('%Y%m%d')}-{int(time.time() * 1000) % 1000000:06d}"
    sync_run = SyncRun(
        id=sync_id,
        started_at=now,
        status="running",
        request_count=0,
        repos_count=0,
        members_count=0,
        collaborators_count=0,
        assignments_created=0,
        assignments_updated=0,
        assignments_revoked=0,
    )
    db.add(sync_run)
    db.commit()

    is_partial = False
    error_summary: str | None = None

    try:
        with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as client:
            # 1. Fetch organization members & outside collaborators
            logger.info("Fetching members and collaborators for GitHub org '%s'...", org_name)
            try:
                members = client.get_org_members(org_name)
            except RequestCapExceededError:
                is_partial = True
                members = []

            try:
                outside = client.get_outside_collaborators(org_name)
            except (RequestCapExceededError, GitHubIntegrationError):
                outside = []

            all_users_map: dict[str, dict[str, Any]] = {}
            for m in members:
                all_users_map[m["login"]] = m
            for o in outside:
                all_users_map[o["login"]] = o

            sync_run.members_count = len(members)
            sync_run.collaborators_count = len(outside)

            # 2. Map identities (auto-match by public email, commit, or link to placeholder)
            logger.info("Resolving identities for %d GitHub accounts...", len(all_users_map))
            login_to_identity: dict[str, Identity] = {}

            for login, user_meta in all_users_map.items():
                id_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == login).first()
                if id_map and id_map.email:
                    matched_id = db.query(Identity).filter(Identity.email == id_map.email).first()
                    if matched_id:
                        login_to_identity[login] = matched_id
                        continue

                # Not yet mapped: fetch user profile for public email
                public_email = user_meta.get("email")
                if not public_email:
                    try:
                        profile = client.get_user_profile(login)
                        public_email = profile.get("email")
                    except Exception:
                        public_email = None

                matched_employee = None
                if public_email:
                    matched_employee = db.query(Identity).filter(Identity.email == public_email.lower()).first()
                    if not matched_employee:
                        # Auto-feed newly discovered employee identity from GitHub public metadata
                        matched_employee = Identity(
                            name=user_meta.get("name") or login.replace("-", " ").replace("_", " ").title(),
                            email=public_email.lower(),
                            initials=login[:2].upper(),
                            job_role="Engineer",
                            team="Engineering",
                            employment_status="active",
                        )
                        db.add(matched_employee)
                        db.flush()

                if matched_employee:
                    # Auto-mapped
                    if not id_map:
                        id_map = GitHubIdentityMap(login=login, email=matched_employee.email, source="auto")
                        db.add(id_map)
                    else:
                        id_map.email = matched_employee.email
                    login_to_identity[login] = matched_employee
                else:
                    # Unmatched account: create or retrieve placeholder Identity
                    if not id_map:
                        id_map = GitHubIdentityMap(login=login, email=None, source="auto")
                        db.add(id_map)

                    placeholder_email = f"{login}@github.unmatched"
                    unmatched_id = db.query(Identity).filter(Identity.email == placeholder_email).first()
                    if not unmatched_id:
                        unmatched_id = Identity(
                            name=user_meta.get("name") or login,
                            email=placeholder_email,
                            initials=(login[:2]).upper(),
                            job_role="External / Unmatched",
                            team="Unmatched",
                            employment_status="contractor",
                        )
                        db.add(unmatched_id)
                        db.flush()
                    login_to_identity[login] = unmatched_id

            db.flush()

            # 3. Fetch repositories and repository collaborators
            logger.info("Fetching repositories for org '%s'...", org_name)
            try:
                repos = client.get_repos(org_name)
            except RequestCapExceededError:
                is_partial = True
                repos = []

            sync_run.repos_count = len(repos)
            outside_logins = {u["login"] for u in outside}
            seen_assignment_keys: set[tuple[str, str]] = set()  # (resource_id, login)
            user_activity_cache: dict[str, Any] = {}

            for repo_data in repos:
                repo_full_name = repo_data.get("full_name") or f"{org_name}/{repo_data['name']}"
                repo_short_name = repo_data["name"]
                is_archived = repo_data.get("archived", False)

                resource = db.query(Resource).filter(Resource.name == repo_full_name).first()
                if not resource:
                    is_sensitive = (
                        "api" in repo_short_name.lower()
                        or "auth" in repo_short_name.lower()
                        or "gateway" in repo_short_name.lower()
                        or "billing" in repo_short_name.lower()
                        or "terraform" in repo_short_name.lower()
                    )
                    resource = Resource(
                        name=repo_full_name,
                        source="GitHub",
                        is_sensitive=is_sensitive,
                        is_archived=is_archived,
                        project="Engineering",
                    )
                    db.add(resource)
                    db.flush()
                else:
                    resource.is_archived = is_archived

                # Fetch collaborators on repo
                try:
                    collaborators = client.get_repo_collaborators(org_name, repo_short_name)
                except RequestCapExceededError:
                    is_partial = True
                    break
                except GitHubIntegrationError as e:
                    logger.warning("Could not fetch collaborators for %s: %s", repo_full_name, e)
                    continue

                for collab in collaborators:
                    login = collab["login"]
                    access_level = map_github_permission(
                        role_name=collab.get("role_name"),
                        permissions=collab.get("permissions"),
                    )

                    identity = login_to_identity.get(login)
                    if not identity:
                        # Should have been mapped above; fallback if not
                        placeholder_email = f"{login}@github.unmatched"
                        identity = db.query(Identity).filter(Identity.email == placeholder_email).first()
                        if not identity:
                            identity = Identity(
                                name=login,
                                email=placeholder_email,
                                initials=login[:2].upper(),
                                job_role="External / Unmatched",
                                team="Unmatched",
                                employment_status="contractor",
                            )
                            db.add(identity)
                            db.flush()
                        login_to_identity[login] = identity

                    seen_assignment_keys.add((resource.id, login))

                    # Look up activity strictly on THIS repository
                    last_active_at = None
                    last_active_text = "No repo commits"
                    try:
                        last_commit = client.get_last_commit(org_name, repo_short_name, login)
                        if last_commit and last_commit.get("commit", {}).get("author", {}).get("date"):
                            commit_date_str = last_commit.get("commit", {}).get("author", {}).get("date")
                            last_active_at = datetime.fromisoformat(commit_date_str.replace("Z", "+00:00"))

                        if last_active_at:
                            days_ago = max(0, (now - _normalize_utc(last_active_at)).days)
                            if days_ago == 0:
                                last_active_text = "Today"
                            elif days_ago == 1:
                                last_active_text = "1 day ago"
                            elif days_ago >= 30:
                                last_active_text = f"{days_ago} days ago (Dormant)"
                            else:
                                last_active_text = f"{days_ago} days ago"
                        else:
                            last_active_text = "No repo commits"

                        # Auto-discover real email from git commit author if identity is unmatched
                        if last_commit:
                            commit_author_email = last_commit.get("commit", {}).get("author", {}).get("email")
                            if (
                                commit_author_email
                                and "@" in commit_author_email
                                and not commit_author_email.endswith("noreply.github.com")
                                and (identity.email.endswith("@github.unmatched") or (id_map and id_map.email is None))
                            ):
                                real_commit_email = commit_author_email.lower()
                                logger.info("Auto-discovered real commit author email for @%s: %s", login, real_commit_email)
                                identity.email = real_commit_email
                                if identity.team == "Unmatched":
                                    identity.team = "Engineering"
                                    identity.job_role = "Engineer"
                                    identity.employment_status = "active"
                                id_map_entry = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == login).first()
                                if id_map_entry:
                                    id_map_entry.email = real_commit_email
                                    id_map_entry.source = "auto_commit"
                                db.flush()
                    except RequestCapExceededError:
                        is_partial = True
                    except Exception as e:
                        logger.debug("Failed activity lookup for %s on %s: %s", login, repo_short_name, e)

                    # Update or insert assignment
                    existing = (
                        db.query(Assignment)
                        .filter(
                            Assignment.origin == "github",
                            Assignment.resource_id == resource.id,
                            Assignment.github_login == login,
                        )
                        .first()
                    )

                    is_outside = login in outside_logins
                    if existing:
                        prev_access = existing.access_level
                        existing.identity_id = identity.id
                        existing.access_level = access_level
                        existing.is_outside_collaborator = is_outside
                        if last_active_at:
                            existing.last_active_at = last_active_at
                            existing.last_active_text = last_active_text
                        existing.external_status = "active"
                        # Drift detection: if permission level changed on GitHub, re-open finding
                        if prev_access != access_level:
                            existing.resolved = False
                            f_rec = db.query(Finding).filter(Finding.assignment_id == existing.id).first()
                            if f_rec:
                                f_rec.status = "Open"
                        # If an old temporary lease already reached its expiration timestamp, clear is_temporary
                        if getattr(existing, "is_temporary", False) and getattr(existing, "expires_at", None):
                            if _normalize_utc(existing.expires_at) <= now:
                                existing.is_temporary = False
                                existing.expires_at = None
                        sync_run.assignments_updated += 1
                    else:
                        assignment_id = _get_next_assignment_id(db)
                        new_assignment = Assignment(
                            id=assignment_id,
                            identity_id=identity.id,
                            resource_id=resource.id,
                            access_level=access_level,
                            last_active_at=last_active_at,
                            last_active_text=last_active_text,
                            resolved=False,
                            current_risk="Low",
                            reason="Imported from GitHub",
                            origin="github",
                            external_status="active",
                            github_login=login,
                            is_outside_collaborator=is_outside,
                        )
                        db.add(new_assignment)
                        db.flush()
                        sync_run.assignments_created += 1

                        # Existing repository assignments synced from GitHub

            # 4. Handle disappeared assignments (mark revoked_externally, do not delete)
            all_github_assignments = (
                db.query(Assignment).filter(Assignment.origin == "github", Assignment.external_status == "active").all()
            )
            for a in all_github_assignments:
                if (a.resource_id, a.github_login) not in seen_assignment_keys:
                    a.external_status = "revoked_externally"
                    sync_run.assignments_revoked += 1

            sync_run.request_count = client.request_count

    except RequestCapExceededError as e:
        is_partial = True
        error_summary = str(e)
        logger.warning("Sync stopped early: %s", e)
    except Exception as e:
        logger.exception("GitHub sync encountered an error: %s", e)
        sync_run.status = "failed"
        sync_run.error_summary = str(e)
        sync_run.finished_at = datetime.now(UTC)
        db.commit()
        raise

    # 5. Run risk scoring for all active GitHub assignments
    logger.info("Evaluating risk for all active GitHub assignments...")
    active_rule_config_row = db.query(RuleConfig).filter(RuleConfig.is_active == True).first()  # noqa: E712
    rule_config_payload = active_rule_config_row.payload if active_rule_config_row else get_default_rule_config()

    active_github_assignments = (
        db.query(Assignment).filter(Assignment.origin == "github", Assignment.external_status == "active").all()
    )

    for assignment in active_github_assignments:
        identity = assignment.identity
        resource = assignment.resource

        is_unmatched = identity.team == "Unmatched" or identity.email.endswith("@github.unmatched")

        id_ctx = IdentityContext(
            name=identity.name,
            email=identity.email,
            job_role=identity.job_role,
            team=identity.team,
            employment_status=identity.employment_status,
            current_project=identity.current_project,
            is_unmatched=is_unmatched,
            github_login=assignment.github_login,
        )
        res_ctx = ResourceContext(
            name=resource.name,
            source=resource.source,
            is_sensitive=resource.is_sensitive,
            project=resource.project,
        )

        last_active_days = calculate_days_inactive(assignment.last_active_at)

        finding_ctx = FindingContext(
            direct_admin_bypass=assignment.direct_admin_bypass,
            privileged_inactive=assignment.privileged_inactive,
        )

        existing_finding = db.query(Finding).filter(Finding.assignment_id == assignment.id).first()
        is_resolved = assignment.resolved
        finding_status = existing_finding.status if existing_finding else "Open"

        # Do not overwrite findings that have already been reviewed/approved/remediated
        if existing_finding and existing_finding.status in ("Remediated", "Dismissed", "Approved change"):
            continue

        eval_res = evaluate_risk(
            identity=id_ctx,
            resource=res_ctx,
            access_level=assignment.access_level,
            last_active_days=last_active_days,
            last_activity_text=assignment.last_active_text or "no recorded activity found",
            finding_context=finding_ctx,
            resolved=is_resolved,
            finding_status=finding_status,
            rule_config=rule_config_payload,
        )

        assignment.current_risk = eval_res.risk_level
        assignment.reason = eval_res.primary_reason

        snapshot = serialize_assignment(assignment).model_dump(by_alias=True)
        if not existing_finding:
            finding = Finding(
                id=assignment.id,
                assignment_id=assignment.id,
                original_reason=eval_res.primary_reason,
                original_severity=eval_res.risk_level,
                original_access=assignment.access_level,
                detected_at=now,
                status="Healthy" if eval_res.risk_level == "Low" else "Open",
                evidence=eval_res.evidence,
                snapshot=snapshot,
            )
            db.add(finding)
        else:
            existing_finding.original_reason = eval_res.primary_reason
            existing_finding.original_severity = eval_res.risk_level
            existing_finding.original_access = assignment.access_level
            existing_finding.evidence = eval_res.evidence
            existing_finding.status = "Healthy" if eval_res.risk_level == "Low" else "Open"
            existing_finding.snapshot = snapshot

    # 6. Complete SyncRun
    finished_time = datetime.now(UTC)
    sync_run.finished_at = finished_time
    sync_run.status = "partial" if is_partial else "ok"
    if error_summary:
        sync_run.error_summary = error_summary

    config.last_sync_at = finished_time

    # Check for accounts with hidden emails and dispatch in-app notification to administrators
    unmatched_users = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.email.is_(None)).all()
    if unmatched_users:
        hidden_logins = [f"@{u.login}" for u in unmatched_users]
        logins_summary = ", ".join(hidden_logins[:3])
        if len(hidden_logins) > 3:
            logins_summary += f" and {len(hidden_logins) - 3} others"
        try:
            from app.engine.notification_service import broadcast_notification
            broadcast_notification(
                db=db,
                event_type="hidden_emails",
                title=f"Hidden emails detected ({len(hidden_logins)} GitHub accounts)",
                message=f"{logins_summary} keep their emails hidden on GitHub. Add their company emails manually in Settings to enable automated revocation notices.",
                link="#settings",
            )
        except Exception as notif_err:
            logger.warning("Could not broadcast hidden_emails notification: %s", notif_err)

    # 7. Write append-only audit log
    audit_note = (
        f"GitHub sync completed ({sync_run.status}): {sync_run.assignments_created} created, "
        f"{sync_run.assignments_updated} updated, {sync_run.assignments_revoked} revoked. "
        f"Requests: {sync_run.request_count}."
    )
    audit_event = AuditLog(
        id=f"EVT-{int(time.time() * 1000)}",
        actor=actor_email,
        tag="Integration",
        title="GitHub organization sync",
        detail=f"{sync_run.assignments_created} created, {sync_run.assignments_updated} updated, {sync_run.assignments_revoked} revoked",
        note=audit_note,
        source="GitHub",
        before=str(config.last_sync_at),
        after=str(finished_time),
        tone="gray",
        icon="repo",
        mode="DRY_RUN",
        occurred_at=finished_time,
    )
    db.add(audit_event)
    db.commit()
    db.refresh(sync_run)
    return sync_run
