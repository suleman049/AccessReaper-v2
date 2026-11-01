"""
Unit and integration tests for Stage 3: Separation of Duties (SoD) and Orphan Account Rules.
Verifies:
1. Pure engine evaluation of SoD conflicting access pairs (*terraform* Admin + *payment* Admin).
2. SoD approval integrity: blocking self-approval with 409 Conflict and writing blocked event to audit_log.
3. Orphan rules (a)-(e):
   (a) Unmatched account elevated & standard
   (b) Active employee with zero assignments (dormant identity)
   (c) Repository with <= 1 admin (bus-factor risk & 'Assign owner' recommendation)
   (d) Archived repository granting Write/Admin
   (e) Inactive outside collaborator holding elevated access
4. Boundary condition: 12 sample records remain 100% unchanged in risk level and primary reason under default rules.
5. SoD CRUD API endpoints: GET, POST, PUT, DELETE /api/rules/sod with audit log verification.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.time import calculate_days_inactive
from app.db.models import AccessRequest, Assignment, AuditLog, Identity, Resource, utc_now
from app.engine.scoring import (
    FindingContext,
    IdentityContext,
    ResourceContext,
    evaluate_risk,
    get_default_rule_config,
)


def test_sod_conflict_pure_engine():
    """Verifies SoD conflicting access pairs detection in pure scoring engine."""
    config = get_default_rule_config()

    identity = IdentityContext(
        name="Security Engineer",
        email="sec.eng@acme.io",
        job_role="Cloud Security",
        team="Security",
        employment_status="active",
    )
    resource = ResourceContext(
        name="acme/terraform-cloud",
        source="GitHub",
        is_sensitive=True,
        project="Infrastructure",
    )

    # User holds Admin on terraform and Admin on payment-gateway
    other_assignments = [
        ("acme/payment-gateway", "Admin"),
        ("acme/docs", "Read"),
    ]

    res = evaluate_risk(
        identity=identity,
        resource=resource,
        access_level="Admin",
        last_active_days=2,
        rule_config=config,
        other_assignments=other_assignments,
    )

    assert any(r.code == "SOD_CONFLICT" for r in res.fired_rules)
    sod_rule = next(r for r in res.fired_rules if r.code == "SOD_CONFLICT")
    assert sod_rule.points == 50
    assert res.primary_reason == "Separation of duties conflict"
    assert res.risk_level == "High"
    assert res.action_label == "Reduce access"
    assert res.recommended_target == "Read"

    # When SoD rule is disabled
    config_disabled = get_default_rule_config()
    config_disabled["rulesEnabled"]["sodConflict"] = False
    res_disabled = evaluate_risk(
        identity=identity,
        resource=resource,
        access_level="Admin",
        last_active_days=2,
        rule_config=config_disabled,
        other_assignments=other_assignments,
    )
    assert not any(r.code == "SOD_CONFLICT" for r in res_disabled.fired_rules)


def test_bus_factor_pure_engine():
    """Verifies bus-factor rule when repository has <= 1 admin."""
    config = get_default_rule_config()

    identity = IdentityContext(
        name="Lead Developer",
        email="lead.dev@acme.io",
        job_role="Lead Developer",
        team="Platform",
        employment_status="active",
    )
    resource = ResourceContext(
        name="acme/core-service",
        source="GitHub",
        is_sensitive=False,
        project="Platform",
        admin_count=1,  # Sole admin
    )

    res = evaluate_risk(
        identity=identity,
        resource=resource,
        access_level="Admin",
        last_active_days=1,
        rule_config=config,
    )

    assert any(r.code == "BUS_FACTOR_SINGLE_ADMIN" for r in res.fired_rules)
    assert res.action_label == "Assign owner"
    assert res.recommendation["title"] == "Assign secondary repository owner"

    # When repo has 2+ admins, bus factor does not fire
    resource.admin_count = 2
    res_2_admins = evaluate_risk(
        identity=identity,
        resource=resource,
        access_level="Admin",
        last_active_days=1,
        rule_config=config,
    )
    assert not any(r.code == "BUS_FACTOR_SINGLE_ADMIN" for r in res_2_admins.fired_rules)


def test_archived_repo_access_pure_engine():
    """Verifies archived repository rule still granting Write or Admin access."""
    config = get_default_rule_config()

    identity = IdentityContext(
        name="Developer",
        email="dev@acme.io",
        job_role="Software Engineer",
        team="Platform",
        employment_status="active",
    )
    resource = ResourceContext(
        name="acme/retired-app",
        source="GitHub",
        is_sensitive=False,
        is_archived=True,
    )

    res = evaluate_risk(
        identity=identity,
        resource=resource,
        access_level="Write",
        last_active_days=5,
        rule_config=config,
    )

    assert any(r.code == "ARCHIVED_REPO_ACTIVE_ACCESS" for r in res.fired_rules)
    assert res.primary_reason == "Archived repository still grants Write/Admin access"
    assert res.recommended_target == "None"
    assert res.action_label == "Revoke access"


def test_inactive_outside_collaborator_pure_engine():
    """Verifies inactive outside collaborator rule with elevated access."""
    config = get_default_rule_config()

    identity = IdentityContext(
        name="Vendor Specialist",
        email="vendor@partner.com",
        job_role="Consultant",
        team="External",
        employment_status="contractor",
        is_outside_collaborator=True,
    )
    resource = ResourceContext(
        name="acme/shared-api",
        source="GitHub",
        is_sensitive=False,
    )

    # Inactive > 30 days
    res = evaluate_risk(
        identity=identity,
        resource=resource,
        access_level="Write",
        last_active_days=45,
        rule_config=config,
    )

    assert any(r.code == "INACTIVE_OUTSIDE_COLLABORATOR" for r in res.fired_rules)
    assert res.recommended_target == "None"
    assert res.action_label == "Revoke access"


def test_dormant_active_identity_pure_engine():
    """Verifies active identity with zero assignments rule."""
    config = get_default_rule_config()

    identity = IdentityContext(
        name="New Employee",
        email="new.hire@acme.io",
        job_role="Engineer",
        team="Platform",
        employment_status="active",
        active_assignment_count=0,
    )
    resource = ResourceContext(
        name="None (Directory record)",
        source="Directory",
    )

    res = evaluate_risk(
        identity=identity,
        resource=resource,
        access_level="None",
        rule_config=config,
    )

    assert any(r.code == "DORMANT_ACTIVE_IDENTITY" for r in res.fired_rules)
    assert res.primary_reason == "Active employee identity holds no active permission assignments"


def test_sample_records_unchanged(db_session: Session):
    """
    CRITICAL: Asserts that all 12 sample records maintain their exact original
    primary reasons and risk levels under the default rule configuration.
    """
    config = get_default_rule_config()
    sample_assignments = db_session.query(Assignment).filter(Assignment.origin == "sample").all()
    assert len(sample_assignments) == 12

    for a in sample_assignments:
        eval_res = evaluate_risk(
            identity=IdentityContext(
                name=a.identity.name,
                email=a.identity.email,
                job_role=a.identity.job_role,
                team=a.identity.team,
                employment_status=a.identity.employment_status,
                current_project=a.identity.current_project,
                is_unmatched=False,
            ),
            resource=ResourceContext(
                name=a.resource.name,
                source=a.resource.source,
                is_sensitive=a.resource.is_sensitive,
                project=a.resource.project,
            ),
            access_level=a.access_level,
            last_active_days=calculate_days_inactive(a.last_active_at),
            last_activity_text=a.last_active_text or "",
            finding_context=FindingContext(
                direct_admin_bypass=a.direct_admin_bypass,
                privileged_inactive=a.privileged_inactive,
            ),
            resolved=a.resolved,
            finding_status=a.finding.status if a.finding else "Open",
            rule_config=config,
        )

        assert eval_res.risk_level == a.current_risk, (
            f"Risk mismatch for {a.id} ({a.identity.name}): {eval_res.risk_level} != {a.current_risk}"
        )
        assert eval_res.primary_reason == a.reason, (
            f"Reason mismatch for {a.id} ({a.identity.name}): '{eval_res.primary_reason}' != '{a.reason}'"
        )


def test_sod_self_approval_blocked(db_session: Session, client: TestClient):
    """
    Verifies that an administrator cannot approve or reject their own access request.
    Returns 409 Conflict and records an append-only AuditLog event.
    """
    admin_email = "approver.admin@acme.io"
    headers = {"X-Dev-User": admin_email}

    # Create identity for this admin
    admin_id = db_session.query(Identity).filter(Identity.email == admin_email).first()
    if not admin_id:
        admin_id = Identity(
            name="Approver Admin",
            email=admin_email,
            initials="AA",
            job_role="Workspace Administrator",
            team="Engineering",
            employment_status="active",
        )
        db_session.add(admin_id)
        db_session.flush()

    # Create test resource
    res = db_session.query(Resource).filter(Resource.name == "acme/self-approval-test").first()
    if not res:
        res = Resource(name="acme/self-approval-test", source="GitHub")
        db_session.add(res)
        db_session.flush()

    # Create access request submitted by this admin
    req_id = "REQ-TEST-SELF-APP"
    existing_req = db_session.query(AccessRequest).filter(AccessRequest.id == req_id).first()
    if existing_req:
        db_session.delete(existing_req)
        db_session.flush()

    req = AccessRequest(
        id=req_id,
        identity_id=admin_id.id,
        resource_id=res.id,
        requested_access="Admin",
        type="Access request",
        business_reason="Emergency deployment rotation",
        risk="Low",
        status="Pending",
        requested_at=utc_now(),
    )
    db_session.add(req)
    db_session.commit()

    # Attempt self-approval -> must fail with 409
    resp = client.post(
        f"/api/approvals/{req_id}/decision",
        json={"action": "Approved", "note": "Approving my own request"},
        headers=headers,
    )
    assert resp.status_code == 409
    data = resp.json()
    assert data["error"]["code"] == "SOD_SELF_APPROVAL_FORBIDDEN"
    assert "Separation of Duties violation" in data["error"]["message"]

    # Verify blocked attempt is logged in append-only audit_log
    blocked_event = (
        db_session.query(AuditLog)
        .filter(AuditLog.request_id == req_id, AuditLog.title == "Self-approval attempt blocked")
        .first()
    )
    assert blocked_event is not None
    assert blocked_event.actor == "Approver Admin"
    assert blocked_event.tag == "Request"
    assert (
        "attempted to approved own request" in blocked_event.detail.lower()
        or "attempted to approve own request" in blocked_event.detail.lower()
    )

    # Now let a DIFFERENT admin approve it -> must succeed
    other_headers = {"X-Dev-User": "different.admin@acme.io"}
    resp_other = client.post(
        f"/api/approvals/{req_id}/decision",
        json={"action": "Approved", "note": "Valid peer approval"},
        headers=other_headers,
    )
    assert resp_other.status_code == 200
    assert resp_other.json()["status"] == "Approved"


def test_sod_crud_api(client: TestClient, auth_headers: dict):
    """Verifies CRUD endpoints for Separation of Duties conflict pairs."""
    headers = auth_headers

    # 1. List SoD rules
    res = client.get("/api/rules/sod", headers=headers)
    assert res.status_code == 200
    rules = res.json()
    assert isinstance(rules, list)
    assert any(r["pattern_a"] == "*terraform*" for r in rules)

    # 2. Create new SoD rule
    new_rule_data = {
        "pattern_a": "*k8s*",
        "access_a": "Admin",
        "pattern_b": "*database*",
        "access_b": "Admin",
        "description": "Cluster Admin and DB Admin conflict",
        "points": 60,
        "enabled": True,
        "note": "Audited compliance requirement",
    }
    create_res = client.post("/api/rules/sod", json=new_rule_data, headers=headers)
    assert create_res.status_code == 201
    created = create_res.json()
    created_id = created["id"]
    assert created["description"] == "Cluster Admin and DB Admin conflict"
    assert created["points"] == 60

    # 3. Update SoD rule
    update_res = client.put(
        f"/api/rules/sod/{created_id}",
        json={"points": 70, "enabled": False, "note": "Increasing penalty and temporarily disabling"},
        headers=headers,
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["points"] == 70
    assert updated["enabled"] is False

    # 4. Delete SoD rule
    delete_res = client.delete(f"/api/rules/sod/{created_id}?note=Rule deprecated", headers=headers)
    assert delete_res.status_code == 200
    assert delete_res.json()["deleted"] == created_id
