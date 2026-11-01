"""
Integration tests for GitHub synchronization, identity mapping, request cap,
disappeared collaborator handling, data mode isolation, and identity updates.
"""

import respx
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.config import settings
from app.db.models import (
    Assignment,
    AuditLog,
    GitHubIdentityMap,
    Identity,
    Resource,
)
from app.engine.scoring import (
    IdentityContext,
    ResourceContext,
    evaluate_risk,
    get_default_rule_config,
)


def _setup_mock_github_routes(base_url: str):
    base = base_url.rstrip("/")
    respx.get(f"{base}/user").respond(
        200,
        json={"login": "audit-admin", "id": 999, "name": "Audit Admin"},
        headers={"x-oauth-scopes": "read:org, repo"},
    )
    respx.get(f"{base}/orgs/acme").respond(
        200,
        json={"login": "acme", "name": "Acme, Inc.", "total_private_repos": 2},
    )
    respx.get(f"{base}/orgs/acme/members").respond(
        200,
        json=[
            {"login": "alexmorgan", "id": 101, "name": "Alex Morgan", "email": "alex.morgan@acme.io"},
            {"login": "mayachen", "id": 102, "name": "Maya Chen", "email": "maya.chen@acme.io"},
            {"login": "marcusvance", "id": 103, "name": "Marcus Vance", "email": "marcus.vance@acme.io"},
            {"login": "ghost-contractor", "id": 104, "name": "Ghost Contractor", "email": None},
        ],
    )
    respx.get(f"{base}/orgs/acme/outside_collaborators").respond(
        200,
        json=[
            {"login": "erostova", "id": 201, "name": "Elena Rostova", "email": "elena.rostova@external.io"},
            {"login": "intern-dev", "id": 202, "name": "Intern Dev", "email": None},
        ],
    )
    respx.get(f"{base}/orgs/acme/repos").respond(
        200,
        json=[
            {
                "id": 401,
                "name": "api-gateway",
                "full_name": "acme/api-gateway",
                "private": True,
                "default_branch": "main",
            },
            {
                "id": 402,
                "name": "auth-service",
                "full_name": "acme/auth-service",
                "private": True,
                "default_branch": "main",
            },
        ],
    )
    respx.get(f"{base}/repos/acme/api-gateway/collaborators").respond(
        200,
        json=[
            {"login": "alexmorgan", "role_name": "admin", "permissions": {"admin": True, "push": True, "pull": True}},
            {"login": "marcusvance", "role_name": "admin", "permissions": {"admin": True, "push": True, "pull": True}},
            {
                "login": "ghost-contractor",
                "role_name": "admin",
                "permissions": {"admin": True, "push": True, "pull": True},
            },
        ],
    )
    respx.get(f"{base}/repos/acme/auth-service/collaborators").respond(
        200,
        json=[
            {
                "login": "mayachen",
                "role_name": "maintain",
                "permissions": {"admin": False, "maintain": True, "push": True, "pull": True},
            },
            {"login": "erostova", "role_name": "admin", "permissions": {"admin": True, "push": True, "pull": True}},
        ],
    )
    respx.get(f"{base}/repos/acme/api-gateway/commits").respond(200, json=[])
    respx.get(f"{base}/repos/acme/auth-service/commits").respond(200, json=[])
    respx.get(f"{base}/users/ghost-contractor").respond(200, json={"login": "ghost-contractor", "email": None})
    respx.get(f"{base}/users/intern-dev").respond(200, json={"login": "intern-dev", "email": None})


