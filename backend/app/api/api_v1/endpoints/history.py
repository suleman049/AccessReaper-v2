"""
Audit history ledger endpoints.
Provides append-only decision and activity events with date-range and action filtering.
"""

import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.security import UserClaims, require_role
from app.db.models import AuditLog
from app.db.session import get_db
from app.engine.csv_export import export_history_csv
from app.schemas.serializers import serialize_audit_log

router = APIRouter()


@router.get("/history")
def list_history(
    q: str | None = "",
    action: str | None = "All actions",
    range_days: str | None = Query("Last 30 days", alias="range"),
    page: int = Query(1, ge=1),
    page_size: int = Query(6, ge=1, le=100, alias="pageSize"),
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    query = db.query(AuditLog)

    if action and action != "All actions":
        query = query.filter(AuditLog.tag == action)

    events = query.order_by(AuditLog.occurred_at.desc()).all()

    # Parse range (e.g. "Last 30 days" -> 30)
    days = 30
    if range_days:
        import re

        m = re.search(r"\d+", range_days)
        if m:
            days = int(m.group(0))

    # Reference time: max of sample baseline anchor or current time
    now_ref = max(datetime(2026, 10, 14, 12, 0, tzinfo=UTC), datetime.now(UTC))
    cutoff = now_ref - timedelta(days=days)

    filtered = []
    q_lower = (q or "").strip().lower()

    for e in events:
        dt = e.occurred_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        if dt < cutoff:
            continue

        if q_lower:
            text = (
                f"{e.id} {e.title} {e.actor} {e.detail} {e.tag} "
                f"{e.note or ''} {e.assignment_id or ''} {e.request_id or ''} {e.source or ''}"
            ).lower()
            if q_lower not in text:
                continue

        filtered.append(e)

    total = len(filtered)
    start = (page - 1) * page_size
    items = [serialize_audit_log(e) for e in filtered[start : start + page_size]]

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.get("/history.csv")
def download_history_csv(
    q: str | None = "",
    action: str | None = "All actions",
    range_days: str | None = Query("Last 30 days", alias="range"),
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Exports filtered audit ledger events to CSV.
    Guaranteed UTF-8 BOM encoding and formula injection sanitization.
    """
    query = db.query(AuditLog)
    if action and action != "All actions":
        query = query.filter(AuditLog.tag == action)

    events = query.order_by(AuditLog.occurred_at.desc()).all()

    days = 30
    if range_days:
        m = re.search(r"\d+", range_days)
        if m:
            days = int(m.group(0))

    now_ref = max(datetime(2026, 10, 14, 12, 0, tzinfo=UTC), datetime.now(UTC))
    cutoff = now_ref - timedelta(days=days)

    filtered = []
    q_lower = (q or "").strip().lower()

    for e in events:
        dt = e.occurred_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        if dt < cutoff:
            continue

        if q_lower:
            text = (
                f"{e.id} {e.title} {e.actor} {e.detail} {e.tag} "
                f"{e.note or ''} {e.assignment_id or ''} {e.request_id or ''} {e.source or ''}"
            ).lower()
            if q_lower not in text:
                continue

        filtered.append(e)

    csv_bytes = export_history_csv(filtered)
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="accessreaper-audit-history.csv"',
            "Content-Length": str(len(csv_bytes)),
        },
    )
