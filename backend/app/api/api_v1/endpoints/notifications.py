"""
Notification endpoints for AccessReaper v2 (Stage 4).
Supports in-app notification center (listing, unread count, mark read, mark all read),
user notification preferences (daily email digest opt-in/opt-out),
and test email dispatch.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import UserClaims, require_role
from app.db.session import get_db
from app.engine.email_service import is_smtp_configured, send_test_email
from app.engine.notification_service import (
    get_or_create_preferences,
    get_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)
from app.schemas.iam import (
    NotificationPreferenceSchema,
    NotificationsResponse,
    TestEmailResponse,
)
from app.schemas.serializers import serialize_notification

logger = logging.getLogger("accessreaper.notifications_api")

router = APIRouter()


class NotificationPreferenceUpdate(BaseModel):
    emailDigestEnabled: bool


class PreferenceWithStatus(NotificationPreferenceSchema):
    smtpConfigured: bool


@router.get("/notifications", response_model=NotificationsResponse)
def list_notifications(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Retrieves in-app notifications and unread badge count for the active administrator.
    """
    unread_count, notifs = get_user_notifications(db=db, admin_email=user.email)
    return NotificationsResponse(
        unreadCount=unread_count,
        notifications=[serialize_notification(n) for n in notifs],
    )


@router.post("/notifications/{id}/read")
def mark_read(
    id: str,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Marks a single notification as read.
    """
    ok = mark_notification_read(db=db, notification_id=id, admin_email=user.email)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Notification not found."}},
        )
    return {"success": True, "id": id}


@router.post("/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Marks all notifications for this administrator as read.
    """
    count = mark_all_notifications_read(db=db, admin_email=user.email)
    return {"success": True, "markedRead": count}


@router.get("/notifications/preferences", response_model=PreferenceWithStatus)
def get_preferences(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Returns the administrator's email digest preference and SMTP configuration status.
    """
    pref = get_or_create_preferences(db=db, admin_email=user.email)
    return PreferenceWithStatus(
        emailDigestEnabled=pref.email_digest_enabled,
        inAppEnabled=pref.in_app_enabled,
        smtpConfigured=is_smtp_configured(),
    )


@router.put("/notifications/preferences", response_model=PreferenceWithStatus)
def update_preferences(
    body: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Updates the administrator's notification preferences.
    """
    pref = get_or_create_preferences(db=db, admin_email=user.email)
    pref.email_digest_enabled = body.emailDigestEnabled
    db.commit()
    db.refresh(pref)
    return PreferenceWithStatus(
        emailDigestEnabled=pref.email_digest_enabled,
        inAppEnabled=pref.in_app_enabled,
        smtpConfigured=is_smtp_configured(),
    )


@router.post("/notifications/test-email", response_model=TestEmailResponse)
def trigger_test_email(
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Dispatches a test notification email to the current administrator.
    Safely verifies SMTP reachability without exposing secrets.
    """
    target_email = user.email
    if not target_email or target_email.endswith(".corp") or target_email.endswith("@example.com"):
        target_email = settings.SMTP_USER or user.email or "admin@acme.corp"
    result = send_test_email(to_email=target_email)
    return TestEmailResponse(
        success=result["success"],
        configured=result["configured"],
        message=result["message"],
    )
