"""
In-process APScheduler service for AccessReaper v2.
Manages automated 24-hour audit triggers with Asia/Karachi timezone,
misfire protection (6 hours), single instance execution, overlap prevention,
and 5-minute heartbeat catch-up execution.
"""

import logging
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.time import KARACHI_TZ
from app.db.session import SessionLocal

logger = logging.getLogger("accessreaper.scheduler")

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=KARACHI_TZ)
    return _scheduler


def scheduled_audit_task():
    """Target job for 24-hour automated audit cycle."""
    logger.info("Executing scheduled 24-hour IAM audit cycle...")
    try:
        from app.engine.automation import execute_automatic_cycle

        with SessionLocal() as db:
            execute_automatic_cycle(db, actor="Automatic audit")
    except Exception as exc:
        logger.error("Error executing scheduled audit cycle: %s", exc, exc_info=True)


def heartbeat_task():
    """5-minute heartbeat to check for catch-up audits."""
    try:
        from app.engine.automation import check_and_run_catchup

        check_and_run_catchup()
    except Exception as exc:
        logger.debug("Automation heartbeat check: %s", exc)


def trigger_background_github_sync(actor: str = "Automated sync", trigger: str = "auto_periodic"):
    """Spawns an asynchronous background thread to sync GitHub without blocking callers."""
    def _run():
        try:
            from app.db.models import GitHubConfig
            from app.integrations.github.sync import run_github_sync

            with SessionLocal() as db:
                gh_config = db.query(GitHubConfig).first()
                if not gh_config or not gh_config.connected:
                    return
                logger.info("Executing automated background GitHub sync (actor=%s, trigger=%s)...", actor, trigger)
                run_github_sync(db, actor_email=actor, trigger=trigger)
                logger.info("Automated background GitHub sync finished successfully.")
        except Exception as exc:
            logger.error("Automated background GitHub sync failed: %s", exc)

    thread = threading.Thread(target=_run, daemon=True, name="automated_github_sync_thread")
    thread.start()


def periodic_github_sync_task():
    """Periodic automated background sync for connected GitHub organization (runs every 15m)."""
    try:
        from app.db.models import GitHubConfig
        from app.integrations.github.sync import run_github_sync

        with SessionLocal() as db:
            gh_config = db.query(GitHubConfig).first()
            if not gh_config or not gh_config.connected:
                return

            logger.info("Executing periodic automated GitHub sync...")
            run_github_sync(db, actor_email="Automated Sync Scheduler", trigger="auto_periodic")
            logger.info("Periodic automated GitHub sync completed successfully.")
    except Exception as exc:
        logger.error("Periodic automated GitHub sync encountered an error: %s", exc)


def jit_and_autoreaper_task():
    """Runs the 60-second JIT temporary access expiration and dormant account auto-reaper."""
    try:
        from app.engine.automation import run_jit_and_reaper_cycle

        run_jit_and_reaper_cycle()
    except Exception as exc:
        logger.debug("JIT and auto-reaper task execution error: %s", exc)


def configure_job(enabled: bool, frequency: str = "daily", time_of_day: str = "02:00", day_of_week: str | None = None):
    """
    Configures or removes the recurring audit job based on schedule parameters.
    """
    scheduler = get_scheduler()
    job_id = "accessreaper_scheduled_audit"

    # Remove existing job if present
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info("Removed existing scheduled audit job.")

    if not enabled or frequency == "off":
        logger.info("Automatic audits paused.")
        return

    try:
        parts = time_of_day.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        hour, minute = 2, 0

    trigger = CronTrigger(hour=hour, minute=minute, timezone=KARACHI_TZ)
    scheduler.add_job(
        scheduled_audit_task,
        trigger=trigger,
        id=job_id,
        name="Automatic 24-Hour IAM Audit",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=21600,
    )
    logger.info("Configured automatic audit at %02d:%02d PKT every 24 hours", hour, minute)


def get_next_run_time() -> datetime | None:
    """Returns the next scheduled trigger time in Karachi timezone, or None."""
    scheduler = get_scheduler()
    job = scheduler.get_job("accessreaper_scheduled_audit")
    if not job:
        return None

    next_time = getattr(job, "next_run_time", None)
    if not next_time and hasattr(job, "trigger") and job.trigger:
        try:
            next_time = job.trigger.get_next_fire_time(None, datetime.now(KARACHI_TZ))
        except Exception:
            next_time = None

    if next_time:
        return next_time.astimezone(KARACHI_TZ)
    return None


def init_scheduler():
    """Starts the background scheduler, configures 24-hour job and 5-min heartbeat."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler background scheduler started.")

    try:
        from app.db.models import Schedule

        with SessionLocal() as db:
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

            configure_job(
                enabled=sch.enabled,
                frequency=sch.frequency or "daily",
                time_of_day=sch.time_of_day or "02:00",
                day_of_week=sch.day_of_week,
            )
    except Exception as exc:
        logger.error("Failed to restore schedule from database: %s", exc)

    # Register 5-minute recurring heartbeat
    if not scheduler.get_job("automation_heartbeat"):
        scheduler.add_job(
            heartbeat_task,
            trigger=IntervalTrigger(minutes=5),
            id="automation_heartbeat",
            name="Automation Catch-Up Heartbeat (5m)",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        logger.info("Registered 5-minute automation catch-up heartbeat.")

    # Register 15-minute recurring automated GitHub sync
    if not scheduler.get_job("github_periodic_sync"):
        scheduler.add_job(
            periodic_github_sync_task,
            trigger=IntervalTrigger(minutes=15),
            id="github_periodic_sync",
            name="Automated GitHub Background Sync (15m)",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        logger.info("Registered 15-minute automated GitHub background sync.")

    # Register 1-minute recurring JIT expiration and auto-reaper task
    if not scheduler.get_job("jit_and_autoreaper"):
        scheduler.add_job(
            jit_and_autoreaper_task,
            trigger=IntervalTrigger(seconds=10),
            id="jit_and_autoreaper",
            name="JIT Expiration & Inactivity Auto-Reaper (1m)",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        logger.info("Registered 1-minute JIT expiration and auto-reaper schedule.")

    # Run immediate background sync on startup if GitHub is connected
    trigger_background_github_sync(actor="Startup automated sync", trigger="startup")

    # Run one asynchronous catch-up check on startup in a separate thread
    threading.Thread(target=heartbeat_task, daemon=True, name="startup_catchup_check").start()


def shutdown_scheduler():
    """Shuts down the background scheduler cleanly."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler background scheduler stopped.")
        _scheduler = None
