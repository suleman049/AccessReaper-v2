"""
Automation endpoints for AccessReaper v2 (Stage 1).
Exposes real-time status of 24-hour automatic audit cycles, countdown info,
and configuration for pausing/resuming with mandatory audit notes.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.scheduler import configure_job
from app.core.security import UserClaims, require_role
from app.db.models import AuditLog, Schedule, utc_now
from app.db.session import get_db
from app.engine.automation import get_automation_status

router = APIRouter()


class AutomationConfigUpdate(BaseModel):
    enabled: bool
    timeOfDay: str = Field(pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", default="02:00")
    note: str | None = None


class LastRunSchema(BaseModel):
    id: str
    at: str
    status: str
    trigger: str
    degradedReason: str | None = None


class AutomationStatusResponse(BaseModel):
    enabled: bool
    intervalHours: int = 24
    timeOfDay: str
    nextRunAt: str | None
    serverTime: str
    secondsUntilNext: int
    lastRun: LastRunSchema | None = None
    catchUpPending: bool
    isRunning: bool
    pauseNote: str | None = None


@router.get("/automation/status", response_model=AutomationStatusResponse)
def get_status(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Returns the current automation status, countdown metrics, and execution health.
    """
    data = get_automation_status(db)
    return AutomationStatusResponse(**data)


class AutoPilotUpdateRequest(BaseModel):
    enabled: bool


@router.get("/automation/autopilot")
def get_autopilot(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    from app.engine.automation import get_autopilot_status

    return get_autopilot_status(db)


@router.put("/automation/autopilot")
def update_autopilot(
    req: AutoPilotUpdateRequest,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    from app.engine.automation import set_autopilot_enabled

    return set_autopilot_enabled(db, req.enabled)


@router.post("/automation/autopilot/enforce")
def trigger_autopilot_enforce(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    from app.engine.automation import enforce_autopilot

    return enforce_autopilot(db, actor=f"{user.name} (Auto-Pilot Trigger)")


@router.post("/automation/trigger")
def trigger_automated_cycle(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    from app.engine.automation import execute_automatic_cycle
    from app.schemas.serializers import serialize_audit_run

    audit_run = execute_automatic_cycle(db, actor=f"Automated audit ({user.name})")
    if not audit_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "AUDIT_IN_PROGRESS",
                    "message": "An IAM audit is already in progress. Please wait for it to complete.",
                }
            },
        )
    return serialize_audit_run(audit_run)


@router.post("/automation/reap")
def trigger_immediate_reap(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Executes an immediate check and revocation of any expired JIT temporary leases.
    """
    from app.engine.automation import process_jit_expirations

    count = process_jit_expirations(db)
    return {"reaped_count": count}





@router.put("/automation/config", response_model=AutomationStatusResponse)
def update_config(
    req: AutomationConfigUpdate,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Updates the 24-hour automatic audit configuration (pause/resume, time of day).
    Pausing requires an explanatory note and appends an immutable audit log event.
    """
    sch = db.query(Schedule).first()
    if not sch:
        sch = Schedule(id=1, enabled=True, frequency="daily", time_of_day="02:00")
        db.add(sch)
        db.commit()
        db.refresh(sch)

    was_enabled = sch.enabled
    new_enabled = req.enabled
    note_cleaned = (req.note or "").strip()

    # Pausing validation
    if not new_enabled:
        if not note_cleaned:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": "NOTE_REQUIRED",
                        "message": "A note explaining the reason for pausing automatic audits is required.",
                    }
                },
            )
        sch.pause_note = note_cleaned
        if was_enabled:
            # Audit log event
            event_id = f"EVT-{int(time.time() * 1000)}"
            db.add(
                AuditLog(
                    id=event_id,
                    actor=user.name,
                    tag="Governance",
                    title="Automatic audits paused",
                    detail=f"Automatic 24-hour IAM audits paused by {user.name}",
                    note=note_cleaned,
                    source="System",
                    assignment_id=None,
                    request_id=None,
                    audit_id=None,
                    before="Enabled (24h recurring)",
                    after="Paused",
                    tone="orange",
                    icon="⏸",
                    mode="DRY_RUN",
                    occurred_at=utc_now(),
                )
            )
            try:
                from app.engine.notification_service import notify_audit_paused
                notify_audit_paused(db, user.name, note_cleaned)
            except Exception:
                pass
    elif was_enabled != new_enabled and new_enabled:
        sch.pause_note = None
        event_id = f"EVT-{int(time.time() * 1000)}"
        resume_note = note_cleaned or "Resumed 24-hour automated IAM audit schedule"
        db.add(
            AuditLog(
                id=event_id,
                actor=user.name,
                tag="Governance",
                title="Automatic audits resumed",
                detail=f"Automatic 24-hour IAM audits resumed at {req.timeOfDay} PKT by {user.name}",
                note=resume_note,
                source="System",
                assignment_id=None,
                request_id=None,
                audit_id=None,
                before="Paused",
                after=f"Enabled (Daily at {req.timeOfDay} PKT)",
                tone="green",
                icon="▶",
                mode="DRY_RUN",
                occurred_at=utc_now(),
            )
        )

    sch.enabled = new_enabled
    sch.frequency = "daily" if new_enabled else "off"
    sch.time_of_day = req.timeOfDay
    sch.updated_at = utc_now()
    sch.updated_by = user.name
    db.commit()

    # Reconfigure scheduler
    configure_job(
        enabled=sch.enabled,
        frequency=sch.frequency,
        time_of_day=sch.time_of_day,
    )

    data = get_automation_status(db)
    return AutomationStatusResponse(**data)


