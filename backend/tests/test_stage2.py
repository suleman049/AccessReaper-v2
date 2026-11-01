"""
Tests for Stage 2: Triage Quality for Real Data.
Covers:
- Bulk identity linking with single-transaction audit events
- Auto-suggestion engine
- Bot/Service/Ignored classification with mandatory notes & risk re-evaluation
- Identities listing, creation, and updating
- CSV import preview validation and confirmation
- "Why this score?" calculation and breakdown
- Unmatched severity rule thresholds (Admin/Write = High, Read = Medium)
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Assignment, AuditLog, GitHubIdentityMap, Identity
from app.engine.scoring import (
    IdentityContext,
    ResourceContext,
    evaluate_risk,
    get_default_rule_config,
)
from app.schemas.serializers import serialize_assignment


def test_unmatched_severity_rule_levels():
    cfg = get_default_rule_config()

    # 1. Unmatched with Admin access -> High (70 pts minimum)
    res_admin = evaluate_risk(
        identity=IdentityContext(
            name="external-dev",
            email="external-dev@github.unmatched",
            job_role="External Collaborator",
            team="Unmatched",
            employment_status="active",
            is_unmatched=True,
            github_login="external-dev",
            account_type="user",
        ),
        resource=ResourceContext(name="payhive/api", source="GitHub"),
        access_level="Admin",
        rule_config=cfg,
    )
    assert res_admin.risk_level == "High"
    assert any(r.code == "UNMATCHED_GITHUB_ACCOUNT_ELEVATED" for r in res_admin.fired_rules)

    # 2. Unmatched with Read access -> Medium (40 pts)
    res_read = evaluate_risk(
        identity=IdentityContext(
            name="external-reader",
            email="external-reader@github.unmatched",
            job_role="External Collaborator",
            team="Unmatched",
            employment_status="active",
            is_unmatched=True,
            github_login="external-reader",
            account_type="user",
        ),
        resource=ResourceContext(name="payhive/docs", source="GitHub"),
        access_level="Read",
        rule_config=cfg,
    )
    assert res_read.risk_level == "Medium"
    assert any(r.code == "UNMATCHED_GITHUB_ACCOUNT" for r in res_read.fired_rules)


def test_bot_service_ignored_classification_excludes_unmatched_finding():
    cfg = get_default_rule_config()

    # Bot account with Read access should NOT trigger unmatched alert
    res_bot = evaluate_risk(
        identity=IdentityContext(
            name="ci-bot",
            email="ci-bot@github.unmatched",
            job_role="Service Account",
            team="Unmatched",
            employment_status="active",
            is_unmatched=True,
            github_login="ci-bot",
            account_type="bot",
        ),
        resource=ResourceContext(name="payhive/api", source="GitHub"),
        access_level="Read",
        rule_config=cfg,
    )
    assert not any(
        r.code in ("UNMATCHED_GITHUB_ACCOUNT", "UNMATCHED_GITHUB_ACCOUNT_ELEVATED") for r in res_bot.fired_rules
    )
    assert res_bot.risk_level == "Low"


def test_classify_account_endpoint(client: TestClient, auth_headers: dict, db_session: Session):
    login = "test-bot-account"
    id_map = GitHubIdentityMap(login=login, email=None, account_type="user")
    db_session.add(id_map)
    db_session.commit()

    # 1. Non-user classification requires note (422)
    resp = client.put(
        f"/api/integrations/github/accounts/{login}/classification",
        headers=auth_headers,
        json={"accountType": "bot", "note": ""},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "NOTE_REQUIRED"

    # 2. With note succeeds
    resp2 = client.put(
        f"/api/integrations/github/accounts/{login}/classification",
        headers=auth_headers,
        json={"accountType": "bot", "note": "Automated Dependabot updater"},
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["accountType"] == "bot"
    assert data["note"] == "Automated Dependabot updater"

    # Check audit log
    audit_evt = (
        db_session.query(AuditLog)
        .filter(AuditLog.title == "GitHub account classified as bot")
        .order_by(AuditLog.occurred_at.desc())
        .first()
    )
    assert audit_evt is not None
    assert "Dependabot" in audit_evt.note


def test_bulk_map_and_auto_suggest(client: TestClient, auth_headers: dict, db_session: Session):
    # Setup unlinked accounts and employee
    ident = db_session.query(Identity).filter(Identity.email == "marcus.vance@acme.io").first()
    if not ident:
        ident = Identity(
            name="Marcus Vance",
            email="marcus.vance@acme.io",
            initials="MV",
            job_role="Lead Architect",
            team="Engineering",
            employment_status="active",
        )
        db_session.add(ident)
    m = db_session.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == "marcus-vance").first()
    if not m:
        db_session.add(GitHubIdentityMap(login="marcus-vance", email=None, account_type="user"))
    else:
        m.email = None
    db_session.commit()

    # 1. Test auto-suggest
    resp_sug = client.get("/api/integrations/github/auto-suggest", headers=auth_headers)
    assert resp_sug.status_code == 200
    suggestions = resp_sug.json()
    assert any(s["login"] == "marcus-vance" and s["suggestedEmail"] == "marcus.vance@acme.io" for s in suggestions)

    # 2. Test bulk mapping
    resp_bulk = client.post(
        "/api/integrations/github/bulk-map",
        headers=auth_headers,
        json={"mappings": [{"login": "marcus-vance", "email": "marcus.vance@acme.io"}]},
    )
    assert resp_bulk.status_code == 200
    assert resp_bulk.json()["mappedCount"] == 1


def test_identities_crud(client: TestClient, auth_headers: dict, db_session: Session):
    # 1. Create identity
    new_user = {
        "name": "Sarah Connor",
        "email": "sarah.connor@acme.io",
        "team": "Security",
        "job_role": "SecOps Analyst",
        "employment_status": "active",
        "current_project": "Access Review",
        "note": "New security analyst hired",
    }
    resp = client.post("/api/identities", headers=auth_headers, json=new_user)
    assert resp.status_code == 201
    created = resp.json()
    assert created["initials"] == "SC"
    assert created["email"] == "sarah.connor@acme.io"

    # 2. List identities
    resp_list = client.get("/api/identities", headers=auth_headers)
    assert resp_list.status_code == 200
    people = resp_list.json()
    assert any(p["email"] == "sarah.connor@acme.io" for p in people)

    # 3. Update identity
    resp_update = client.put(
        "/api/identities/sarah.connor@acme.io",
        headers=auth_headers,
        json={"employment_status": "contractor", "team": "SecOps External", "note": "Contractor conversion"},
    )
    assert resp_update.status_code == 200
    assert resp_update.json()["employment_status"] == "contractor"


def test_csv_import_preview_and_confirm(client: TestClient, auth_headers: dict):
    # 1. Preview
    csv_text = """github_login,email,name,team,employment_status
dev-user-1,dev1@acme.io,Dev One,Engineering,Active
dev-user-2,dev2@acme.io,Dev Two,Design,Contractor
"""
    resp_prev = client.post(
        "/api/identities/import-csv/preview",
        headers=auth_headers,
        json={"csvText": csv_text},
    )
    assert resp_prev.status_code == 200
    prev_data = resp_prev.json()
    assert prev_data["canImport"] is True
    assert len(prev_data["validRows"]) == 2

    # 2. Confirm import
    resp_conf = client.post(
        "/api/identities/import-csv/confirm",
        headers=auth_headers,
        json={"rows": prev_data["validRows"], "note": "Test CSV import"},
    )
    assert resp_conf.status_code == 200
    assert resp_conf.json()["imported"] >= 1


def test_why_this_score_serialization(db_session: Session):
    assignment = db_session.query(Assignment).first()
    assert assignment is not None
    person = serialize_assignment(assignment)
    assert person.score >= 0
    assert isinstance(person.scoreBreakdown, list)
