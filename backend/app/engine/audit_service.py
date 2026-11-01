"""
Shared IAM Audit Execution Service for AccessReaper v2.
Used by both the manual /api/audits/run endpoint and APScheduler scheduled audit jobs.
Enforces overlap prevention, snapshot freezing, rule version tracking, and append-only audit logging.
Supports workspace dataMode ('sample' | 'live') and optional 'sync_before_audit' hook.
"""

import logging
import threading
import time
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.time import KARACHI_TZ, calculate_days_inactive
from app.db.models import (
    Assignment,
    AuditLog,
    AuditRun,
    AuditSnapshot,
    GitHubConfig,
    GitHubIdentityMap,
    RuleConfig,
    Setting,
    SoDConflict,
    utc_now,
)
from app.engine.scoring import (
    FindingContext,
    IdentityContext,
    ResourceContext,
    evaluate_risk,
    get_default_rule_config,
)
from app.integrations.github.sync import run_github_sync
from app.schemas.serializers import serialize_assignment

logger = logging.getLogger("accessreaper.audit_service")

# Overlap guard
_audit_lock = threading.Lock()


def _get_data_mode(db: Session) -> str:
    setting = db.query(Setting).filter(Setting.key == "dataMode").first()
    return setting.value if setting and setting.value in ("sample", "live") else "sample"


