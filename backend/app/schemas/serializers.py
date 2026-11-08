"""
Model serializers converting SQLAlchemy models into camelCase API response schemas.
Handles timezone localization for Asia/Karachi display.
"""

from datetime import UTC, datetime

from app.core.time import KARACHI_TZ, calculate_days_inactive
from app.db.models import (
    AccessRequest,
    AIExplanation,
    Assignment,
    AuditLog,
    AuditRun,
    AuditSnapshot,
    Notification,
)
from app.engine.scoring import (
    FindingContext,
    IdentityContext,
    ResourceContext,
    evaluate_risk,
)
from app.schemas.iam import (
    AIExplanationSchema,
    ApprovalSchema,
    AuditRunSchema,
    AuditSnapshotSchema,
    FindingSchema,
    HistoryEventChange,
    HistoryEventSchema,
    NotificationSchema,
    PersonSchema,
    SourceBreakdown,
)


def format_iso_karachi(dt: datetime | None) -> str | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(KARACHI_TZ).isoformat()


def serialize_assignment(assignment: Assignment, ai_explanation: AIExplanation | None = None) -> PersonSchema:
    f = assignment.finding
    ai_exp = ai_explanation or getattr(assignment, "_ai_explanation", None)
    finding_schema = FindingSchema(
        id=f.id if f else assignment.id,
        originalReason=f.original_reason if f else assignment.reason,
        originalSeverity=f.original_severity if f else assignment.current_risk,
        originalAccess=f.original_access if f else assignment.access_level,
        detectedAt=format_iso_karachi(f.detected_at) if f else format_iso_karachi(assignment.created_at),
        status=f.status if f else ("Reviewed" if assignment.resolved else "Open"),
        snapshot=(
            {k: v for k, v in f.snapshot.items() if k != "finding"}
            if (f and isinstance(f.snapshot, dict))
            else (f.snapshot if f else {
                "role": assignment.identity.job_role,
                "team": assignment.identity.team,
                "source": assignment.resource.source,
                "lastActiveAt": format_iso_karachi(assignment.last_active_at),
                "lastActivity": assignment.last_active_text or "Not recorded",
            })
        ),
        evidence=f.evidence if f else [],
        aiExplanation=ai_exp.summary_text if ai_exp else None,
        aiRecommendation=ai_exp.recommendation_text if ai_exp else None,
        aiStatus=ai_exp.status if ai_exp else None,
        aiModel=ai_exp.model if ai_exp else None,
    )

    # Compute deterministic score & breakdown
    is_unmatched = assignment.identity.team == "Unmatched" or (
        assignment.identity.email and assignment.identity.email.endswith("@github.unmatched")
    )
    account_type = getattr(assignment, "_account_type", "user")
    eval_res = evaluate_risk(
        identity=IdentityContext(
            name=assignment.identity.name,
            email=assignment.identity.email,
            job_role=assignment.identity.job_role,
            team=assignment.identity.team,
            employment_status=assignment.identity.employment_status,
            current_project=assignment.identity.current_project,
            is_unmatched=is_unmatched,
            github_login=assignment.github_login,
            account_type=account_type,
            is_outside_collaborator=getattr(assignment, "is_outside_collaborator", False),
        ),
        resource=ResourceContext(
            name=assignment.resource.name,
            source=assignment.resource.source,
            is_sensitive=assignment.resource.is_sensitive,
            project=assignment.resource.project,
            is_archived=getattr(assignment.resource, "is_archived", False),
            admin_count=getattr(assignment, "_admin_count", None),
        ),
        access_level=assignment.access_level,
        last_active_days=calculate_days_inactive(assignment.last_active_at, getattr(assignment, "origin", None)),
        last_activity_text=assignment.last_active_text or "",
        finding_context=FindingContext(
            direct_admin_bypass=assignment.direct_admin_bypass,
            privileged_inactive=assignment.privileged_inactive,
        ),
        resolved=assignment.resolved,
        other_assignments=getattr(assignment, "_other_assignments", None),
    )
    score_val = eval_res.score
    breakdown = [{"code": r.code, "name": r.name, "points": r.points, "reason": r.reason} for r in eval_res.fired_rules]

    calculated_days = calculate_days_inactive(assignment.last_active_at, getattr(assignment, "origin", None))
    display_last = assignment.last_active_text
    if not display_last or display_last == "Not recorded":
        if calculated_days is not None:
            if calculated_days == 0:
                display_last = "Today"
            elif calculated_days == 1:
                display_last = "1 day ago"
            elif calculated_days >= 30:
                display_last = f"{calculated_days} days ago (Dormant)"
            else:
                display_last = f"{calculated_days} days ago"
        elif assignment.last_active_at:
            display_last = "Recent"
        else:
            display_last = "Active"

    return PersonSchema(
        id=assignment.id,
        name=assignment.identity.name,
        email=assignment.identity.email,
        initials=assignment.identity.initials,
        role=assignment.identity.job_role,
        team=assignment.identity.team,
        repo=assignment.resource.name,
        source=assignment.resource.source,
        access=assignment.access_level,
        risk=assignment.current_risk,
        last=display_last,
        lastActiveAt=format_iso_karachi(assignment.last_active_at),
        reason=assignment.reason,
        resolved=assignment.resolved,
        reviewedAt=assignment.reviewed_at,
        isTemporary=getattr(assignment, "is_temporary", False) or False,
        expiresAt=format_iso_karachi(getattr(assignment, "expires_at", None)),
        employmentStatus=getattr(assignment.identity, "employment_status", None),
        finding=finding_schema,
        score=score_val,
        scoreBreakdown=breakdown,
    )


