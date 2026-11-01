"""
Dashboard summary metrics and trend history endpoints.
Filters metrics according to workspace dataMode ('sample' or 'live').
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.security import UserClaims, require_role
from app.core.time import KARACHI_TZ
from app.db.models import (
    AccessRequest,
    Assignment,
    AuditSnapshot,
    Setting,
)
from app.db.session import get_db
from app.engine.scoring import calculate_security_health_score
from app.schemas.iam import DashboardSummary, TrendPoint

router = APIRouter()


def _get_data_mode(db: Session) -> str:
    setting = db.query(Setting).filter(Setting.key == "dataMode").first()
    return setting.value if setting and setting.value in ("sample", "live") else "sample"


@router.get("/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    data_mode = _get_data_mode(db)

    if data_mode == "live":
        assignments = (
            db.query(Assignment)
            .options(joinedload(Assignment.resource))
            .filter(Assignment.origin == "github", Assignment.external_status != "revoked_externally")
            .all()
        )
    else:
        assignments = (
            db.query(Assignment).options(joinedload(Assignment.resource)).filter(Assignment.origin == "sample").all()
        )

    total_assignments = len(assignments)
    distinct_identities = len({a.identity_id for a in assignments})
    github_count = sum(1 for a in assignments if a.resource.source == "GitHub")
    firestore_count = sum(1 for a in assignments if a.resource.source == "Firestore")

    open_high = sum(1 for a in assignments if not a.resolved and a.current_risk == "High")
    open_medium = sum(1 for a in assignments if not a.resolved and a.current_risk == "Medium")
    healthy = sum(1 for a in assignments if not a.resolved and a.current_risk == "Low")
    resolved = sum(1 for a in assignments if a.resolved)

    pending_approvals = db.query(AccessRequest).filter(AccessRequest.status == "Pending").count()

    health_info = calculate_security_health_score(assignments, pending_count=pending_approvals)

    return DashboardSummary(
        identities=distinct_identities,
        assignments=total_assignments,
        github=github_count,
        firestore=firestore_count,
        high=open_high,
        medium=open_medium,
        healthy=healthy,
        resolved=resolved,
        pending=pending_approvals,
        healthScore=health_info["score"],
        healthGrade=health_info["grade"],
        healthStatus=health_info["status"],
        activeJitCount=health_info["activeJitCount"],
        dormantCount=health_info["dormantCount"],
    )


@router.get("/dashboard/trend", response_model=list[TrendPoint])
def get_dashboard_trend(
    days: int = Query(7),
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    if days not in (7, 30, 90):
        days = 7
    """
    Computes daily trend snapshots matching the frontend trend chart calculation.
    """
    snapshots = db.query(AuditSnapshot).order_by(AuditSnapshot.at.asc()).all()

    # Anchor to 2026-10-14 in Karachi timezone (matching the app's anchor date)
    anchor_date = datetime(2026, 10, 14, 12, 0, tzinfo=KARACHI_TZ)
    end_date = anchor_date.date()

    # Group snapshots by day (Karachi date)
    by_day = {}
    for s in snapshots:
        s_dt = s.at
        if s_dt.tzinfo is None:
            s_dt = s_dt.replace(tzinfo=UTC)
        k_date = s_dt.astimezone(KARACHI_TZ).date()
        # Keep latest snapshot for that date
        by_day[k_date] = s

    result: list[TrendPoint] = []
    for i in range(days):
        day_date = end_date - timedelta(days=(days - 1 - i))
        day_str = day_date.strftime("%Y-%m-%d")
        snap = by_day.get(day_date)
        if snap:
            result.append(TrendPoint(date=day_str, high=snap.high, remediated=snap.remediated))
        else:
            result.append(TrendPoint(date=day_str, high=None, remediated=None))

    return result