def execute_audit_run(
    db: Session,
    actor: str,
    trigger: str = "manual",
    status_override: str | None = None,
    degraded_reason: str | None = None,
) -> AuditRun:
    """
    Executes a complete IAM access audit run.
    Guards against overlapping runs.
    Uses active RuleConfig weights, freezes findings into findings_snapshot,
    records daily AuditSnapshot, and appends an immutable AuditLog event.
    """
    acquired = _audit_lock.acquire(blocking=False)
    if not acquired:
        logger.warning("Audit run skipped: another audit is already in progress.")
        if trigger == "scheduled":
            return None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "AUDIT_IN_PROGRESS",
                    "message": "Another audit run is currently in progress.",
                }
            },
        )

    try:
        now_karachi = datetime.now(KARACHI_TZ)
        completed_at = utc_now()

        # 0. Sync before audit hook (if configured)
        gh_config = db.query(GitHubConfig).first()
        if gh_config and gh_config.connected and gh_config.sync_before_audit:
            try:
                logger.info("Executing sync_before_audit hook prior to audit run...")
                run_github_sync(db, actor_email=actor, trigger=trigger)
            except Exception as e:
                logger.warning("sync_before_audit failed: %s. Continuing with existing data.", e)

        data_mode = _get_data_mode(db)

        # 1. Fetch active RuleConfig
        active_rc = db.query(RuleConfig).filter(RuleConfig.is_active == True).first()  # noqa: E712
        active_payload = active_rc.payload if active_rc else get_default_rule_config()
        rule_version = active_rc.version if active_rc else 1

        # 2. Fetch assignments based on data_mode
        if data_mode == "live":
            query = db.query(Assignment).filter(
                Assignment.origin == "github",
                Assignment.external_status != "revoked_externally",
            )
            scope = ["GitHub"]
            is_sample = False
            audit_source_label = "GitHub"
        else:
            query = db.query(Assignment).filter(Assignment.origin == "sample")
            scope = ["GitHub", "Firestore"]
            is_sample = True
            audit_source_label = "GitHub + Firestore"

        assignments = (
            query.options(
                joinedload(Assignment.identity),
                joinedload(Assignment.resource),
                joinedload(Assignment.finding),
            )
            .order_by(Assignment.id.asc())
            .all()
        )

        # 3. Re-evaluate open assignments with engine
        gh_maps = {m.login: m for m in db.query(GitHubIdentityMap).all()}
        sod_conflicts = [
            {
                "id": s.id,
                "pattern_a": s.pattern_a,
                "access_a": s.access_a,
                "pattern_b": s.pattern_b,
                "access_b": s.access_b,
                "description": s.description,
                "points": s.points,
                "enabled": s.enabled,
            }
            for s in db.query(SoDConflict).filter(SoDConflict.enabled == True).all()  # noqa: E712
        ]

        admin_counts: dict[str, int] = {}
        user_assignments: dict[str, list[tuple[str, str]]] = {}
        for a in assignments:
            if a.access_level == "Admin" and not a.resolved:
                admin_counts[a.resource_id] = admin_counts.get(a.resource_id, 0) + 1
            user_assignments.setdefault(a.identity_id, []).append((a.resource.name, a.access_level))

        for a in assignments:
            is_unmatched = a.identity.team == "Unmatched" or (
                a.identity.email and a.identity.email.endswith("@github.unmatched")
            )
            gh_map = gh_maps.get(a.github_login) if a.github_login else None
            account_type = gh_map.account_type if gh_map else "user"
            other_assignments = [
                pair for pair in user_assignments.get(a.identity_id, []) if pair != (a.resource.name, a.access_level)
            ]
            admin_count = admin_counts.get(a.resource_id, 0)
            a._other_assignments = other_assignments
            a._admin_count = admin_count

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
                    account_type=account_type,
                    is_outside_collaborator=getattr(a, "is_outside_collaborator", False),
                ),
                resource=ResourceContext(
                    name=a.resource.name,
                    source=a.resource.source,
                    is_sensitive=a.resource.is_sensitive,
                    project=a.resource.project,
                    is_archived=getattr(a.resource, "is_archived", False),
                    admin_count=admin_count,
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
                rule_config=active_payload,
                other_assignments=other_assignments,
                sod_conflicts=sod_conflicts,
            )

            if not a.resolved:
                a.current_risk = eval_res.risk_level
                a.reason = eval_res.primary_reason
                if a.finding:
                    a.finding.status = "Healthy" if eval_res.risk_level == "Low" else "Open"
                    a.finding.original_severity = eval_res.risk_level
                    a.finding.original_reason = eval_res.primary_reason
                    a.finding.evidence = eval_res.evidence

        # 4. Compute statistics
        total_assignments = len(assignments)
        distinct_identities = len({a.identity.email for a in assignments})
        high_count = sum(1 for a in assignments if not a.resolved and a.current_risk == "High")
        medium_count = sum(1 for a in assignments if not a.resolved and a.current_risk == "Medium")
        healthy_count = sum(1 for a in assignments if not a.resolved and a.current_risk == "Low")
        resolved_count = sum(
            1 for a in assignments if a.resolved and a.finding and a.finding.original_severity != "Low"
        )

        sources_summary = []
        for src in scope:
            src_assignments = [a for a in assignments if a.resource.source == src]
            src_resources = len({a.resource.name for a in src_assignments})
            sources_summary.append(
                {
                    "source": src,
                    "assignments": len(src_assignments),
                    "resources": src_resources,
                }
            )

        # 5. Capture frozen findings snapshot
        findings_snapshot = [serialize_assignment(a).model_dump(by_alias=True) for a in assignments]

        # 6. Generate unique AuditRun ID (AUD-YYYYMMDD-###)
        day_prefix = now_karachi.strftime("%Y%m%d")
        existing_today = db.query(AuditRun).filter(AuditRun.id.like(f"AUD-{day_prefix}-%")).count()
        run_id = f"AUD-{day_prefix}-{existing_today + 1:03d}"
        run_status = status_override or "Completed"

        audit_run = AuditRun(
            id=run_id,
            completed_at=completed_at,
            status=run_status,
            actor=actor,
            scope=scope,
            assignments=total_assignments,
            identities=distinct_identities,
            high=high_count,
            medium=medium_count,
            healthy=healthy_count,
            resolved=resolved_count,
            sources=sources_summary,
            sample=is_sample,
            mode="LIVE_GITHUB" if not is_sample else "DRY_RUN",
            rule_version=rule_version,
            trigger=trigger,
            degraded_reason=degraded_reason,
            findings_snapshot=findings_snapshot,
        )
        db.add(audit_run)
        db.flush()

        # 7. Add audit log entry
        event_id = f"EVT-{int(time.time() * 1000)}"
        audit_title = "Scheduled access audit completed" if trigger == "scheduled" else "Access audit completed"
        detail_suffix = f" (Degraded: {degraded_reason})" if degraded_reason else ""
        log_entry = AuditLog(
            id=event_id,
            actor=actor,
            tag="Audit",
            title=audit_title,
            detail=f"{total_assignments} assignments checked; {high_count} high / {medium_count} medium findings (rules v{rule_version}){detail_suffix}",
            note=f"Triggered via {trigger} execution ({'Live data' if not is_sample else 'Sample data'})",
            source=audit_source_label,
            assignment_id=None,
            request_id=None,
            audit_id=run_id,
            before=None,
            after=None,
            tone="orange" if run_status == "Degraded" else "gray",
            icon="!" if run_status == "Degraded" else "?",
            mode="LIVE_GITHUB" if not is_sample else "DRY_RUN",
            occurred_at=completed_at,
        )
        db.add(log_entry)

        # 8. Take daily snapshot
        remediated_count = db.query(AuditLog).filter(AuditLog.tag == "Remediated").count()
        snapshot = AuditSnapshot(
            at=completed_at,
            label=f"{audit_title} ({trigger})",
            high=high_count,
            medium=medium_count,
            healthy=healthy_count,
            resolved=resolved_count,
            assignments=total_assignments,
            remediated=remediated_count,
        )
        db.add(snapshot)

        # 9. Update lastAudit setting
        last_audit_str = now_karachi.strftime("%b %d, %Y, %I:%M %p").replace(" 0", " ")
        last_audit_setting = db.query(Setting).filter(Setting.key == "lastAudit").first()
        if last_audit_setting:
            last_audit_setting.value = last_audit_str
        else:
            db.add(Setting(key="lastAudit", value=last_audit_str))

        # 10. Stage 4: Generate AI explanations (Gemini / deterministic fallback)
        try:
            from app.engine.gemini_service import generate_audit_explanations
            generate_audit_explanations(db, audit_run, assignments)
        except Exception as exc:
            logger.warning("Error generating AI explanations: %s", exc)

        # 11. Stage 4: In-app notifications
        try:
            from app.engine.notification_service import (
                check_and_notify_overdue_approvals,
                notify_audit_completed,
            )
            notify_audit_completed(db, audit_run)
            check_and_notify_overdue_approvals(db)
        except Exception as exc:
            logger.warning("Error creating audit notifications: %s", exc)

        # 12. Stage 4: Scheduled Daily Email Digest
        if trigger == "scheduled":
            try:
                from app.engine.email_service import send_daily_audit_digest
                prefs = db.query(NotificationPreference).all()
                admin_emails = [p.admin_email for p in prefs if p.admin_email] or ["admin@payhive-eng.internal"]
                send_daily_audit_digest(db, audit_run, admin_emails)
            except Exception as exc:
                logger.warning("Error dispatching daily email digest: %s", exc)

        db.commit()
        db.refresh(audit_run)
        logger.info("Audit run %s completed successfully (trigger=%s, actor=%s)", run_id, trigger, actor)
        return audit_run
    finally:
        _audit_lock.release()
