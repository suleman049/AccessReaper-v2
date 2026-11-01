"""
Authentication and authorization unit tests.
Verifies token verification, audience check, expiration, profile authorization,
role checks, and dev mode security restrictions.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_health_no_auth(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["mode"] == "DRY_RUN"


def test_dev_mode_authenticated(client: TestClient, auth_headers: dict):
    resp = client.get("/api/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "jordan.davis@acme.io"
    assert data["role"] == "admin"
    assert data["status"] == "active"
    assert data["organizationId"] == "acme"


def test_firebase_mode_missing_token():
    original_mode = settings.AUTH_MODE
    try:
        settings.AUTH_MODE = "firebase"
        client = TestClient(app, base_url="http://127.0.0.1:8100")
        resp = client.get("/api/me")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "MISSING_TOKEN"
    finally:
        settings.AUTH_MODE = original_mode


def test_firebase_mode_invalid_token():
    original_mode = settings.AUTH_MODE
    try:
        settings.AUTH_MODE = "firebase"
        client = TestClient(app, base_url="http://127.0.0.1:8100")
        with patch("app.core.security.google_id_token.verify_firebase_token") as mock_verify:
            mock_verify.side_effect = ValueError("Token expired")
            resp = client.get("/api/me", headers={"Authorization": "Bearer invalid-token"})
            assert resp.status_code == 401
            assert resp.json()["error"]["code"] == "INVALID_TOKEN"
    finally:
        settings.AUTH_MODE = original_mode


def test_firebase_mode_pending_role():
    original_mode = settings.AUTH_MODE
    try:
        settings.AUTH_MODE = "firebase"
        client = TestClient(app, base_url="http://127.0.0.1:8100")
        with (
            patch("app.core.security.google_id_token.verify_firebase_token") as mock_verify,
            patch("app.core.security.fetch_firestore_profile") as mock_profile,
        ):
            mock_verify.return_value = {
                "sub": "user-pending-123",
                "email": "pending@acme.io",
                "name": "Pending User",
            }
            # Profile with pending role
            mock_profile.return_value = {
                "uid": "user-pending-123",
                "email": "pending@acme.io",
                "name": "Pending User",
                "role": "pending",
                "status": "pending",
                "organizationId": "acme",
            }
            resp = client.get("/api/me", headers={"Authorization": "Bearer valid-token"})
            assert resp.status_code == 403
            assert resp.json()["error"]["code"] in ("ACCOUNT_INACTIVE", "FORBIDDEN")
    finally:
        settings.AUTH_MODE = original_mode


def test_firebase_mode_wrong_organization():
    original_mode = settings.AUTH_MODE
    try:
        settings.AUTH_MODE = "firebase"
        client = TestClient(app, base_url="http://127.0.0.1:8100")
        with (
            patch("app.core.security.google_id_token.verify_firebase_token") as mock_verify,
            patch("app.core.security.fetch_firestore_profile") as mock_profile,
        ):
            mock_verify.return_value = {
                "sub": "user-ext-123",
                "email": "external@other.io",
                "name": "External User",
            }
            mock_profile.return_value = {
                "uid": "user-ext-123",
                "email": "external@other.io",
                "name": "External User",
                "role": "admin",
                "status": "active",
                "organizationId": "other-corp",
            }
            resp = client.get("/api/me", headers={"Authorization": "Bearer valid-token"})
            assert resp.status_code == 403
            assert resp.json()["error"]["code"] == "ORGANIZATION_MISMATCH"
    finally:
        settings.AUTH_MODE = original_mode


def test_firebase_mode_valid_admin():
    original_mode = settings.AUTH_MODE
    try:
        settings.AUTH_MODE = "firebase"
        client = TestClient(app, base_url="http://127.0.0.1:8100")
        with (
            patch("app.core.security.google_id_token.verify_firebase_token") as mock_verify,
            patch("app.core.security.fetch_firestore_profile") as mock_profile,
        ):
            mock_verify.return_value = {
                "sub": "user-admin-456",
                "email": "admin@acme.io",
                "name": "Admin User",
            }
            mock_profile.return_value = {
                "uid": "user-admin-456",
                "email": "admin@acme.io",
                "name": "Admin User",
                "role": "admin",
                "status": "active",
                "organizationId": "acme",
            }
            resp = client.get("/api/me", headers={"Authorization": "Bearer valid-token"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["email"] == "admin@acme.io"
            assert data["role"] == "admin"
            assert data["status"] == "active"
            assert data["organizationId"] == "acme"
    finally:
        settings.AUTH_MODE = original_mode


def test_dev_mode_host_restriction():
    """App must refuse dev authentication if host is not 127.0.0.1."""
    original_host = settings.HOST
    try:
        settings.HOST = "0.0.0.0"
        client = TestClient(app, base_url="http://127.0.0.1:8100")
        resp = client.get("/api/me", headers={"X-Dev-User": "admin@acme.io"})
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "MISCONFIGURED"
    finally:
        settings.HOST = original_host
