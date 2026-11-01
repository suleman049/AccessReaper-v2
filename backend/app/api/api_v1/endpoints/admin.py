"""
Admin operations for development environment.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import UserClaims, require_role
from app.db.models import AuditLog, utc_now
from app.db.seed import seed_database
from app.db.session import get_db

router = APIRouter()


@router.post("/admin/reset-sample")
def reset_sample_data(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Restores seed assignments and requests.
    Permitted only in ENV=dev.
    The audit log remains strictly append-only; an audit reset event is recorded first.
    """
    if settings.ENV != "dev":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Sample data reset is only available in development environment.",
                }
            },
        )

    # 1. Record reset audit event first (audit log is strictly append-only)
    event_id = f"EVT-{int(time.time() * 1000)}"
    reset_event = AuditLog(
        id=event_id,
        actor=user.name,
        tag="Audit",
        title="Sample workspace reset",
        detail="Sample assignments and requests restored to baseline",
        note="Administrative reset executed",
        source="System",
        assignment_id=None,
        request_id=None,
        audit_id=None,
        before=None,
        after=None,
        tone="gray",
        icon="↻",
        mode="DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(reset_event)
    db.commit()

    # 2. Reset mutable tables and reseed
    seed_database(db, reset_mode=True)

    return {
        "status": "ok",
        "message": "Sample assignments, audits and decisions restored.",
    }
