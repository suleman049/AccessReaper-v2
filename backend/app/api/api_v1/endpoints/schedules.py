"""
Audit scheduling endpoints for AccessReaper v2.
Allows administrators to configure in-process recurring audits (daily/weekly/off),
query upcoming run times, and records append-only schedule change events.
"""

import time
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.scheduler import configure_job, get_next_run_time
from app.core.security import UserClaims, require_role
from app.core.time import KARACHI_TZ
from app.db.models import AuditLog, Schedule, utc_now
from app.db.session import get_db

router = APIRouter()


class ScheduleUpdate(BaseModel):
    enabled: bool = True
    frequency: Literal["off", "daily", "weekly"]
    timeOfDay: str = Field(pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", default="09:00")
    dayOfWeek: Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun", None] = None


class ScheduleResponse(BaseModel):
    enabled: bool
    frequency: str
    timeOfDay: str
    dayOfWeek: str | None
    nextRun: str | None
    formattedNextRun: str | None
    lastRunAt: str | None


def _format_next_run(next_dt) -> tuple[str | None, str]:
    if not next_dt:
        return None, "Not scheduled"
    local_dt = next_dt.astimezone(KARACHI_TZ)
    iso_str = local_dt.isoformat()
    formatted = local_dt.strftime("%A, %b %d at %I:%M %p PKT").replace(" 0", " ")
    return iso_str, formatted


@router.get("/schedule", response_model=ScheduleResponse)
def get_audit_schedule(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Returns the current audit schedule configuration and the next scheduled execution time.
    """
    sch = db.query(Schedule).first()
    if not sch:
        sch = Schedule(id=1, enabled=False, frequency="off", time_of_day="09:00", day_of_week=None)
        db.add(sch)
        db.commit()
        db.refresh(sch)

    next_dt = get_next_run_time()
    next_iso, formatted = _format_next_run(next_dt)

    return ScheduleResponse(
        enabled=sch.enabled,
        frequency=sch.frequency,
        timeOfDay=sch.time_of_day,
        dayOfWeek=sch.day_of_week,
        nextRun=next_iso,
        formattedNextRun=formatted,
        lastRunAt=sch.last_run_at.isoformat() if sch.last_run_at else None,
    )


@router.put("/schedule", response_model=ScheduleResponse)
def update_audit_schedule(
    req: ScheduleUpdate,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Updates the recurring audit schedule in the database and reconfigures APScheduler.
    Appends an immutable audit log entry.
    """
    sch = db.query(Schedule).first()
    if not sch:
        sch = Schedule(id=1)
        db.add(sch)

    old_summary = f"{sch.frequency} at {sch.time_of_day}" if sch.enabled else "Disabled"

    sch.enabled = req.enabled and req.frequency != "off"
    sch.frequency = req.frequency
    sch.time_of_day = req.timeOfDay
    sch.day_of_week = req.dayOfWeek if req.frequency == "weekly" else None
    sch.updated_at = utc_now()
    sch.updated_by = user.name

    # Reconfigure APScheduler
    configure_job(
        enabled=sch.enabled,
        frequency=sch.frequency,
        time_of_day=sch.time_of_day,
        day_of_week=sch.day_of_week,
    )

    next_dt = get_next_run_time()
    sch.next_run_at = next_dt

    new_summary = f"{sch.frequency} at {sch.time_of_day}" if sch.enabled else "Disabled"

    # Append to append-only audit_log
    event_id = f"EVT-{int(time.time() * 1000)}"
    log_entry = AuditLog(
        id=event_id,
        actor=user.name,
        tag="Schedule",
        title="Audit schedule updated",
        detail=f"Automated audit schedule updated to {new_summary}",
        note=f"Configured by administrator {user.name}",
        source="Scheduler",
        assignment_id=None,
        request_id=None,
        audit_id=None,
        before=old_summary,
        after=new_summary,
        tone="blue",
        icon="↻",
        mode="DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(sch)

    next_iso, formatted = _format_next_run(next_dt)

    return ScheduleResponse(
        enabled=sch.enabled,
        frequency=sch.frequency,
        timeOfDay=sch.time_of_day,
        dayOfWeek=sch.day_of_week,
        nextRun=next_iso,
        formattedNextRun=formatted,
        lastRunAt=sch.last_run_at.isoformat() if sch.last_run_at else None,
    )


@router.get("/schedule/next-run")
def get_next_audit_run(
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Returns the next calculated scheduled audit run time.
    """
    next_dt = get_next_run_time()
    next_iso, formatted = _format_next_run(next_dt)
    return {
        "nextRun": next_iso,
        "formatted": formatted,
    }
