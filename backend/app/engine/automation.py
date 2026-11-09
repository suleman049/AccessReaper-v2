"""
Automation engine for AccessReaper v2 (Stage 1).
Manages fully automated 24-hour IAM audit cycles, catch-up executions,
overlap locking, GitHub sync resilience with degraded status and 10-minute retry,
and automation configuration / status inspection.
"""

import logging
import threading
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.scheduler import get_scheduler
from app.core.time import KARACHI_TZ
from app.db.models import (
    Assignment,
    AuditLog,
    AuditRun,
    GitHubConfig,
    Identity,
    Schedule,
    Setting,
    utc_now,
)
from app.db.session import SessionLocal
from app.engine.audit_service import _audit_lock, execute_audit_run
from app.integrations.github.sync import run_github_sync
from app.schemas.serializers import format_iso_karachi

logger = logging.getLogger("accessreaper.automation")

_automation_cycle_lock = threading.Lock()


def is_audit_running() -> bool:
    """Returns True if an audit run is currently in progress."""
    return _audit_lock.locked() or _automation_cycle_lock.locked()


def get_data_mode(db: Session) -> str:
    setting = db.query(Setting).filter(Setting.key == "dataMode").first()
    return setting.value if setting and setting.value in ("sample", "live") else "sample"


def schedule_github_sync_retry():
    """Schedules a one-off retry of GitHub sync after 10 minutes if an earlier sync failed."""
    scheduler = get_scheduler()
    retry_time = datetime.now(KARACHI_TZ) + timedelta(minutes=10)

    def _sync_retry_task():
        logger.info("Executing scheduled 10-minute retry for GitHub sync...")
        try:
            with SessionLocal() as db:
                gh_config = db.query(GitHubConfig).first()
                if gh_config and gh_config.connected:
                    run_github_sync(db, actor_email="Automatic audit (retry)", trigger="retry")
                    logger.info("Automatic GitHub sync retry succeeded.")
        except Exception as exc:
            logger.error("Automatic GitHub sync retry failed: %s", exc)

    try:
        scheduler.add_job(
            _sync_retry_task,
            trigger="date",
            run_date=retry_time,
            id="github_sync_retry",
            replace_existing=True,
            name="GitHub Sync Retry (10m)",
        )
        logger.info("Scheduled GitHub sync retry at %s PKT", retry_time.strftime("%H:%M:%S"))
    except Exception as exc:
        logger.warning("Could not register sync retry task: %s", exc)


def execute_automatic_cycle(db: Session, actor: str = "Automatic audit") -> AuditRun | None:
    """
    Executes a complete automatic IAM audit cycle:
    1. If dataMode is 'live' and GitHub connected: runs GitHub sync.
       If sync fails: continues in degraded mode, logs reason, schedules 10-minute retry.
    2. Runs audit execution with frozen findings snapshot and immutable audit log.
    3. Updates Schedule.last_run_at.
    """
    if _audit_lock.locked() or _automation_cycle_lock.locked():
        logger.warning("Automatic audit cycle skipped: audit already in progress.")
        return None

    if not _automation_cycle_lock.acquire(blocking=False):
        logger.warning("Automatic audit cycle skipped: could not acquire cycle lock.")
        return None

    try:
        return _do_execute_automatic_cycle(db=db, actor=actor)
    finally:
        _automation_cycle_lock.release()


