"""
Firebase Admin SDK integration for AccessReaper v2.
Provides authenticated Firestore administration for accessreaper-profiles and Auth token revocation.
Safely handles unconfigured service accounts so the application continues running.
"""

import logging
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import auth, credentials, firestore

from app.core.config import settings

logger = logging.getLogger("accessreaper.firebase_admin")

_mock_firestore_client: Any = None
_mock_auth_module: Any = None
_mock_mode: bool = False


def set_mock_clients(mock_firestore: Any = None, mock_auth: Any = None) -> None:
    """Sets mock clients for testing purposes."""
    global _mock_firestore_client, _mock_auth_module, _mock_mode
    _mock_firestore_client = mock_firestore
    _mock_auth_module = mock_auth
    _mock_mode = True


def is_service_account_configured() -> bool:
    """Returns True if a valid service account key file exists at the configured path."""
    if _mock_mode:
        return _mock_firestore_client is not None
    path = Path(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
    return path.is_file() and path.stat().st_size > 10


def get_firebase_admin_app() -> firebase_admin.App | None:
    """Initializes or retrieves the Firebase Admin default app."""
    if _mock_firestore_client is not None:
        return None
    if not is_service_account_configured():
        return None

    if firebase_admin._apps:
        return firebase_admin.get_app()

    try:
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
        app = firebase_admin.initialize_app(cred, {"projectId": settings.FIREBASE_PROJECT_ID})
        logger.info("Firebase Admin initialized successfully using %s", settings.FIREBASE_SERVICE_ACCOUNT_PATH)
        return app
    except Exception as exc:
        logger.error("Failed to initialize Firebase Admin SDK: %s", exc)
        return None


def get_firestore_admin_client():
    """
    Returns a Firestore client connected to accessreaper-profiles.
    Returns None if service account is not configured.
    """
    if _mock_firestore_client is not None:
        return _mock_firestore_client

    app = get_firebase_admin_app()
    if not app:
        return None

    try:
        client = firestore.client(app=app, database_id=settings.FIRESTORE_DATABASE_ID)
        return client
    except Exception as exc:
        logger.error("Failed to get Firestore admin client for database %s: %s", settings.FIRESTORE_DATABASE_ID, exc)
        return None


def revoke_user_refresh_tokens(uid: str) -> bool:
    """
    Revokes all refresh tokens for the specified user UID so their session is terminated.
    Returns True on success, False if unconfigured or failed.
    """
    if _mock_auth_module is not None:
        _mock_auth_module.revoke_refresh_tokens(uid)
        return True

    app = get_firebase_admin_app()
    if not app:
        logger.warning("Cannot revoke refresh tokens for %s: service account unconfigured", uid)
        return False

    try:
        auth.revoke_refresh_tokens(uid, app=app)
        logger.info("Revoked refresh tokens for user %s", uid)
        return True
    except Exception as exc:
        logger.error("Failed to revoke refresh tokens for %s: %s", uid, exc)
        return False
