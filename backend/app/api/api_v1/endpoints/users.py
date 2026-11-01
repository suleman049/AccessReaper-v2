"""
User management endpoints for AccessReaper v2.
Allows administrators to list, activate, deactivate, and reject workspace user profiles in Firestore.
Safely handles missing service account credentials and protects against self-deactivation and orphan orgs.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.firebase_admin_client import (
    get_firestore_admin_client,
    is_service_account_configured,
    revoke_user_refresh_tokens,
)
from app.core.security import UserClaims, clear_profile_cache, require_role
from app.db.models import AuditLog, utc_now
from app.db.session import get_db

router = APIRouter()


class UserActionRequest(BaseModel):
    note: str = Field(min_length=1, max_length=500, description="Audit reason for access change")


class UserProfileItem(BaseModel):
    uid: str
    name: str
    email: str
    role: str
    status: str
    organizationId: str
    createdAt: str | None = None


class UserListResponse(BaseModel):
    configured: bool
    message: str | None = None
    users: list[UserProfileItem] = []


def _get_firestore_or_503():
    if not is_service_account_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "SERVICE_ACCOUNT_UNCONFIGURED",
                    "message": "Firebase service account not configured. Save your key to backend/secrets/firebase-service-account.json.",
                }
            },
        )
    client = get_firestore_admin_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "FIRESTORE_CLIENT_ERROR",
                    "message": "Could not connect to Firestore administration client.",
                }
            },
        )
    return client


@router.get("/users", response_model=UserListResponse)
def list_workspace_users(
    status_filter: str = Query("all", alias="status"),
    q: str = Query("", alias="q"),
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Lists user profiles for organization acme from Firestore.
    Returns configured: false if the service account key is missing.
    """
    if not is_service_account_configured():
        return UserListResponse(
            configured=False,
            message="Firebase service account not configured. Save your service account private key JSON file to backend/secrets/firebase-service-account.json to manage workspace users.",
            users=[],
        )

    client = get_firestore_admin_client()
    if client is None:
        return UserListResponse(
            configured=False,
            message="Could not initialize Firestore admin client.",
            users=[],
        )

    try:
        users_ref = client.collection("users")
        # Fetch all user documents
        docs = users_ref.stream()

        results: list[UserProfileItem] = []
        q_lower = q.strip().lower()

        for doc in docs:
            data = doc.to_dict() or {}
            # Filter strictly to organization
            org_id = data.get("organizationId", "")
            if org_id not in (settings.ORGANIZATION_ID, "acme", "payhive-eng"):
                continue

            user_status = data.get("status", "pending")
            # Apply status filter
            if status_filter != "all":
                if status_filter == "pending" and user_status != "pending":
                    continue
                elif status_filter == "active" and user_status != "active":
                    continue
                elif status_filter == "disabled" and user_status not in ("disabled", "rejected"):
                    continue

            name = data.get("name", "")
            email = data.get("email", "")

            # Apply search filter
            if q_lower:
                if q_lower not in name.lower() and q_lower not in email.lower():
                    continue

            created_at = data.get("createdAt")
            created_at_str = str(created_at) if created_at is not None else None

            results.append(
                UserProfileItem(
                    uid=doc.id,
                    name=name,
                    email=email,
                    role=data.get("role", "pending"),
                    status=user_status,
                    organizationId=org_id,
                    createdAt=created_at_str,
                )
            )

        # Sort: pending first, then by createdAt desc
        results.sort(
            key=lambda x: (
                0 if x.status == "pending" else 1,
                x.createdAt or "",
            ),
            reverse=True,
        )

        return UserListResponse(configured=True, users=results)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "FIRESTORE_QUERY_FAILED", "message": f"Failed to list users: {exc}"}},
        )