def serialize_approval(req: AccessRequest) -> ApprovalSchema:
    gh_login = None
    is_new = False
    if req.identity:
        if req.identity.assignments:
            for a in req.identity.assignments:
                if a.github_login:
                    gh_login = a.github_login
                    break
        if not gh_login and req.identity.email:
            try:
                from app.db.session import SessionLocal
                from app.db.models import GitHubIdentityMap
                _db = SessionLocal()
                m = _db.query(GitHubIdentityMap).filter(GitHubIdentityMap.email == req.identity.email.lower()).first()
                if m:
                    gh_login = m.login
                _db.close()
            except Exception:
                pass
        has_active = any(a.external_status == "active" for a in req.identity.assignments) if req.identity.assignments else False
        if not has_active or req.identity.team == "Unmatched" or req.identity.email.endswith("@payhive.internal") or req.identity.email.endswith("@github.unmatched"):
            is_new = True

    return ApprovalSchema(
        id=req.id,
        person=req.identity.name,
        email=req.identity.email,
        initials=req.identity.initials,
        repo=req.resource.name,
        access=req.requested_access,
        reason=req.business_reason,
        requested=req.requested_text or "Recently",
        requestedAt=format_iso_karachi(req.requested_at),
        durationHours=getattr(req, "duration_hours", None),
        expiresAt=format_iso_karachi(getattr(req, "expires_at", None)),
        type=req.type,
        risk=req.risk,
        status=req.status,
        githubLogin=gh_login,
        isNewEmployee=is_new,
    )


def serialize_audit_log(evt: AuditLog) -> HistoryEventSchema:
    dt = evt.occurred_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    local_dt = dt.astimezone(KARACHI_TZ)

    date_str = local_dt.strftime("%Y-%m-%d")
    time_str = local_dt.strftime("%I:%M %p").lstrip("0")
    month_name = local_dt.strftime("%B")
    day_num = local_dt.strftime("%d").lstrip("0")

    # Friendly day string (e.g. "Today, October 14", "Yesterday, October 13", "October 2, 2026")
    anchor_day = "2026-10-14"
    if date_str == anchor_day:
        day_str = f"Today, {month_name} {day_num}"
    elif date_str == "2026-10-13":
        day_str = f"Yesterday, {month_name} {day_num}"
    else:
        day_str = f"{month_name} {day_num}, {local_dt.year}"

    changes = []
    if evt.before is not None and evt.after is not None:
        changes.append(HistoryEventChange(field="Permission", before=evt.before, after=evt.after))

    return HistoryEventSchema(
        id=evt.id,
        day=day_str,
        date=date_str,
        time=time_str,
        occurredAt=local_dt.isoformat(),
        icon=evt.icon,
        tone=evt.tone,
        title=evt.title,
        actor=evt.actor,
        detail=evt.detail,
        tag=evt.tag,
        note=evt.note or "",
        source=evt.source or "",
        assignmentId=evt.assignment_id,
        requestId=evt.request_id,
        auditId=evt.audit_id,
        before=evt.before,
        after=evt.after,
        mode=evt.mode or "LIVE_GITHUB",
        changes=changes,
    )


def serialize_ai_explanation(exp: AIExplanation | None) -> AIExplanationSchema | None:
    if not exp:
        return None
    return AIExplanationSchema(
        id=exp.id,
        runId=exp.run_id,
        findingId=exp.finding_id,
        summaryText=exp.summary_text,
        recommendationText=exp.recommendation_text,
        model=exp.model,
        status=exp.status,
        generatedAt=format_iso_karachi(exp.generated_at) or "",
    )


def serialize_audit_run(run: AuditRun, ai_summary: AIExplanation | None = None) -> AuditRunSchema:
    sources = [
        SourceBreakdown(
            source=s.get("source", ""),
            assignments=s.get("assignments", 0),
            resources=s.get("resources", 0),
        )
        for s in (run.sources or [])
    ]
    summary_obj = ai_summary or getattr(run, "_ai_summary", None)
    serialized_ai = serialize_ai_explanation(summary_obj)

    return AuditRunSchema(
        id=run.id,
        completedAt=format_iso_karachi(run.completed_at),
        status=run.status,
        actor=run.actor,
        scope=run.scope or ["GitHub", "Firestore"],
        assignments=run.assignments,
        identities=run.identities,
        high=run.high,
        medium=run.medium,
        healthy=run.healthy,
        resolved=run.resolved,
        sources=sources,
        sample=run.sample,
        mode=run.mode,
        ruleVersion=getattr(run, "rule_version", 1),
        trigger=getattr(run, "trigger", "manual"),
        degradedReason=getattr(run, "degraded_reason", None),
        aiSummary=serialized_ai,
    )


def serialize_notification(n: Notification) -> NotificationSchema:
    return NotificationSchema(
        id=n.id,
        eventType=n.event_type,
        title=n.title,
        message=n.message,
        link=n.link,
        isRead=n.is_read,
        createdAt=format_iso_karachi(n.created_at) or "",
    )


def serialize_audit_snapshot(s: AuditSnapshot) -> AuditSnapshotSchema:
    return AuditSnapshotSchema(
        at=format_iso_karachi(s.at),
        label=s.label,
        high=s.high,
        medium=s.medium,
        healthy=s.healthy,
        resolved=s.resolved,
        assignments=s.assignments,
        remediated=s.remediated,
    )