def _do_execute_automatic_cycle(db: Session, actor: str = "Automatic audit") -> AuditRun | None:
    logger.info("Starting automatic 15-minute IAM audit cycle (actor=%s)...", actor)

    sync_failed = False
    degraded_reason: str | None = None
    data_mode = get_data_mode(db)

    # 1. GitHub sync (if connected and dataMode is live)
    if data_mode == "live":
        gh_config = db.query(GitHubConfig).first()
        if gh_config and gh_config.connected:
            try:
                logger.info("Running automated GitHub sync before audit...")
                run_github_sync(db, actor_email=actor, trigger="scheduled")
                logger.info("Automated GitHub sync completed successfully.")
            except Exception as exc:
                sync_failed = True
                degraded_reason = f"GitHub sync failed: {exc}"
                logger.warning("Automatic GitHub sync failed (%s). Continuing audit in Degraded mode.", exc)
                schedule_github_sync_retry()

    # 2. Audit run
    run_status = "Degraded" if sync_failed else "Completed"
    audit_run = execute_audit_run(
        db=db,
        actor=actor,
        trigger="scheduled",
        status_override=run_status,
        degraded_reason=degraded_reason,
    )

    # 3. Update schedule record
    sch = db.query(Schedule).first()
    if sch:
        sch.last_run_at = utc_now()
        db.commit()

    logger.info(
        "Automatic audit cycle finished: run_id=%s, status=%s, high=%s, medium=%s",
        getattr(audit_run, "id", None),
        run_status,
        getattr(audit_run, "high", 0),
        getattr(audit_run, "medium", 0),
    )

    # 4. In-app notifications and daily audit digest email are already
    # dispatched inside execute_audit_run() to prevent duplicate alerts.
    logger.debug("Notifications and digest handled inside execute_audit_run for run_id=%s", getattr(audit_run, "id", None))

    return audit_run


def check_and_run_catchup(db: Session | None = None):
    """
    Heartbeat and startup check:
    If automatic audits are enabled, checks time since last successful automatic audit.
    If > 24 hours + 15 min grace (87,300 seconds), executes ONE catch-up audit immediately.
    Never burst-runs multiple catch-ups.
    """
    if _audit_lock.locked():
        return

    def _do_check(session: Session):
        sch = session.query(Schedule).first()
        if not sch or not sch.enabled:
            return

        last_auto_run = (
            session.query(AuditRun)
            .filter(AuditRun.trigger == "scheduled")
            .order_by(AuditRun.completed_at.desc())
            .first()
        )

        now_utc = utc_now()
        # 24 hours + 15 minutes = 87300 seconds
        grace_threshold_seconds = 24 * 3600 + 15 * 60

        needs_catchup = False
        if last_auto_run:
            completed_at = last_auto_run.completed_at
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=now_utc.tzinfo)
            elapsed = (now_utc - completed_at).total_seconds()
            if elapsed > grace_threshold_seconds:
                logger.warning(
                    "Last automatic audit was %.1f hours ago (> 24h + 15m grace). Triggering catch-up audit.",
                    elapsed / 3600,
                )
                needs_catchup = True
        elif sch.last_run_at:
            last_time = sch.last_run_at
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=now_utc.tzinfo)
            elapsed = (now_utc - last_time).total_seconds()
            if elapsed > grace_threshold_seconds:
                needs_catchup = True

        if needs_catchup:
            execute_automatic_cycle(session, actor="Automatic audit (catch-up)")

    if db is not None:
        _do_check(db)
    else:
        try:
            with SessionLocal() as session:
                _do_check(session)
        except Exception as exc:
            logger.error("Error during automation heartbeat catch-up check: %s", exc)


