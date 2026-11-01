"""
Tests for Risk Rule configuration (Feature 2).
Validates schema validation boundaries, dry-preview immutability,
version creation, rollback conflict protection, and 12-seed default regression.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Assignment, AuditLog, Finding, RuleConfig
from app.db.seed import SEED_PEOPLE
from app.engine.scoring import (
    IdentityContext,
    ResourceContext,
    evaluate_risk,
    get_default_rule_config,
)


def test_default_rule_config_reproduces_12_seeds_regression():
    """
    Regression assertion: The configurable scoring engine under default configuration
    must produce 100% identical risk levels, primary reasons, and action targets
    for all 12 baseline seed records.
    """
    default_config = get_default_rule_config()

    expected_results = {
        "FND-2841": ("High", "Elevated access unused for 94 days", "Read"),
        "FND-2842": ("High", "Direct admin grant bypasses team policy", "Read"),
        "FND-2843": ("Medium", "Team mismatch for repository access", "Read"),
        "FND-2844": ("Low", "Access matches current role", "Write"),
        "FND-2845": ("High", "Privileged access with no recent activity", "Read"),
        "FND-2846": ("Low", "Access matches current role", "Write"),
        "FND-2847": ("High", "External account has administrator access", "Read"),
        "FND-2848": ("Low", "Read access matches current role", "Read"),
        "FND-2849": ("High", "Former employee account is still active", "None"),
        "FND-2850": ("High", "Application admin role exceeds support duties", "Viewer"),
        "FND-2851": ("Low", "Application role matches current responsibilities", "Editor"),
        "FND-2852": ("Low", "Read-only application role matches current responsibilities", "Viewer"),
    }

    for p in SEED_PEOPLE:
        eval_res = evaluate_risk(
            identity=IdentityContext(
                name=p["name"],
                email=p["email"],
                job_role=p["role"],
                team=p["team"],
                employment_status=p["emp_status"],
            ),
            resource=ResourceContext(
                name=p["repo"],
                source=p["source"],
                is_sensitive=p["sensitive"],
                project=p["project"],
            ),
            access_level=p["access"],
            last_active_days=p["last_days"],
            last_activity_text=p["last"],
            finding_context=p["ctx"],
            rule_config=default_config,
        )

        expected_risk, expected_reason, expected_target = expected_results[p["id"]]
        assert eval_res.risk_level == expected_risk, f"Mismatch on {p['id']}: {eval_res.risk_level} != {expected_risk}"
        assert eval_res.primary_reason == expected_reason, f"Reason mismatch on {p['id']}: {eval_res.primary_reason}"
        assert eval_res.recommended_target == expected_target, (
            f"Target mismatch on {p['id']}: {eval_res.recommended_target}"
        )


def test_rule_validation_boundaries(client: TestClient, auth_headers: dict):
    valid_cfg = get_default_rule_config()

    # 1. Reject negative points (HTTP 422)
    bad_cfg = get_default_rule_config()
    bad_cfg["points"]["dormant"] = -5
    resp = client.post("/api/rules", headers=auth_headers, json={"config": bad_cfg, "note": "Test note"})
    assert resp.status_code == 422

    # 2. Reject points > 100 (HTTP 422)
    bad_cfg = get_default_rule_config()
    bad_cfg["points"]["dormant"] = 101
    resp = client.post("/api/rules", headers=auth_headers, json={"config": bad_cfg, "note": "Test note"})
    assert resp.status_code == 422

    # 3. Reject non-integer float points (HTTP 422)
    bad_cfg = get_default_rule_config()
    bad_cfg["points"]["dormant"] = 40.5
    resp = client.post("/api/rules", headers=auth_headers, json={"config": bad_cfg, "note": "Test note"})
    assert resp.status_code == 422

    # 4. Reject dormantDays < 1 (HTTP 422)
    bad_cfg = get_default_rule_config()
    bad_cfg["dormantDays"] = 0
    resp = client.post("/api/rules", headers=auth_headers, json={"config": bad_cfg, "note": "Test note"})
    assert resp.status_code == 422

    # 5. Reject dormantDays > 3650 (HTTP 422)
    bad_cfg = get_default_rule_config()
    bad_cfg["dormantDays"] = 4000
    resp = client.post("/api/rules", headers=auth_headers, json={"config": bad_cfg, "note": "Test note"})
    assert resp.status_code == 422

    # 6. Reject mediumMin >= highMin (HTTP 422)
    bad_cfg = get_default_rule_config()
    bad_cfg["thresholds"]["mediumMin"] = 80
    bad_cfg["thresholds"]["highMin"] = 70
    resp = client.post("/api/rules", headers=auth_headers, json={"config": bad_cfg, "note": "Test note"})
    assert resp.status_code == 422

    # 7. Reject empty note
    resp = client.post("/api/rules", headers=auth_headers, json={"config": valid_cfg, "note": ""})
    assert resp.status_code == 422


def test_rule_preview_does_not_write_to_db(client: TestClient, db_session: Session, auth_headers: dict):
    # Snapshot counts before preview
    cfg_count_before = db_session.query(RuleConfig).count()
    audit_log_count_before = db_session.query(AuditLog).count()
    assignment_count_before = db_session.query(Assignment).count()
    finding_count_before = db_session.query(Finding).count()

    candidate_cfg = get_default_rule_config()
    # Drastic change: low dormancy threshold and high points
    candidate_cfg["dormantDays"] = 10
    candidate_cfg["points"]["dormant"] = 90
    candidate_cfg["thresholds"]["mediumMin"] = 20
    candidate_cfg["thresholds"]["highMin"] = 30

    resp = client.post("/api/rules/preview", headers=auth_headers, json={"config": candidate_cfg})
    assert resp.status_code == 200
    data = resp.json()

    assert "summary" in data
    assert "changes" in data
    assert data["summary"]["high"] >= data["summary"]["currentHigh"]

    # Verify counts in database are 100% UNCHANGED
    assert db_session.query(RuleConfig).count() == cfg_count_before
    assert db_session.query(AuditLog).count() == audit_log_count_before
    assert db_session.query(Assignment).count() == assignment_count_before
    assert db_session.query(Finding).count() == finding_count_before


def test_rule_versioning_and_rollback(client: TestClient, db_session: Session, auth_headers: dict):
    # 1. Get initial rules (v1 should be active)
    resp = client.get("/api/rules", headers=auth_headers)
    assert resp.status_code == 200
    initial_data = resp.json()
    assert initial_data["active"]["version"] == 1
    assert initial_data["active"]["isActive"] is True

    # 2. Create new rule configuration (v2)
    v2_cfg = get_default_rule_config()
    v2_cfg["dormantDays"] = 60
    v2_cfg["points"]["dormant"] = 50

    create_resp = client.post(
        "/api/rules",
        headers=auth_headers,
        json={"config": v2_cfg, "note": "Shorten dormancy to 60 days"},
    )
    assert create_resp.status_code == 201
    v2_data = create_resp.json()
    assert v2_data["version"] == 2
    assert v2_data["isActive"] is True

    # Verify v1 is now inactive
    get_resp = client.get("/api/rules", headers=auth_headers)
    assert get_resp.status_code == 200
    active_now = get_resp.json()["active"]
    assert active_now["version"] == 2

    # 3. Attempt to rollback to already active version (409 Conflict)
    conflict_resp = client.post("/api/rules/2/activate", headers=auth_headers)
    assert conflict_resp.status_code == 409
    assert "already active" in conflict_resp.json()["error"]["message"].lower()

    # 4. Attempt to rollback to non-existent version (404)
    not_found_resp = client.post("/api/rules/999/activate", headers=auth_headers)
    assert not_found_resp.status_code == 404

    # 5. Rollback to v1
    rollback_resp = client.post("/api/rules/1/activate", headers=auth_headers)
    assert rollback_resp.status_code == 200
    assert rollback_resp.json()["version"] == 1
    assert rollback_resp.json()["isActive"] is True

    # Verify audit log recorded Rules events
    hist_resp = client.get("/api/history?action=Rules", headers=auth_headers)
    assert hist_resp.status_code == 200
    rule_events = hist_resp.json()["items"]
    assert len(rule_events) >= 2
    assert any("Risk rule weights updated" in e["title"] for e in rule_events)
    assert any("Risk rule weights restored" in e["title"] for e in rule_events)