@respx.mock
def test_sync_flow_and_idempotence(client: TestClient, db_session: Session, auth_headers: dict):
    """
    Tests full synchronization, permission mapping, and idempotency (re-sync doesn't duplicate).
    """
    base = settings.GITHUB_API_BASE
    _setup_mock_github_routes(base)

    # 1. Connect
    client.put(
        "/api/integrations/github/config", headers=auth_headers, json={"org": "acme", "token": "ghp_MockToken1234"}
    )

    # 2. First Sync
    sync_resp1 = client.post("/api/integrations/github/sync", headers=auth_headers)
    assert sync_resp1.status_code == 200
    data1 = sync_resp1.json()
    assert data1["status"] == "ok"
    assert data1["repos_count"] == 2
    assert data1["assignments_created"] > 0
    created_count = data1["assignments_created"]

    # Verify maintain was mapped to Write (NOT Admin) for mayachen on auth-service
    auth_srv = db_session.query(Resource).filter(Resource.name == "acme/auth-service").first()
    maya_asgn = (
        db_session.query(Assignment)
        .filter(
            Assignment.resource_id == auth_srv.id,
            Assignment.github_login == "mayachen",
        )
        .first()
    )
    assert maya_asgn is not None
    assert maya_asgn.access_level == "Write"

    # 3. Second Sync (must be idempotent: no new assignments created, updated in place)
    sync_resp2 = client.post("/api/integrations/github/sync", headers=auth_headers)
    assert sync_resp2.status_code == 200
    data2 = sync_resp2.json()
    assert data2["assignments_created"] == 0
    assert data2["assignments_updated"] == created_count


@respx.mock
def test_unmatched_accounts_and_mapping(client: TestClient, db_session: Session, auth_headers: dict):
    """
    Tests that unlinked accounts appear in /api/integrations/github/unmatched
    and can be mapped to an employee via PUT /map/{login}.
    """
    base = settings.GITHUB_API_BASE
    _setup_mock_github_routes(base)

    client.put(
        "/api/integrations/github/config", headers=auth_headers, json={"org": "acme", "token": "ghp_MockToken1234"}
    )
    client.post("/api/integrations/github/sync", headers=auth_headers)

    # 1. Fetch unmatched accounts
    unmatched_resp = client.get("/api/integrations/github/unmatched", headers=auth_headers)
    assert unmatched_resp.status_code == 200
    unmatched = unmatched_resp.json()
    unmatched_logins = [u["login"] for u in unmatched]
    assert "ghost-contractor" in unmatched_logins

    # 2. Map ghost-contractor to an employee (e.g. Maya Chen)
    map_resp = client.put(
        "/api/integrations/github/map/ghost-contractor",
        headers=auth_headers,
        json={"email": "maya.chen@acme.io"},
    )
    assert map_resp.status_code == 200
    assert map_resp.json()["ok"] is True

    # 3. Verify ghost-contractor is now mapped in DB and removed from unmatched
    unmatched_after = client.get("/api/integrations/github/unmatched", headers=auth_headers).json()
    assert "ghost-contractor" not in [u["login"] for u in unmatched_after]

    id_map = db_session.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == "ghost-contractor").first()
    assert id_map.email == "maya.chen@acme.io"
    assert id_map.source == "manual"


@respx.mock
def test_disappeared_collaborator_revoked_externally(client: TestClient, db_session: Session, auth_headers: dict):
    """
    When a collaborator disappears from GitHub, subsequent sync marks external_status='revoked_externally'
    instead of deleting it.
    """
    base = settings.GITHUB_API_BASE
    _setup_mock_github_routes(base)

    client.put(
        "/api/integrations/github/config", headers=auth_headers, json={"org": "acme", "token": "ghp_MockToken1234"}
    )
    client.post("/api/integrations/github/sync", headers=auth_headers)

    # Now remove ghost-contractor from collaborators list on api-gateway
    respx.get(f"{base}/repos/acme/api-gateway/collaborators").respond(
        200,
        json=[
            {"login": "alexmorgan", "role_name": "admin", "permissions": {"admin": True, "push": True, "pull": True}},
            {"login": "marcusvance", "role_name": "admin", "permissions": {"admin": True, "push": True, "pull": True}},
        ],
    )

    # Sync again
    sync_resp = client.post("/api/integrations/github/sync", headers=auth_headers)
    assert sync_resp.status_code == 200
    assert sync_resp.json()["assignments_revoked"] == 1

    # Verify ghost-contractor's assignment on api-gateway is marked revoked_externally
    api_gw = db_session.query(Resource).filter(Resource.name == "acme/api-gateway").first()
    ghost_asgn = (
        db_session.query(Assignment)
        .filter(
            Assignment.resource_id == api_gw.id,
            Assignment.github_login == "ghost-contractor",
        )
        .first()
    )
    assert ghost_asgn is not None
    assert ghost_asgn.external_status == "revoked_externally"