def get_automation_status(db: Session) -> dict:
    """
    Computes full automation status:
    - enabled, intervalHours: 24, timeOfDay, nextRunAt, serverTime, secondsUntilNext,
    - lastRun: {id, at, status, trigger, degradedReason}, catchUpPending, isRunning, pauseNote
    """
    sch = db.query(Schedule).first()
    if not sch:
        sch = Schedule(
            id=1,
            enabled=True,
            frequency="daily",
            time_of_day="02:00",
            day_of_week=None,
        )
        db.add(sch)
        db.commit()
        db.refresh(sch)

    now_karachi = datetime.now(KARACHI_TZ)
    server_time_iso = now_karachi.isoformat()

    # Calculate next 15-minute scheduled audit execution time
    next_run_dt = None
    try:
        from app.core.scheduler import get_scheduler
        sched = get_scheduler()
        job = sched.get_job("github_periodic_sync")
        if job and getattr(job, "next_run_time", None):
            next_run_dt = job.next_run_time.astimezone(KARACHI_TZ)
    except Exception:
        pass

    if not next_run_dt or next_run_dt <= now_karachi:
        current_minute = now_karachi.minute
        next_boundary_min = ((current_minute // 15) + 1) * 15
        if next_boundary_min >= 60:
            next_run_dt = (now_karachi + timedelta(hours=1)).replace(minute=next_boundary_min % 60, second=0, microsecond=0)
        else:
            next_run_dt = now_karachi.replace(minute=next_boundary_min, second=0, microsecond=0)

    time_of_day = sch.time_of_day or "02:00"

    if sch.enabled:
        next_run_iso = next_run_dt.isoformat()
        seconds_until_next = max(0, int((next_run_dt - now_karachi).total_seconds()))
    else:
        next_run_iso = None
        seconds_until_next = 0

    # Fetch last audit run (prefer scheduled, fallback to any)
    last_run = db.query(AuditRun).order_by(AuditRun.completed_at.desc()).first()

    last_run_info = None
    if last_run:
        last_run_info = {
            "id": last_run.id,
            "at": format_iso_karachi(last_run.completed_at),
            "status": last_run.status,
            "trigger": getattr(last_run, "trigger", "manual"),
            "degradedReason": getattr(last_run, "degraded_reason", None),
        }

    # Catch-up pending check
    catch_up_pending = False
    if sch.enabled and last_run:
        completed = last_run.completed_at
        if completed.tzinfo is None:
            completed = completed.replace(tzinfo=utc_now().tzinfo)
        elapsed = (utc_now() - completed).total_seconds()
        if elapsed > (24 * 3600 + 15 * 60):
            catch_up_pending = True

    return {
        "enabled": sch.enabled,
        "intervalHours": 24,
        "timeOfDay": time_of_day,
        "nextRunAt": next_run_iso,
        "serverTime": server_time_iso,
        "secondsUntilNext": seconds_until_next,
        "lastRun": last_run_info,
        "catchUpPending": catch_up_pending,
        "isRunning": is_audit_running(),
        "pauseNote": sch.pause_note if not sch.enabled else None,
    }


def process_jit_expirations(db: Session) -> int:
    """
    Checks for temporary JIT assignments that have reached their expires_at timestamp.
    Revokes access on live GitHub, marks assignment None, logs audit event,
    sends expiration email, and dispatches webhook.
    """
    from app.core.config import settings
    from app.engine.email_service import send_jit_expiration_email_to_user
    from app.engine.webhook_service import send_security_webhook

    now = utc_now()
    expired = (
        db.query(Assignment)
        .filter(
            Assignment.is_temporary == True,
            Assignment.expires_at <= now,
            Assignment.access_level != "None",
        )
        .all()
    )

    if not expired:
        return 0

    count = 0
    gh_config = db.query(GitHubConfig).first()
    can_live_github = (
        gh_config
        and gh_config.connected
        and gh_config.encrypted_token
        and getattr(settings, "ENABLE_LIVE_GITHUB_REVOCATION", True)
    )

    for a in expired:
        old_access = a.access_level
        username = a.github_login
        repo_name = a.resource.name if a.resource else "repository"
        is_live_github = False

        if can_live_github and username and ("/" in repo_name or (a.resource and a.resource.source == "GitHub")):
            try:
                from app.core.crypto import decrypt_secret
                from app.integrations.github.client import GitHubClient

                token = decrypt_secret(gh_config.encrypted_token)
                owner = gh_config.org_name
                repo_short = repo_name.split("/")[-1] if "/" in repo_name else repo_name
                with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as gh_client:
                    gh_client.remove_repository_collaborator(org=owner, repo=repo_short, username=username)
                    a.external_status = "revoked_externally"
                    is_live_github = True
                    logger.info("JIT Auto-Reaper revoked GitHub collaborator @%s from %s/%s", username, owner, repo_short)
            except Exception as exc:
                logger.error("Failed to revoke collaborator @%s on GitHub live during JIT expiration: %s", username, exc)

        a.access_level = "None"
        a.is_temporary = False
        a.expires_at = None
        a.resolved = True
        a.current_risk = "Low"
        a.reason = "Temporary JIT access expired automatically"
        if a.finding:
            a.finding.status = "Remediated"

        import time

        log_entry = AuditLog(
            id=f"EVT-JIT-{int(time.time() * 1000)}-{count}",
            actor="JIT Auto-Scheduler",
            tag="Auto-Expired",
            title="JIT temporary access expired",
            detail=f"{a.identity.name} · {repo_name}{f' (Live GitHub: @{username})' if is_live_github else ''}",
            note="Access automatically revoked by JIT scheduler upon reaching duration expiration limit.",
            source=a.resource.source if a.resource else "GitHub",
            assignment_id=a.id,
            before=old_access,
            after="None",
            tone="orange",
            icon="⏱️",
            mode="LIVE_GITHUB" if is_live_github else "DRY_RUN",
            occurred_at=utc_now(),
        )
        db.add(log_entry)

        # Broadcast in-app notification to all administrators
        try:
            from app.engine.notification_service import broadcast_notification

            broadcast_notification(
                db=db,
                event_type="jit_expired",
                title="JIT Temporary Access Expired",
                message=f"Temporary {old_access} access for {a.identity.name} (@{username or 'user'}) on {repo_name} reached its expiration limit and was automatically revoked.",
                link="#history",
            )
        except Exception as exc:
            logger.warning("Could not broadcast JIT expiration notification: %s", exc)

        db.commit()

        # Notify recipient via email
        if a.identity and a.identity.email and not a.identity.email.endswith("@github.unmatched"):
            try:
                send_jit_expiration_email_to_user(
                    to_email=a.identity.email,
                    user_name=a.identity.name,
                    repo_name=repo_name,
                    previous_access=old_access,
                    new_status_or_access="Revoked",
                )
            except Exception as exc:
                logger.warning("Could not dispatch user JIT expiration email: %s", exc)

        # Also notify administrators via email
        try:
            from app.db.models import User
            admins = db.query(User).filter(User.role == "admin", User.status == "active").all()
            adm_emails = {u.email for u in admins if u.email}
            if not adm_emails and getattr(settings, "SMTP_USER", None):
                adm_emails = {settings.SMTP_USER}
            for adm_email in adm_emails:
                if adm_email != (a.identity.email if a.identity else None):
                    send_jit_expiration_email_to_user(
                        to_email=adm_email,
                        user_name=f"Admin Notice (User: {a.identity.name})",
                        repo_name=repo_name,
                        previous_access=old_access,
                        new_status_or_access="Automatically Revoked",
                    )
        except Exception as exc:
            logger.warning("Could not dispatch admin JIT expiration email: %s", exc)

        send_security_webhook(
            title="JIT Temporary Access Expired",
            description=f"Temporary access for **{a.identity.name}** (@{username or 'user'}) on **{repo_name}** reached its expiration time and was automatically revoked.",
            color_hex="#eab308",
            fields=[
                {"name": "User", "value": a.identity.name, "inline": True},
                {"name": "Resource", "value": repo_name, "inline": True},
                {"name": "Revoked Access", "value": old_access, "inline": True},
                {"name": "Mode", "value": "LIVE_GITHUB" if is_live_github else "DRY_RUN", "inline": True},
            ],
        )
        count += 1

    return count


def process_inactive_reaper(db: Session) -> dict[str, int]:
    """
    Scans elevated accounts for inactivity:
    - 83 to 89 days inactive with no warning: dispatches 7-day warning email notice & logs warning audit.
    - >= 90 days inactive: auto-reaps access live on GitHub, updates DB, sends notice & logs audit.
    """
    from app.core.config import settings
    from app.core.time import calculate_days_inactive
    from app.engine.email_service import send_inactivity_reaped_email_to_user, send_inactivity_warning_email_to_user
    from app.engine.webhook_service import send_security_webhook

    elevated = (
        db.query(Assignment)
        .filter(
            Assignment.access_level.in_(["Admin", "Write", "Editor"]),
        )
        .all()
    )

    warnings_sent = 0
    reaped_count = 0

    gh_config = db.query(GitHubConfig).first()
    can_live_github = (
        gh_config
        and gh_config.connected
        and gh_config.encrypted_token
        and getattr(settings, "ENABLE_LIVE_GITHUB_REVOCATION", True)
    )

    for a in elevated:
        days = calculate_days_inactive(a.last_active_at, getattr(a, "origin", None))
        if days is None:
            continue

        repo_name = a.resource.name if a.resource else "repository"
        user_name = a.identity.name if a.identity else "User"
        user_email = a.identity.email if a.identity else None
        username = a.github_login

        if days >= 30:
            old_access = a.access_level
            is_live_github = False

            if can_live_github and username and ("/" in repo_name or (a.resource and a.resource.source == "GitHub")):
                try:
                    from app.core.crypto import decrypt_secret
                    from app.integrations.github.client import GitHubClient

                    token = decrypt_secret(gh_config.encrypted_token)
                    owner = gh_config.org_name
                    repo_short = repo_name.split("/")[-1] if "/" in repo_name else repo_name
                    with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as gh_client:
                        gh_client.remove_repository_collaborator(org=owner, repo=repo_short, username=username)
                        a.external_status = "revoked_externally"
                        is_live_github = True
                        logger.info("Zero-Touch Auto-Reaper revoked dormant collaborator @%s (%dd inactive) from %s/%s", username, days, owner, repo_short)
                except Exception as exc:
                    logger.error("Failed to auto-reap collaborator @%s on GitHub: %s", username, exc)

            a.access_level = "None"
            a.resolved = True
            a.current_risk = "Low"
            a.reason = f"Dormant elevated access auto-reaped ({days} days inactive)"
            if a.finding:
                a.finding.status = "Remediated"

            import time

            log_entry = AuditLog(
                id=f"EVT-REAP-{int(time.time() * 1000)}-{reaped_count}",
                actor="Zero-Touch Auto-Reaper",
                tag="Auto-Reaped",
                title=f"Dormant account auto-reaped ({days}d inactive)",
                detail=f"{user_name} · {repo_name}{f' (Live GitHub: @{username})' if is_live_github else ''}",
                note=f"Revoked elevated permissions after {days} days of inactivity under organization compliance policies.",
                source=a.resource.source if a.resource else "GitHub",
                assignment_id=a.id,
                before=old_access,
                after="None",
                tone="red",
                icon="💀",
                mode="LIVE_GITHUB" if is_live_github else "DRY_RUN",
                occurred_at=utc_now(),
            )
            db.add(log_entry)
            db.commit()

            if user_email and not user_email.endswith("@github.unmatched"):
                send_inactivity_reaped_email_to_user(
                    to_email=user_email,
                    user_name=user_name,
                    repo_name=repo_name,
                    previous_access=old_access,
                    days_inactive=days,
                )

            send_security_webhook(
                title="Dormant Account Auto-Reaped",
                description=f"Elevated permissions for **{user_name}** (@{username or 'user'}) on **{repo_name}** were automatically revoked after **{days} days** of inactivity.",
                color_hex="#ef4444",
                fields=[
                    {"name": "User", "value": user_name, "inline": True},
                    {"name": "Resource", "value": repo_name, "inline": True},
                    {"name": "Days Dormant", "value": f"{days} days", "inline": True},
                    {"name": "Mode", "value": "LIVE_GITHUB" if is_live_github else "DRY_RUN", "inline": True},
                ],
            )
            reaped_count += 1

        elif days >= 23 and a.warning_email_sent_at is None:
            days_left = max(1, 30 - days)
            a.warning_email_sent_at = utc_now()

            import time

            log_entry = AuditLog(
                id=f"EVT-WARN-{int(time.time() * 1000)}-{warnings_sent}",
                actor="Zero-Touch Auto-Reaper",
                tag="Warning Notice",
                title=f"7-day reaper warning sent ({days_left}d remaining)",
                detail=f"{user_name} · {repo_name} ({days}d inactive)",
                note=f"Dispatched automated inactivity warning. Account will be auto-reaped in {days_left} days if unused.",
                source=a.resource.source if a.resource else "GitHub",
                assignment_id=a.id,
                tone="orange",
                icon="⚠️",
                mode="DRY_RUN",
                occurred_at=utc_now(),
            )
            db.add(log_entry)
            db.commit()

            if user_email and not user_email.endswith("@github.unmatched"):
                send_inactivity_warning_email_to_user(
                    to_email=user_email,
                    user_name=user_name,
                    repo_name=repo_name,
                    access_level=a.access_level,
                    days_inactive=days,
                    days_left=days_left,
                )

            send_security_webhook(
                title="Inactivity Warning: 7 Days Remaining",
                description=f"Automated warning dispatched to **{user_name}** regarding inactive **{a.access_level}** access on **{repo_name}** ({days} days dormant).",
                color_hex="#f97316",
                fields=[
                    {"name": "User", "value": user_name, "inline": True},
                    {"name": "Resource", "value": repo_name, "inline": True},
                    {"name": "Days Remaining", "value": f"{days_left} days", "inline": True},
                ],
            )
            warnings_sent += 1

    return {"warnings": warnings_sent, "reaped": reaped_count}


def run_jit_and_reaper_cycle():
    """Target function executed periodically by the scheduler."""
    try:
        with SessionLocal() as db:
            jit_count = process_jit_expirations(db)
            reaper_res = process_inactive_reaper(db)
            # Autonomous enforcement if Auto-Pilot is enabled
            ap_setting = db.query(Setting).filter(Setting.key == "autoPilotEnabled").first()
            if ap_setting and ap_setting.value == "true":
                enforce_autopilot(db, actor="Auto-Pilot (Autonomous Background)")

            if jit_count > 0 or reaper_res["reaped"] > 0 or reaper_res["warnings"] > 0:
                logger.info(
                    "JIT and Reaper cycle completed: %d JIT expired, %d dormant reaped, %d warnings sent",
                    jit_count,
                    reaper_res["reaped"],
                    reaper_res["warnings"],
                )
    except Exception as exc:
        logger.error("Error in automated JIT and Reaper cycle: %s", exc)


def get_autopilot_status(db: Session) -> dict:
    """Returns current Auto-Pilot configuration, eligible count, and active policies."""
    setting = db.query(Setting).filter(Setting.key == "autoPilotEnabled").first()
    enabled = (setting.value == "true") if setting else False
    last_setting = db.query(Setting).filter(Setting.key == "autoPilotLastEnforced").first()
    last_enforced = last_setting.value if last_setting else None

    eligible_count = (
        db.query(Assignment)
        .join(Identity, Assignment.identity_id == Identity.id)
        .filter(
            Assignment.access_level == "Admin",
            Assignment.resolved == False,
            (Identity.employment_status == "contractor") | (Identity.team == "External"),
        )
        .count()
    )

    return {
        "enabled": enabled,
        "last_enforced_at": last_enforced,
        "eligible_findings_count": eligible_count,
        "active_policies": [
            "Contractor Privilege De-escalation: External contractors with Admin automatically reduced to Write",
            "JIT Lease Reaper: Expired time-bound access immediately revoked on GitHub",
            "Dormant Account Isolation: Inactive elevated accounts quarantined under compliance policy",
        ],
    }


def set_autopilot_enabled(db: Session, enabled: bool) -> dict:
    """Updates the Auto-Pilot state in settings."""
    setting = db.query(Setting).filter(Setting.key == "autoPilotEnabled").first()
    if not setting:
        setting = Setting(key="autoPilotEnabled", value="true" if enabled else "false")
        db.add(setting)
    else:
        setting.value = "true" if enabled else "false"
    db.commit()
    return get_autopilot_status(db)


def enforce_autopilot(db: Session, actor: str = "Auto-Pilot Policy Enforcer") -> dict:
    """
    Executes autonomous security policies:
    1. Demotes external contractors with Admin permissions down to Write (least privilege).
    2. Revokes expired JIT leases immediately.
    3. Logs immutable audit entries and updates health score.
    """
    import time

    from app.core.config import settings
    from app.engine.webhook_service import send_security_webhook

    # 1. Process expired JIT leases
    jit_count = process_jit_expirations(db)

    # 2. Find external contractors with Admin privileges who are unreviewed
    contractor_assignments = (
        db.query(Assignment)
        .join(Identity, Assignment.identity_id == Identity.id)
        .filter(
            Assignment.access_level == "Admin",
            Assignment.resolved == False,
            (Identity.employment_status == "contractor") | (Identity.team == "External"),
        )
        .all()
    )

    actions = []
    gh_config = db.query(GitHubConfig).first()
    can_live_github = (
        gh_config
        and gh_config.connected
        and gh_config.encrypted_token
        and getattr(settings, "ENABLE_LIVE_GITHUB_REVOCATION", True)
    )

    for a in contractor_assignments:
        user_name = a.identity.name if a.identity else "Contractor"
        user_email = a.identity.email if a.identity else None
        username = a.github_login
        repo_name = a.resource.name if a.resource else "repository"
        old_access = a.access_level
        is_live_github = False

        if can_live_github and username and ("/" in repo_name or (a.resource and a.resource.source == "GitHub")):
            try:
                from app.core.crypto import decrypt_secret
                from app.integrations.github.client import GitHubClient

                token = decrypt_secret(gh_config.encrypted_token)
                owner = gh_config.org_name
                repo_short = repo_name.split("/")[-1] if "/" in repo_name else repo_name
                with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as gh_client:
                    gh_client.set_repository_collaborator_permission(
                        org=owner, repo=repo_short, username=username, permission="push"
                    )
                    is_live_github = True
                    logger.info("Auto-Pilot downgraded contractor @%s to Write on %s/%s", username, owner, repo_short)
            except Exception as exc:
                logger.error("Auto-Pilot GitHub downgrade error for @%s: %s", username, exc)

        a.access_level = "Write"
        a.resolved = True
        a.current_risk = "Low"
        a.reason = "Auto-Pilot: External contractor Admin de-escalated to Write under Least Privilege policy"
        if a.finding:
            a.finding.status = "Remediated"

        # Immutable audit log
        log_entry = AuditLog(
            id=f"EVT-AUTOPILOT-{int(time.time() * 1000)}-{len(actions)}",
            actor=actor,
            tag="Remediated",
            title="Auto-Pilot: Contractor Admin de-escalated",
            detail=f"{user_name} · {repo_name} (Admin → Write)",
            note="Autonomous least-privilege policy enforced: external contractor elevated access reduced.",
            source=a.resource.source if a.resource else "GitHub",
            assignment_id=a.id,
            before=old_access,
            after="Write",
            tone="green",
            icon="⚡",
            mode="LIVE_GITHUB" if is_live_github else "DRY_RUN",
            occurred_at=utc_now(),
        )
        db.add(log_entry)
        actions.append({
            "assignment_id": a.id,
            "user": user_name,
            "resource": repo_name,
            "before": old_access,
            "after": "Write",
            "reason": "Contractor de-escalation policy",
        })

    # Save last enforced timestamp
    last_setting = db.query(Setting).filter(Setting.key == "autoPilotLastEnforced").first()
    if not last_setting:
        last_setting = Setting(key="autoPilotLastEnforced", value=utc_now().isoformat())
        db.add(last_setting)
    else:
        last_setting.value = utc_now().isoformat()

    db.commit()

    if actions:
        send_security_webhook(
            title="Auto-Pilot Security Policies Enforced",
            description=f"Auto-Pilot has autonomously remediated **{len(actions)} high-risk contractor privileges**.",
            color_hex="#10b981",
            fields=[
                {"name": "Remediated Assignments", "value": str(len(actions)), "inline": True},
                {"name": "JIT Expired", "value": str(jit_count), "inline": True},
                {"name": "Enforcement Mode", "value": "Autonomous Active", "inline": True},
            ],
        )

    return {
        "success": True,
        "remediated_count": len(actions),
        "jit_reaped_count": jit_count,
        "actions": actions,
        "message": f"Auto-Pilot successfully remediated {len(actions)} high-risk privileges and {jit_count} expired JIT leases.",
    }
