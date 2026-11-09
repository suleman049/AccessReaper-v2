"""
End-to-end API endpoint tests for AccessReaper v2.
Validates bootstrap, dashboard, assignments, remediate/dismiss, approvals decision,
audits execution idempotency, history, search, and admin reset.
"""

from fastapi.testclient import TestClient


def test_bootstrap_payload_shape(client: TestClient, auth_headers: dict):
    resp = client.get("/api/bootstrap", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "people" in data
    assert "approvals" in data
    assert "history" in data
    assert "auditRuns" in data
    assert "auditSnapshots" in data
    assert "lastAudit" in data

    assert len(data["people"]) == 12
    assert len(data["approvals"]) == 6
    assert len(data["auditRuns"]) >= 1

    # Check finding shape in a person record
    first_person = data["people"][0]
    assert "id" in first_person
    assert "name" in first_person
    assert "finding" in first_person
    f = first_person["finding"]
    assert "originalReason" in f
    assert "originalSeverity" in f
    assert "originalAccess" in f
    assert "detectedAt" in f
    assert "status" in f
    assert "snapshot" in f
    assert "evidence" in f


def test_dashboard_summary(client: TestClient, auth_headers: dict):
    resp = client.get("/api/dashboard/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["identities"] == 12
    assert data["assignments"] == 12
    assert data["github"] == 9
    assert data["firestore"] == 3
    assert data["high"] == 6
    assert data["medium"] == 1
    assert data["healthy"] == 5
    assert data["pending"] == 4


def test_dashboard_trend(client: TestClient, auth_headers: dict):
    resp = client.get("/api/dashboard/trend?days=7", headers=auth_headers)
    assert resp.status_code == 200
    points = resp.json()
    assert len(points) == 7
    # At least one recorded day has high risk count
    recorded = [p for p in points if p["high"] is not None]
    assert len(recorded) >= 1


def test_assignments_filters(client: TestClient, auth_headers: dict):
    # Risk filter High
    resp = client.get("/api/assignments?risk=High", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 6

    # Source filter Firestore
    resp = client.get("/api/assignments?source=Firestore", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 3

    # Query search
    resp = client.get("/api/assignments?q=Alex", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "Alex Morgan"


def test_assignment_detail(client: TestClient, auth_headers: dict):
    resp = client.get("/api/assignments/FND-2841", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["assignment"]["id"] == "FND-2841"
    assert "recommendation" in data
    assert "timeline" in data
    assert "relatedRequests" in data
    assert data["recommendation"]["target"] == "Read"


def test_remediate_flow_and_double_submit(client: TestClient, auth_headers: dict):
    # Missing/empty note -> 422
    resp = client.post("/api/assignments/FND-2841/remediate", json={"note": ""}, headers=auth_headers)
    assert resp.status_code == 422

    # Happy path: Remediate Alex Morgan (Admin -> Read)
    note = "Confirmed elevated admin no longer needed for platform rotation."
    resp = client.post("/api/assignments/FND-2841/remediate", json={"note": note}, headers=auth_headers)
    assert resp.status_code == 200
    person = resp.json()
    assert person["access"] == "Read"
    assert person["resolved"] is True
    assert person["finding"]["status"] == "Remediated"

    # Verify history event was appended
    h_resp = client.get("/api/history?q=FND-2841", headers=auth_headers)
    assert h_resp.status_code == 200
    events = h_resp.json()["items"]
    remediated_evt = next((e for e in events if e["tag"] == "Remediated"), None)
    assert remediated_evt is not None
    assert remediated_evt["note"] == note
    assert remediated_evt["before"] == "Admin"
    assert remediated_evt["after"] == "Read"

    # Double submit: already resolved -> 409 Conflict
    resp_conflict = client.post("/api/assignments/FND-2841/remediate", json={"note": "Retry"}, headers=auth_headers)
    assert resp_conflict.status_code == 409
    assert resp_conflict.json()["error"]["code"] == "ALREADY_DECIDED"


def test_dismiss_flow_and_double_submit(client: TestClient, auth_headers: dict):
    # Dismiss Sam Rivera (FND-2843: Medium risk)
    note = "Design team requires write access for portal styling review."
    resp = client.post("/api/assignments/FND-2843/dismiss", json={"note": note}, headers=auth_headers)
    assert resp.status_code == 200
    person = resp.json()
    assert person["access"] == "Write"  # Permission kept
    assert person["resolved"] is True
    assert person["finding"]["status"] == "Dismissed"

    # Double submit -> 409 Conflict
    resp_conflict = client.post("/api/assignments/FND-2843/dismiss", json={"note": "Retry"}, headers=auth_headers)
    assert resp_conflict.status_code == 409


def test_approval_decision_and_double_submit(client: TestClient, auth_headers: dict):
    # REQ-1042: Maya Chen role change to Write
    # Missing note -> 422
    resp = client.post(
        "/api/approvals/REQ-1042/decision", json={"action": "Approved", "note": ""}, headers=auth_headers
    )
    assert resp.status_code == 422

    # Happy path: Approve request
    resp = client.post(
        "/api/approvals/REQ-1042/decision",
        json={"action": "Approved", "note": "Approved write access for on-call rotation"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    approval = resp.json()
    assert approval["status"] == "Approved"

    # Check Maya Chen assignment (FND-2842) updated to Write and resolved
    a_resp = client.get("/api/assignments/FND-2842", headers=auth_headers)
    assert a_resp.status_code == 200
    assignment = a_resp.json()["assignment"]
    assert assignment["access"] == "Write"
    assert assignment["resolved"] is True
    assert assignment["finding"]["status"] == "Approved change"

    # Double submit on REQ-1042 -> 409 Conflict
    resp_conflict = client.post(
        "/api/approvals/REQ-1042/decision",
        json={"action": "Approved", "note": "Trying again"},
        headers=auth_headers,
    )
    assert resp_conflict.status_code == 409
    assert resp_conflict.json()["error"]["code"] == "ALREADY_DECIDED"


def test_approval_reject_flow(client: TestClient, auth_headers: dict):
    # REQ-1038: Noah Williams (contractor)
    resp = client.post(
        "/api/approvals/REQ-1038/decision",
        json={"action": "Declined", "note": "External contractors must not have write permissions"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    approval = resp.json()
    assert approval["status"] == "Declined"


def test_audit_run_and_idempotency(client: TestClient, auth_headers: dict):
    import time
    from app.engine.audit_service import _audit_lock
    for _ in range(50):
        if not _audit_lock.locked():
            break
        time.sleep(0.1)
    # Run audit 1
    resp1 = client.post("/api/audits/run", headers=auth_headers)
    assert resp1.status_code == 200
    run1 = resp1.json()
    assert run1["status"] == "Completed"
    assert run1["assignments"] == 12
    assert "AUD-" in run1["id"]

    # Run audit 2 immediately after: verify idempotent counts and non-corruption
    resp2 = client.post("/api/audits/run", headers=auth_headers)
    assert resp2.status_code == 200
    run2 = resp2.json()
    assert run2["status"] == "Completed"
    assert run2["assignments"] == run1["assignments"]
    assert run2["high"] == run1["high"]
    assert run2["medium"] == run1["medium"]
    assert run2["healthy"] == run1["healthy"]


def test_global_search(client: TestClient, auth_headers: dict):
    resp = client.get("/api/search?q=api-gateway", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["resources"]) >= 1
    assert any("api-gateway" in r["name"] for r in data["resources"])


def test_admin_reset_sample(client: TestClient, auth_headers: dict):
    resp = client.post("/api/admin/reset-sample", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # After reset, verify summary counts match baseline
    s_resp = client.get("/api/dashboard/summary", headers=auth_headers)
    assert s_resp.status_code == 200
    summary = s_resp.json()
    assert summary["high"] == 6
    assert summary["medium"] == 1
    assert summary["healthy"] == 5
    assert summary["pending"] == 4

def test_admin_direct_onboard_workflow(client: TestClient, auth_headers: dict):
    """Verifies that an admin onboarding an employee immediately approves & provisions without pending loop."""
    try:
        payload = {
            "github_login": "test-new-dev",
            "name": "Test New Dev",
            "email": "testdev@payhive.internal",
            "repo_name": "payhive-eng/payment-gateway",
            "access_level": "Write",
            "duration_hours": 0,
            "business_reason": "Direct administrative onboarding of backend developer",
        }
        resp = client.post("/api/approvals", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "Approved"
        assert data["person"] == "Test New Dev"
        assert data["access"] == "Write"
        assert data["repo"] == "payhive-eng/payment-gateway"

        # Verify assignment is active in DB
        assign_resp = client.get("/api/assignments?q=testdev@payhive.internal", headers=auth_headers)
        assert assign_resp.status_code == 200
        items = assign_resp.json()["items"]
        assert len(items) >= 1
        assert any(a["repo"] == "payhive-eng/payment-gateway" and a["access"] == "Write" for a in items)
    finally:
        client.post("/api/admin/reset-sample", headers=auth_headers)


def test_public_request_pending_and_approval_workflow(client: TestClient, auth_headers: dict):
    """Verifies public requests queue as Pending, and Admin approval completes onboarding."""
    try:
        payload = {
            "github_login": "external-contributor",
            "name": "External Contributor",
            "email": "external.contrib@example.com",
            "repo_name": "payhive-eng/mobile-app",
            "access_level": "Read",
            "duration_hours": 24,
            "business_reason": "Security audit collaborator",
        }
        # Unauthenticated public request
        resp = client.post("/api/requests/public", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "Pending"
        req_id = data["id"]

        # Pending in approvals queue
        q_resp = client.get("/api/approvals?status=Pending", headers=auth_headers)
        assert q_resp.status_code == 200
        pending_ids = [r["id"] for r in q_resp.json()]
        assert req_id in pending_ids

        # Admin approves external request
        dec_resp = client.post(
            f"/api/approvals/{req_id}/decision",
            json={"action": "Approved", "note": "Approved contractor read access for 24h"},
            headers=auth_headers,
        )
        assert dec_resp.status_code == 200
        assert dec_resp.json()["status"] == "Approved"

        # Verify assignment exists
        a_resp = client.get("/api/assignments?q=external.contrib@example.com", headers=auth_headers)
        assert a_resp.status_code == 200
        items = a_resp.json()["items"]
        assert len(items) >= 1
        assert items[0]["access"] == "Read"
    finally:
        client.post("/api/admin/reset-sample", headers=auth_headers)