def test_data_mode_switching_and_isolation(client: TestClient, db_session: Session, auth_headers: dict):
    """
    Verifies switching dataMode (sample <-> live) cleanly filters assignments in bootstrap and dashboard.
    """
    # 1. Switch to live mode
    mode_resp = client.put("/api/integrations/github/mode", headers=auth_headers, json={"data_mode": "live"})
    assert mode_resp.status_code == 200
    assert mode_resp.json()["data_mode"] == "live"

    # Check bootstrap in live mode (should only contain origin == 'github')
    boot_live = client.get("/api/bootstrap", headers=auth_headers).json()
    for person in boot_live["people"]:
        asgn = db_session.query(Assignment).filter(Assignment.id == person["id"]).first()
        assert asgn.origin == "github"
        assert asgn.external_status != "revoked_externally"

    # 2. Switch back to sample mode
    client.put("/api/integrations/github/mode", headers=auth_headers, json={"data_mode": "sample"})
    boot_sample = client.get("/api/bootstrap", headers=auth_headers).json()
    for person in boot_sample["people"]:
        asgn = db_session.query(Assignment).filter(Assignment.id == person["id"]).first()
        assert asgn.origin == "sample"


def test_identities_api_status_update(client: TestClient, db_session: Session, auth_headers: dict):
    """
    Tests updating employment status via PUT /api/identities/{email} with required note,
    re-evaluates risk to High for former employee, and writes audit event.
    """
    target_email = "alex.morgan@acme.io"
    resp = client.put(
        f"/api/identities/{target_email}",
        headers=auth_headers,
        json={"employment_status": "former", "note": "Alex left the company on Oct 20"},
    )
    assert resp.status_code == 200
    assert resp.json()["employment_status"] == "former"

    # Check risk re-evaluated
    alex = db_session.query(Identity).filter(Identity.email == target_email).first()
    for a in alex.assignments:
        assert a.current_risk == "High"
        assert "Former employee" in a.reason

    # Audit event recorded
    audit_evt = (
        db_session.query(AuditLog)
        .filter(AuditLog.tag == "Identity", AuditLog.detail.contains(target_email))
        .order_by(AuditLog.occurred_at.desc())
        .first()
    )
    assert audit_evt is not None
    assert "Alex left the company" in audit_evt.note

    # Reset back to active
    client.put(
        f"/api/identities/{target_email}",
        headers=auth_headers,
        json={"employment_status": "active", "note": "Re-activated account"},
    )


def test_null_activity_counts_as_dormant_rule_option():
    """
    Tests that unknownActivityCountsAsDormant flag correctly toggles dormancy evaluation when activity is null.
    """
    id_ctx = IdentityContext(
        name="Test User",
        email="test@acme.io",
        job_role="Engineer",
        team="Platform",
        employment_status="active",
        current_project="Platform",
    )
    res_ctx = ResourceContext(
        name="acme/api-gateway",
        source="GitHub",
        is_sensitive=False,
        project="Platform",
    )

    # 1. Default (unknownActivityCountsAsDormant = False)
    cfg_default = get_default_rule_config()
    cfg_default["unknownActivityCountsAsDormant"] = False
    eval_default = evaluate_risk(
        identity=id_ctx,
        resource=res_ctx,
        access_level="Admin",
        last_active_days=None,
        last_activity_text="",
        rule_config=cfg_default,
    )
    assert not any(r.code == "UNUSED_90_DAYS" for r in eval_default.fired_rules)
    assert any("no recorded activity found" in e for e in eval_default.evidence)

    # 2. Enabled (unknownActivityCountsAsDormant = True)
    cfg_enabled = get_default_rule_config()
    cfg_enabled["unknownActivityCountsAsDormant"] = True
    eval_enabled = evaluate_risk(
        identity=id_ctx,
        resource=res_ctx,
        access_level="Admin",
        last_active_days=None,
        last_activity_text="",
        rule_config=cfg_enabled,
    )
    assert any(r.code == "UNUSED_90_DAYS" for r in eval_enabled.fired_rules)
