"""
Bootstrap endpoint: provides all workspace data in a single payload for frontend initialization.
Filters assignments according to workspace dataMode ('sample' or 'live').
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.core.security import UserClaims, require_role
from app.db.models import (
    AccessRequest,
    AIExplanation,
    Assignment,
    AuditLog,
    AuditRun,
    AuditSnapshot,
    GitHubIdentityMap,
    Setting,
)
from app.db.session import get_db
from app.engine.automation import get_automation_status
from app.schemas.iam import BootstrapResponse
from app.schemas.serializers import (
    serialize_approval,
    serialize_assignment,
    serialize_audit_log,
    serialize_audit_run,
    serialize_audit_snapshot,
)

router = APIRouter()


def _get_data_mode(db: Session) -> str:
    setting = db.query(Setting).filter(Setting.key == "dataMode").first()
    return setting.value if setting and setting.value in ("sample", "live") else "sample"


@router.get("/bootstrap", response_model=BootstrapResponse)
def get_bootstrap_data(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    data_mode = _get_data_mode(db)

    # 1. Assignments filtered by data_mode
    if data_mode == "live":
        query = db.query(Assignment).filter(
            Assignment.origin == "github",
            Assignment.external_status != "revoked_externally",
        )
    else:
        query = db.query(Assignment).filter(Assignment.origin == "sample")

    assignments = (
        query.options(
            joinedload(Assignment.identity),
            joinedload(Assignment.resource),
            joinedload(Assignment.finding),
        )
        .order_by(Assignment.id.asc())
        .all()
    )
    finding_explanations = {
        exp.finding_id: exp
        for exp in db.query(AIExplanation).filter(AIExplanation.finding_id.isnot(None)).all()
    }
    people = [serialize_assignment(a, finding_explanations.get(a.id)) for a in assignments]

    # 2. Approvals
    requests = (
        db.query(AccessRequest)
        .options(
            joinedload(AccessRequest.identity),
            joinedload(AccessRequest.resource),
        )
        .order_by(AccessRequest.requested_at.desc())
        .all()
    )
    approvals = [serialize_approval(r) for r in requests]

    # 3. History
    events = db.query(AuditLog).order_by(AuditLog.occurred_at.desc()).all()
    history = [serialize_audit_log(e) for e in events]

    # 4. Audit runs
    runs = (
        db.query(AuditRun)
        .filter(AuditRun.sample == False)
        .order_by(AuditRun.completed_at.asc())
        .all()
        if data_mode == "live"
        else db.query(AuditRun).order_by(AuditRun.completed_at.asc()).all()
    )
    run_summaries = {
        exp.run_id: exp
        for exp in db.query(AIExplanation).filter(AIExplanation.finding_id.is_(None)).all()
    }
    audit_runs = [serialize_audit_run(r, run_summaries.get(r.id)) for r in runs]

    # 5. Snapshots
    snapshots = (
        db.query(AuditSnapshot)
        .filter(~AuditSnapshot.label.ilike("%sample%"))
        .order_by(AuditSnapshot.at.asc())
        .all()
        if data_mode == "live"
        else db.query(AuditSnapshot).order_by(AuditSnapshot.at.asc()).all()
    )
    audit_snapshots = [serialize_audit_snapshot(s) for s in snapshots]

    # 6. Last audit setting
    last_audit_setting = db.query(Setting).filter(Setting.key == "lastAudit").first()
    last_audit = last_audit_setting.value if last_audit_setting else "Just now"

    # 7. LLM Provider Status
    from app.services.llm.manager import llm_manager
    llm_status = llm_manager.get_status(db)

    # 8. GitHub accounts with hidden/unmatched emails
    unmatched_maps = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.email.is_(None)).all()
    unmatched_github = [
        {
            "login": m.login,
            "name": m.login,
            "account_type": m.account_type,
            "assignments_count": db.query(Assignment).filter(
                Assignment.origin == "github",
                Assignment.github_login == m.login,
                Assignment.external_status == "active",
            ).count(),
        }
        for m in unmatched_maps
    ]

    return BootstrapResponse(
        people=people,
        approvals=approvals,
        history=history,
        auditRuns=audit_runs,
        auditSnapshots=audit_snapshots,
        lastAudit=last_audit,
        dataMode=data_mode,
        automation=get_automation_status(db),
        llmStatus=llm_status,
        unmatchedGitHub=unmatched_github,
    )
