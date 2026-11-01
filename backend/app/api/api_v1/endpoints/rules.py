"""
Risk rule configuration endpoints for AccessReaper v2.
Allows administrators to inspect, preview, create, and restore versioned risk rule weights.
Ensures pure deterministic evaluation, version immutability, and append-only audit logging.
"""

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.security import UserClaims, require_role
from app.core.time import calculate_days_inactive
from app.db.models import Assignment, AuditLog, RuleConfig, SoDConflict, utc_now
from app.db.session import get_db
from app.engine.scoring import (
    FindingContext,
    IdentityContext,
    ResourceContext,
    evaluate_risk,
    get_default_rule_config,
)
from app.schemas.rules import (
    RuleConfigCreate,
    RuleConfigRead,
    RuleConfigSummary,
    RulePreviewChange,
    RulePreviewRequest,
    RulePreviewResponse,
    RulePreviewSummary,
    SoDConflictCreate,
    SoDConflictSchema,
    SoDConflictUpdate,
)

router = APIRouter()


@router.get("/rules")
def get_rule_configs(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Returns the currently active rule configuration and historical versions.
    """
    active = db.query(RuleConfig).filter(RuleConfig.is_active == True).first()  # noqa: E712
    if not active:
        # Fallback to default v1 if none marked active
        active_payload = get_default_rule_config()
        active_version = 1
        active_read = RuleConfigRead(
            version=active_version,
            payload=active_payload,
            createdBy="System baseline",
            createdAt=utc_now(),
            note="Default baseline rule weights",
            isActive=True,
        )
    else:
        active_read = RuleConfigRead(
            version=active.version,
            payload=active.payload,
            createdBy=active.created_by,
            createdAt=active.created_at,
            note=active.note,
            isActive=True,
        )

    all_configs = db.query(RuleConfig).order_by(RuleConfig.version.desc()).all()
    history = [
        RuleConfigSummary(
            version=rc.version,
            createdBy=rc.created_by,
            createdAt=rc.created_at,
            note=rc.note,
            isActive=rc.is_active,
        )
        for rc in all_configs
    ]

    return {
        "active": active_read,
        "history": history,
    }


@router.post("/rules", response_model=RuleConfigRead, status_code=status.HTTP_201_CREATED)
def create_rule_config_version(
    req: RuleConfigCreate,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Creates a new immutable rule configuration version, deactivates the current active version,
    and logs an audit event.
    """
    max_version = db.query(func.max(RuleConfig.version)).scalar() or 0
    new_version = max_version + 1

    current_active = db.query(RuleConfig).filter(RuleConfig.is_active == True).first()  # noqa: E712
    old_version_str = f"v{current_active.version}" if current_active else "v1"

    if current_active:
        current_active.is_active = False

    payload_dict = req.config.model_dump()
    new_rc = RuleConfig(
        version=new_version,
        payload=payload_dict,
        created_by=user.name,
        created_at=utc_now(),
        note=req.note.strip(),
        is_active=True,
    )
    db.add(new_rc)

    # Append to append-only audit_log
    event_id = f"EVT-{int(time.time() * 1000)}"
    log_entry = AuditLog(
        id=event_id,
        actor=user.name,
        tag="Rules",
        title=f"Risk rule weights updated (v{new_version})",
        detail=f"Rule configuration version {new_version} activated with custom scoring weights",
        note=req.note.strip(),
        source="Risk Engine",
        assignment_id=None,
        request_id=None,
        audit_id=None,
        before=old_version_str,
        after=f"v{new_version}",
        tone="blue",
        icon="⚖",
        mode="DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(new_rc)

    return RuleConfigRead(
        version=new_rc.version,
        payload=new_rc.payload,
        createdBy=new_rc.created_by,
        createdAt=new_rc.created_at,
        note=new_rc.note,
        isActive=new_rc.is_active,
    )


@router.post("/rules/{version}/activate", response_model=RuleConfigRead)
def rollback_rule_config(
    version: int,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Rolls back the active rule configuration to a previously created version.
    """
    target = db.query(RuleConfig).filter(RuleConfig.version == version).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "RULE_VERSION_NOT_FOUND", "message": f"Rule version {version} does not exist."}},
        )

    if target.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "ALREADY_ACTIVE",
                    "message": f"Rule configuration version {version} is already active.",
                }
            },
        )

    current_active = db.query(RuleConfig).filter(RuleConfig.is_active == True).first()  # noqa: E712
    old_version_str = f"v{current_active.version}" if current_active else "v1"

    if current_active:
        current_active.is_active = False

    target.is_active = True

    # Append to append-only audit_log
    event_id = f"EVT-{int(time.time() * 1000)}"
    log_entry = AuditLog(
        id=event_id,
        actor=user.name,
        tag="Rules",
        title=f"Risk rule weights restored (v{version})",
        detail=f"Rolled back active rule configuration to version {version}",
        note=f"Restored rule configuration version {version}",
        source="Risk Engine",
        assignment_id=None,
        request_id=None,
        audit_id=None,
        before=old_version_str,
        after=f"v{version}",
        tone="blue",
        icon="⚖",
        mode="DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(target)

    return RuleConfigRead(
        version=target.version,
        payload=target.payload,
        createdBy=target.created_by,
        createdAt=target.created_at,
        note=target.note,
        isActive=target.is_active,
    )


@router.post("/rules/preview", response_model=RulePreviewResponse)
def preview_rule_impact(
    req: RulePreviewRequest,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Dry preview: Given a candidate rule configuration, evaluates all assignments
    and returns how many would be High/Medium/Low vs current, plus the list of changed assignments.
    WRITES NOTHING to the database.
    """
    assignments = (
        db.query(Assignment)
        .options(
            joinedload(Assignment.identity),
            joinedload(Assignment.resource),
            joinedload(Assignment.finding),
        )
        .all()
    )

    active_config = db.query(RuleConfig).filter(RuleConfig.is_active == True).first()  # noqa: E712
    current_payload = active_config.payload if active_config else get_default_rule_config()
    candidate_payload = req.config.model_dump()

    new_high = 0
    new_medium = 0
    new_low = 0

    curr_high = 0
    curr_medium = 0
    curr_low = 0

    changes: list[RulePreviewChange] = []

    for a in assignments:
        # Current evaluation
        curr_eval = evaluate_risk(
            identity=IdentityContext(
                name=a.identity.name,
                email=a.identity.email,
                job_role=a.identity.job_role,
                team=a.identity.team,
                employment_status=a.identity.employment_status,
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
            finding_context=FindingContext(
                direct_admin_bypass=a.direct_admin_bypass,
                privileged_inactive=a.privileged_inactive,
            ),
            resolved=a.resolved,
            finding_status=a.finding.status if a.finding else "Open",
            rule_config=current_payload,
        )

        # Candidate evaluation
        candidate_eval = evaluate_risk(
            identity=IdentityContext(
                name=a.identity.name,
                email=a.identity.email,
                job_role=a.identity.job_role,
                team=a.identity.team,
                employment_status=a.identity.employment_status,
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
            finding_context=FindingContext(
                direct_admin_bypass=a.direct_admin_bypass,
                privileged_inactive=a.privileged_inactive,
            ),
            resolved=a.resolved,
            finding_status=a.finding.status if a.finding else "Open",
            rule_config=candidate_payload,
        )

        if not a.resolved:
            if curr_eval.risk_level == "High":
                curr_high += 1
            elif curr_eval.risk_level == "Medium":
                curr_medium += 1
            else:
                curr_low += 1

            if candidate_eval.risk_level == "High":
                new_high += 1
            elif candidate_eval.risk_level == "Medium":
                new_medium += 1
            else:
                new_low += 1

            if candidate_eval.risk_level != a.current_risk or candidate_eval.risk_level != curr_eval.risk_level:
                changes.append(
                    RulePreviewChange(
                        assignmentId=a.id,
                        name=a.identity.name,
                        resource=a.resource.name,
                        oldRisk=a.current_risk,
                        newRisk=candidate_eval.risk_level,
                        oldScore=curr_eval.score,
                        newScore=candidate_eval.score,
                    )
                )

    return RulePreviewResponse(
        summary=RulePreviewSummary(
            high=new_high,
            medium=new_medium,
            low=new_low,
            currentHigh=curr_high,
            currentMedium=curr_medium,
            currentLow=curr_low,
        ),
        changes=changes,
    )


# --- Separation of Duties (SoD) Endpoints ---


@router.get("/rules/sod", response_model=list[SoDConflictSchema])
def list_sod_conflicts(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Returns all configured Separation of Duties conflict pairs.
    """
    conflicts = db.query(SoDConflict).order_by(SoDConflict.created_at.asc()).all()
    return [
        SoDConflictSchema(
            id=c.id,
            pattern_a=c.pattern_a,
            access_a=c.access_a,
            pattern_b=c.pattern_b,
            access_b=c.access_b,
            description=c.description,
            points=c.points,
            enabled=c.enabled,
        )
        for c in conflicts
    ]


@router.post("/rules/sod", response_model=SoDConflictSchema, status_code=status.HTTP_201_CREATED)
def create_sod_conflict(
    req: SoDConflictCreate,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Creates a new Separation of Duties conflicting access pair. Requires note and logs audit event.
    """
    new_id = f"sod-{str(uuid.uuid4())[:8]}"
    conflict = SoDConflict(
        id=new_id,
        pattern_a=req.pattern_a.strip(),
        access_a=req.access_a.strip(),
        pattern_b=req.pattern_b.strip(),
        access_b=req.access_b.strip(),
        description=req.description.strip(),
        points=req.points,
        enabled=req.enabled,
        created_at=utc_now(),
    )
    db.add(conflict)

    audit_entry = AuditLog(
        id=f"EVT-SOD-ADD-{int(time.time() * 1000)}",
        actor=user.name or user.email,
        tag="Rules",
        title="SoD conflict rule created",
        detail=f"Created rule '{conflict.description}' ({conflict.pattern_a} {conflict.access_a} + {conflict.pattern_b} {conflict.access_b})",
        note=req.note,
        source="AccessReaper",
        tone="gray",
        icon="✓",
        mode="DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(conflict)

    return SoDConflictSchema(
        id=conflict.id,
        pattern_a=conflict.pattern_a,
        access_a=conflict.access_a,
        pattern_b=conflict.pattern_b,
        access_b=conflict.access_b,
        description=conflict.description,
        points=conflict.points,
        enabled=conflict.enabled,
    )


@router.put("/rules/sod/{id}", response_model=SoDConflictSchema)
def update_sod_conflict(
    id: str,
    req: SoDConflictUpdate,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Updates an existing SoD conflict rule. Requires note and logs audit event.
    """
    conflict = db.query(SoDConflict).filter(SoDConflict.id == id).first()
    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"SoD conflict rule '{id}' not found."}},
        )

    before_desc = f"{conflict.description} (enabled={conflict.enabled}, points={conflict.points})"

    if req.pattern_a is not None:
        conflict.pattern_a = req.pattern_a.strip()
    if req.access_a is not None:
        conflict.access_a = req.access_a.strip()
    if req.pattern_b is not None:
        conflict.pattern_b = req.pattern_b.strip()
    if req.access_b is not None:
        conflict.access_b = req.access_b.strip()
    if req.description is not None:
        conflict.description = req.description.strip()
    if req.points is not None:
        conflict.points = req.points
    if req.enabled is not None:
        conflict.enabled = req.enabled

    after_desc = f"{conflict.description} (enabled={conflict.enabled}, points={conflict.points})"

    audit_entry = AuditLog(
        id=f"EVT-SOD-UPD-{int(time.time() * 1000)}",
        actor=user.name or user.email,
        tag="Rules",
        title="SoD conflict rule updated",
        detail=f"Updated rule '{conflict.id}': {before_desc} -> {after_desc}",
        note=req.note,
        source="AccessReaper",
        before=before_desc,
        after=after_desc,
        tone="gray",
        icon="✓",
        mode="DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(conflict)

    return SoDConflictSchema(
        id=conflict.id,
        pattern_a=conflict.pattern_a,
        access_a=conflict.access_a,
        pattern_b=conflict.pattern_b,
        access_b=conflict.access_b,
        description=conflict.description,
        points=conflict.points,
        enabled=conflict.enabled,
    )


@router.delete("/rules/sod/{id}", status_code=status.HTTP_200_OK)
def delete_sod_conflict(
    id: str,
    note: str = "",
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Deletes an SoD conflict rule. Logs audit event.
    """
    conflict = db.query(SoDConflict).filter(SoDConflict.id == id).first()
    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"SoD conflict rule '{id}' not found."}},
        )

    deleted_desc = f"{conflict.description} ({conflict.pattern_a} + {conflict.pattern_b})"
    db.delete(conflict)

    audit_entry = AuditLog(
        id=f"EVT-SOD-DEL-{int(time.time() * 1000)}",
        actor=user.name or user.email,
        tag="Rules",
        title="SoD conflict rule deleted",
        detail=f"Deleted rule '{id}': {deleted_desc}",
        note=note or "Rule removed by administrator",
        source="AccessReaper",
        tone="orange",
        icon="−",
        mode="DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(audit_entry)
    db.commit()

    return {"status": "ok", "deleted": id}