@router.post("/users/{uid}/activate")
def activate_user(
    uid: str,
    action: UserActionRequest,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Activates a user account, setting role: admin, status: active in Firestore.
    Writes an append-only audit log entry and clears the profile cache.
    """
    client = _get_firestore_or_503()
    doc_ref = client.collection("users").document(uid)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "USER_NOT_FOUND", "message": f"User {uid} not found."}},
        )

    data = doc.to_dict() or {}
    if data.get("organizationId") not in (settings.ORGANIZATION_ID, "acme", "payhive-eng"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": f"User does not belong to organization '{settings.ORGANIZATION_ID}'."}},
        )

    old_status = str(data.get("status", "pending"))
    target_email = data.get("email", uid)
    target_name = data.get("name", target_email)

    # Update Firestore document
    doc_ref.update({"role": "admin", "status": "active"})

    # Clear profile cache for uid
    clear_profile_cache(uid)

    # Append audit log entry
    event_id = f"EVT-{int(time.time() * 1000)}"
    log_entry = AuditLog(
        id=event_id,
        actor=user.name,
        tag="User access",
        title=f"User activated: {target_name}",
        detail=f"Activated admin access for {target_email} ({uid})",
        note=action.note.strip(),
        source="Firebase Auth",
        assignment_id=None,
        request_id=None,
        audit_id=None,
        before=old_status,
        after="active",
        tone="green",
        icon="✓",
        mode="DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(log_entry)
    db.commit()

    return {
        "status": "success",
        "message": f"User {target_email} activated successfully.",
        "uid": uid,
        "role": "admin",
        "newStatus": "active",
    }


@router.post("/users/{uid}/deactivate")
def deactivate_user(
    uid: str,
    action: UserActionRequest,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Deactivates a user account, setting status: disabled in Firestore.
    Revokes user refresh tokens, writes an append-only audit log entry.
    Protects against self-deactivation and deactivating the last active administrator.
    """
    client = _get_firestore_or_503()

    # Safety Rule 1: Admin cannot deactivate themselves
    if uid == user.uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "SELF_DEACTIVATION_FORBIDDEN",
                    "message": "Admins cannot deactivate their own account.",
                }
            },
        )

    doc_ref = client.collection("users").document(uid)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "USER_NOT_FOUND", "message": f"User {uid} not found."}},
        )

    data = doc.to_dict() or {}
    if data.get("organizationId") not in (settings.ORGANIZATION_ID, "acme", "payhive-eng"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": f"User does not belong to organization '{settings.ORGANIZATION_ID}'."}},
        )

    target_email = data.get("email", "")
    if target_email and target_email.lower() == user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "SELF_DEACTIVATION_FORBIDDEN",
                    "message": "Admins cannot deactivate their own account.",
                }
            },
        )

    # Safety Rule 2: Never allow the last active administrator to be deactivated
    # Count active admin accounts in 'acme'
    active_admins = 0
    all_users = client.collection("users").stream()
    for u in all_users:
        udata = u.to_dict() or {}
        if (
            udata.get("organizationId") == settings.ORGANIZATION_ID
            and udata.get("role") == "admin"
            and udata.get("status") == "active"
        ):
            active_admins += 1

    if active_admins <= 1 and data.get("status") == "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "LAST_ADMIN_PROTECTION",
                    "message": f"Cannot deactivate the last active administrator for organization '{settings.ORGANIZATION_ID}'.",
                }
            },
        )

    old_status = str(data.get("status", "active"))
    target_email = data.get("email", uid)
    target_name = data.get("name", target_email)

    # Update document status to disabled (role stays admin)
    doc_ref.update({"status": "disabled"})

    # Revoke Firebase refresh tokens to immediately terminate sessions
    revoke_user_refresh_tokens(uid)

    # Clear profile cache
    clear_profile_cache(uid)

    # Append audit log entry
    event_id = f"EVT-{int(time.time() * 1000)}"
    log_entry = AuditLog(
        id=event_id,
        actor=user.name,
        tag="User access",
        title=f"User deactivated: {target_name}",
        detail=f"Deactivated access and revoked refresh tokens for {target_email} ({uid})",
        note=action.note.strip(),
        source="Firebase Auth",
        assignment_id=None,
        request_id=None,
        audit_id=None,
        before=old_status,
        after="disabled",
        tone="gray",
        icon="−",
        mode="DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(log_entry)
    db.commit()

    return {
        "status": "success",
        "message": f"User {target_email} deactivated successfully.",
        "uid": uid,
        "newStatus": "disabled",
    }


@router.post("/users/{uid}/reject")
def reject_user(
    uid: str,
    action: UserActionRequest,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Rejects a pending user signup, setting status: rejected in Firestore.
    """
    client = _get_firestore_or_503()
    doc_ref = client.collection("users").document(uid)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "USER_NOT_FOUND", "message": f"User {uid} not found."}},
        )

    data = doc.to_dict() or {}
    if data.get("organizationId") not in (settings.ORGANIZATION_ID, "acme", "payhive-eng"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": f"User does not belong to organization '{settings.ORGANIZATION_ID}'."}},
        )

    old_status = str(data.get("status", "pending"))
    target_email = data.get("email", uid)
    target_name = data.get("name", target_email)

    doc_ref.update({"status": "rejected"})
    clear_profile_cache(uid)

    event_id = f"EVT-{int(time.time() * 1000)}"
    log_entry = AuditLog(
        id=event_id,
        actor=user.name,
        tag="User access",
        title=f"User request rejected: {target_name}",
        detail=f"Rejected account request for {target_email} ({uid})",
        note=action.note.strip(),
        source="Firebase Auth",
        assignment_id=None,
        request_id=None,
        audit_id=None,
        before=old_status,
        after="rejected",
        tone="gray",
        icon="−",
        mode="DRY_RUN",
        occurred_at=utc_now(),
    )
    db.add(log_entry)
    db.commit()

    return {
        "status": "success",
        "message": f"User {target_email} rejected successfully.",
        "uid": uid,
        "newStatus": "rejected",
    }
