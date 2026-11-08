"""
Authentication and Authorization module for AccessReaper v2.
Verifies Firebase ID tokens using Google public keys without requiring a service account key.
Authorizes users server-side against Firestore REST API using the caller's own token.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings

logger = logging.getLogger("accessreaper.security")

# HTTP Bearer scheme (auto_error=False so we can handle missing tokens cleanly)
bearer_scheme = HTTPBearer(auto_error=False)

# Profile cache: uid -> (cached_at_timestamp, profile_dict)
# Enforces TTL <= 60 seconds
_PROFILE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 60.0

_google_request_adapter = google_requests.Request()

OWNER_EMAILS = {"24sw049@gmail.com"}


@dataclass
class UserClaims:
    uid: str
    email: str
    name: str
    role: str
    status: str
    organization_id: str
    token: str | None = None


def unwrap_firestore_fields(fields_dict: dict[str, Any]) -> dict[str, Any]:
    """Unwraps Firestore REST API typed values into Python primitives."""
    result = {}
    for key, val in fields_dict.items():
        if not isinstance(val, dict):
            result[key] = val
            continue
        if "stringValue" in val:
            result[key] = val["stringValue"]
        elif "integerValue" in val:
            result[key] = int(val["integerValue"])
        elif "booleanValue" in val:
            result[key] = bool(val["booleanValue"])
        elif "timestampValue" in val:
            result[key] = val["timestampValue"]
        elif "mapValue" in val:
            result[key] = unwrap_firestore_fields(val["mapValue"].get("fields", {}))
        elif "arrayValue" in val:
            values = val["arrayValue"].get("values", [])
            result[key] = [
                v.get("stringValue") or v.get("integerValue") or list(v.values())[0]
                for v in values
                if isinstance(v, dict)
            ]
        elif "nullValue" in val:
            result[key] = None
        else:
            result[key] = list(val.values())[0] if val else None
    return result


def fetch_firestore_profile(uid: str, token: str) -> dict[str, Any]:
    """
    Fetches the caller's own user profile from Firestore REST API using their own ID token.
    Uses the dedicated accessreaper-profiles database.
    """
    url = (
        f"https://firestore.googleapis.com/v1/projects/{settings.FIREBASE_PROJECT_ID}/"
        f"databases/{settings.FIRESTORE_DATABASE_ID}/documents/users/{uid}"
    )
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 404:
                logger.warning("Firestore profile not found for uid %s", uid)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": {
                            "code": "PROFILE_NOT_FOUND",
                            "message": "Account profile not found in workspace.",
                        }
                    },
                )
            if resp.status_code == 403:
                logger.warning("Firestore returned 403 for uid %s", uid)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": {
                            "code": "FORBIDDEN",
                            "message": "Access to workspace profile denied.",
                        }
                    },
                )
            if not resp.is_success:
                logger.error("Firestore REST API returned %s: %s", resp.status_code, resp.text)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": {
                            "code": "PROFILE_ERROR",
                            "message": "Could not verify workspace profile.",
                        }
                    },
                )
            doc_data = resp.json()
            raw_fields = doc_data.get("fields", {})
            return unwrap_firestore_fields(raw_fields)
    except httpx.RequestError as exc:
        logger.error("Failed to connect to Firestore REST API: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "PROFILE_UNAVAILABLE",
                    "message": "Profile verification service unreachable.",
                }
            },
        )


def verify_firebase_id_token(token: str) -> dict[str, Any]:
    """
    Verifies the Firebase ID token signature, expiration, audience and issuer
    using Google's public certificates.
    """
    try:
        claims = google_id_token.verify_firebase_token(
            token,
            _google_request_adapter,
            audience=settings.FIREBASE_PROJECT_ID,
        )
        return claims
    except Exception as exc:
        logger.warning("Firebase ID token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Invalid or expired Firebase authentication token.",
                }
            },
        )


async def get_current_user(
    auth_header: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_dev_user: str | None = Header(None, alias="X-Dev-User"),
) -> UserClaims:
    """
    FastAPI dependency that extracts and validates the user's authentication and authorization.
    In AUTH_MODE=dev: accepts X-Dev-User or falls back to dev admin (only on 127.0.0.1).
    In AUTH_MODE=firebase: verifies Firebase ID token and verifies Firestore profile.
    """
    # 1. Dev mode override (bound to 127.0.0.1 only)
    if settings.AUTH_MODE == "dev":
        if settings.HOST != "127.0.0.1":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": {
                        "code": "MISCONFIGURED",
                        "message": "Dev mode prohibited on non-loopback host.",
                    }
                },
            )
        dev_email = x_dev_user
        if not dev_email and auth_header and auth_header.credentials and auth_header.credentials != "dev-token":
            try:
                claims = verify_firebase_id_token(auth_header.credentials)
                dev_email = claims.get("email")
            except Exception:
                pass
        dev_email = dev_email or "24sw049@gmail.com" 
        dev_name = dev_email.split("@")[0].replace(".", " ").title()
        role = "owner" if dev_email.lower() in OWNER_EMAILS else "admin"
        return UserClaims(
            uid="dev-owner-uid" if role == "owner" else "dev-admin-uid",
            email=dev_email,
            name=dev_name,
            role=role,
            status="active",
            organization_id=settings.ORGANIZATION_ID,
            token="dev-token",
        )

    # 2. Firebase Auth verification
    if not auth_header or not auth_header.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "MISSING_TOKEN",
                    "message": "Authentication token required.",
                }
            },
        )

    token = auth_header.credentials
    claims = verify_firebase_id_token(token)
    uid = claims.get("user_id") or claims.get("sub")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_CLAIMS", "message": "Token has no user ID."}},
        )

    email = claims.get("email", "")

    # 3. Check profile cache (TTL <= 60 seconds)
    now = time.time()
    cached = _PROFILE_CACHE.get(uid)
    if cached and (now - cached[0] < CACHE_TTL_SECONDS):
        profile = cached[1]
    else:
        profile = fetch_firestore_profile(uid, token)
        _PROFILE_CACHE[uid] = (now, profile)

    # 4. Authorize against workspace requirements: role == admin, status == active, organizationId == acme
    role = profile.get("role", "")
    user_status = profile.get("status", "")
    org_id = profile.get("organizationId", "")
    profile_name = profile.get("name") or claims.get("name") or email.split("@")[0].title()

    if org_id != settings.ORGANIZATION_ID:
        logger.warning("User %s rejected: wrong organizationId '%s'", uid, org_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "ORGANIZATION_MISMATCH",
                    "message": "Account does not belong to this organization.",
                }
            },
        )

    if user_status != "active":
        logger.warning("User %s rejected: status is '%s'", uid, user_status)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "ACCOUNT_INACTIVE",
                    "message": "Workspace account is not active.",
                }
            },
        )

    if email.lower() in OWNER_EMAILS:
        role = "owner"

    if role not in ("admin", "owner"):
        logger.warning("User %s rejected: role is '%s' (admin/owner required)", uid, role)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Administrator or Owner privileges required.",
                }
            },
        )

    return UserClaims(
        uid=uid,
        email=email,
        name=profile_name,
        role=role,
        status=user_status,
        organization_id=org_id,
        token=token,
    )


def require_role(required_role: str):
    """Dependency factory checking that the authenticated user possesses the required role."""

    def role_checker(user: UserClaims = Depends(get_current_user)) -> UserClaims:
        # Owner possesses all roles (admin, manager, etc.)
        if user.role == "owner" or (user.email and user.email.lower() in OWNER_EMAILS):
            return user

        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "INSUFFICIENT_ROLE",
                        "message": f"{required_role.capitalize()} role required.",
                    }
                },
            )
        return user

    return role_checker


def clear_profile_cache(uid: str | None = None) -> None:
    """Clears cached Firestore profile for a specific UID or all cached profiles."""
    if uid:
        _PROFILE_CACHE.pop(uid, None)
    else:
        _PROFILE_CACHE.clear()
