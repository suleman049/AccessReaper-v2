"""
In-App Notification Service for AccessReaper v2.
Manages notification dispatch, retrieval, read state, and lifecycle events:
- audit completed
- high findings flagged
- approvals pending > 24 hours
- sync degraded / failed
- automatic audits paused
- new user pending activation
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import (
    AccessRequest,
    AuditRun,
    Notification,
    NotificationPreference,
    utc_now,
)

logger = logging.getLogger("accessreaper.notifications")


def create_notification(
    db: Session,
    admin_email: str,
    event_type: str,
    title: str,
    message: str,
    link: str | None = None,
) -> Notification:
    notif = Notification(
        id=f"NOTIF-{uuid.uuid4().hex[:12]}",
        admin_email=admin_email,
        event_type=event_type,
        title=title,
        message=message,
        link=link,
        is_read=False,
        created_at=datetime.now(UTC),
    )
    db.add(notif)
    try:
        db.commit()
        db.refresh(notif)
    except Exception:
        db.flush()
    return notif


def broadcast_notification(
    db: Session,
    event_type: str,
    title: str,
    message: str,
    link: str | None = None,
) -> Notification:
    """Creates a broadcast notification intended for all workspace administrators."""
    return create_notification(
        db=db,
        admin_email="*",
        event_type=event_type,
        title=title,
        message=message,
        link=link,
    )


def notify_audit_completed(db: Session, run: AuditRun) -> list[Notification]:
    notifs = []
    # 1. Audit completed notification
    n1 = broadcast_notification(
        db=db,
        event_type="audit_completed",
        title="Access audit completed",
        message=f"Audit {run.id} completed ({run.assignments} assignments checked; {run.high} High, {run.medium} Medium).",
        link="#audit",
    )
    notifs.append(n1)

    # 2. High findings alert if high > 0
    if run.high > 0:
        n2 = broadcast_notification(
            db=db,
            event_type="high_findings",
            title=f"{run.high} High-risk findings require review",
            message=f"{run.high} assignments hold critical privilege discrepancies that require immediate review.",
            link="#audit",
        )
        notifs.append(n2)

    # 3. Degraded notification if applicable
    if run.status == "Degraded" and run.degraded_reason:
        n3 = broadcast_notification(
            db=db,
            event_type="sync_degraded",
            title="Audit completed with degraded sync",
            message=f"Audit {run.id} operated in degraded mode: {run.degraded_reason}",
            link="#settings",
        )
        notifs.append(n3)

    return notifs


def notify_audit_paused(db: Session, actor: str, note: str) -> Notification:
    return broadcast_notification(
        db=db,
        event_type="audit_paused",
        title="Automatic audits paused",
        message=f"Automatic audits were paused by {actor}. Note: {note}",
        link="#settings",
    )


def notify_user_pending_activation(db: Session, user_email: str) -> Notification:
    return broadcast_notification(
        db=db,
        event_type="user_pending_activation",
        title="New user awaiting activation",
        message=f"New workspace user {user_email} is pending administrator review and activation.",
        link="#users",
    )


def check_and_notify_overdue_approvals(db: Session) -> list[Notification]:
    """
    Checks for approvals pending older than 24 hours that haven't been notified yet.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    pending_overdue = (
        db.query(AccessRequest)
        .filter(AccessRequest.status == "Pending", AccessRequest.requested_at <= cutoff)
        .all()
    )

    created_notifs = []
    for req in pending_overdue:
        # Check if we already notified for this request in the last 24 hours
        already_notified = (
            db.query(Notification)
            .filter(
                Notification.event_type == "approval_overdue",
                Notification.message.like(f"%{req.id}%"),
                Notification.created_at >= cutoff,
            )
            .first()
        )
        if not already_notified:
            n = broadcast_notification(
                db=db,
                event_type="approval_overdue",
                title="Pending access approval overdue",
                message=f"Approval request [{req.id}] for {req.identity.name} ({req.requested_access} on {req.resource.name}) has been pending > 24 hours.",
                link="#approvals",
            )
            created_notifs.append(n)

    return created_notifs


def get_user_notifications(db: Session, admin_email: str, limit: int = 40) -> tuple[int, list[Notification]]:
    """
    Returns unread count and most recent notifications applicable to this admin.
    """
    query = db.query(Notification).filter(
        (Notification.admin_email == admin_email) | (Notification.admin_email == "*")
    ).order_by(Notification.created_at.desc())

    all_notifs = query.limit(limit).all()
    unread_count = (
        db.query(Notification)
        .filter(
            ((Notification.admin_email == admin_email) | (Notification.admin_email == "*")),
            Notification.is_read.is_(False),
        )
        .count()
    )

    return unread_count, all_notifs


def mark_notification_read(db: Session, notification_id: str, admin_email: str) -> bool:
    notif = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            ((Notification.admin_email == admin_email) | (Notification.admin_email == "*")),
        )
        .first()
    )
    if notif:
        notif.is_read = True
        db.commit()
        return True
    return False


def mark_all_notifications_read(db: Session, admin_email: str) -> int:
    notifs = (
        db.query(Notification)
        .filter(
            ((Notification.admin_email == admin_email) | (Notification.admin_email == "*")),
            Notification.is_read.is_(False),
        )
        .all()
    )
    count = len(notifs)
    for n in notifs:
        n.is_read = True
    db.commit()
    return count


def get_or_create_preferences(db: Session, admin_email: str) -> NotificationPreference:
    pref = db.query(NotificationPreference).filter(NotificationPreference.admin_email == admin_email).first()
    if not pref:
        pref = NotificationPreference(
            admin_email=admin_email,
            email_digest_enabled=True,
            in_app_enabled=True,
            updated_at=utc_now(),
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref
