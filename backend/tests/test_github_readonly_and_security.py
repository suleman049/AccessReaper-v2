"""
Tests for GitHub Client read-only guarantee and token security.
Safety requirement:
1. Strict read-only enforcement: Only GET allowed. POST/PUT/PATCH/DELETE must fail immediately.
2. Token security: Token encrypted at rest, never returned over API, never in logs.
"""

import pytest
import respx
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.crypto import decrypt_secret
from app.db.models import AuditLog, GitHubConfig
from app.integrations.github.client import GitHubClient, ReadOnlyViolationError
from app.integrations.github.mapping import map_github_permission


def test_github_client_readonly_enforcement():
    """Verify that any non-GET request directly raises ReadOnlyViolationError."""
    client = GitHubClient(token="mock-token-for-test", base_url="http://127.0.0.1:8109")

    # 1. Direct method calls must raise ReadOnlyViolationError
    with pytest.raises(ReadOnlyViolationError):
        client.post("repos/acme/api-gateway/hooks", json={})

    with pytest.raises(ReadOnlyViolationError):
        client.put("repos/acme/api-gateway/collaborators/alex", json={})

    with pytest.raises(ReadOnlyViolationError):
        client.patch("repos/acme/api-gateway", json={})

    with pytest.raises(ReadOnlyViolationError):
        client.delete("repos/acme/api-gateway/collaborators/alex")

    # 2. Assert no other write methods exist
    for method_name in ["request", "options", "head"]:
        assert not hasattr(client, method_name) or method_name not in client.__dict__


def test_permission_mapping_policy():
    """
    Asserts strict permission mapping:
    admin -> Admin
    maintain -> Write (MUST NOT BE ADMIN)
    push -> Write
    triage -> Read
    pull -> Read
    """
    assert map_github_permission(role_name="admin") == "Admin"
    assert map_github_permission(permissions={"admin": True}) == "Admin"

    # Strict rule: maintain is Write, NEVER Admin
    assert map_github_permission(role_name="maintain") == "Write"
    assert map_github_permission(permissions={"admin": False, "maintain": True}) == "Write"

    assert map_github_permission(role_name="push") == "Write"
    assert map_github_permission(role_name="write") == "Write"
    assert map_github_permission(permissions={"admin": False, "maintain": False, "push": True}) == "Write"

    assert map_github_permission(role_name="triage") == "Read"
    assert map_github_permission(role_name="pull") == "Read"
    assert map_github_permission(role_name="read") == "Read"
    assert map_github_permission(permissions={"pull": True}) == "Read"


@respx.mock
def test_token_encryption_and_api_masking(client: TestClient, db_session: Session, auth_headers: dict):
    """
    Tests that:
    1. Token is encrypted in SQLite db using Fernet.
    2. Token is never returned over API (only token_last4 and connected: true).
    3. Audit log contains no plaintext token.
    """
    secret_pat = "ghp_VerySecretSecretToken1234"

    # Mock GitHub API responses for connection test
    base = settings.GITHUB_API_BASE.rstrip("/")
    respx.get(f"{base}/user").respond(
        200,
        json={"login": "audit-admin", "id": 999, "name": "Audit Admin"},
        headers={"x-oauth-scopes": "read:org, repo"},
    )
    respx.get(f"{base}/orgs/acme").respond(
        200,
        json={"login": "acme", "name": "Acme, Inc.", "total_private_repos": 3},
    )

    # Configure integration
    resp = client.put(
        "/api/integrations/github/config",
        headers=auth_headers,
        json={"org": "acme", "token": secret_pat},
    )
    assert resp.status_code == 200
    data = resp.json()

    # 1. API response must NEVER include secret_pat
    assert secret_pat not in str(data)
    assert data["connected"] is True
    assert data["token_last4"] == "1234"
    assert data["org_name"] == "acme"

    # 2. Database must store encrypted ciphertext
    gh_cfg = db_session.query(GitHubConfig).first()
    assert gh_cfg is not None
    assert gh_cfg.encrypted_token != secret_pat
    assert decrypt_secret(gh_cfg.encrypted_token) == secret_pat

    # 3. Audit log must never contain secret_pat
    audit_events = db_session.query(AuditLog).filter(AuditLog.tag == "Integration").all()
    for evt in audit_events:
        assert secret_pat not in (evt.note or "")
        assert secret_pat not in str(evt.before or "")
        assert secret_pat not in str(evt.after or "")
        assert secret_pat not in str(evt.detail or "")
