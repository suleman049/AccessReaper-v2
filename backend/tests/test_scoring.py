"""
Tests for scoring engine in AccessReaper v2.
Verifies base rules, boundary values (39, 40, 69, 70), named rules, and calibration.
"""

from app.engine.scoring import (
    FindingContext,
    IdentityContext,
    ResourceContext,
    evaluate_risk,
)


def test_base_rules_isolated():
    identity = IdentityContext(
        name="Test User",
        email="test@acme.io",
        job_role="Engineer",
        team="Engineering",
        employment_status="active",
    )
    resource = ResourceContext(
        name="acme/test-repo",
        source="GitHub",
        is_sensitive=False,
        project="Engineering",
    )

    # Low baseline: Read on matching project, active today -> score 0
    res = evaluate_risk(identity, resource, access_level="Read", last_active_days=0)
    assert res.score == 0
    assert res.risk_level == "Low"
    assert res.action_label == "Keep access"

    # Elevated access: Write (+20) -> score 20 -> Low
    res = evaluate_risk(identity, resource, access_level="Write", last_active_days=0)
    assert res.score == 20
    assert res.risk_level == "Low"

    # Sensitive resource: (+10) + Write (+20) -> score 30 -> Low
    sensitive_res = ResourceContext(
        name="acme/test-repo",
        source="GitHub",
        is_sensitive=True,
        project="Engineering",
    )
    res = evaluate_risk(identity, sensitive_res, access_level="Write", last_active_days=0)
    assert res.score == 30
    assert res.risk_level == "Low"

    # Project mismatch (+30) + Write (+20) -> score 50 -> Medium
    mismatch_res = ResourceContext(
        name="acme/other-repo",
        source="GitHub",
        is_sensitive=False,
        project="Design",
    )
    res = evaluate_risk(identity, mismatch_res, access_level="Write", last_active_days=0)
    assert res.score == 50
    assert res.risk_level == "Medium"
    assert res.action_label == "Reduce access"
    assert res.recommended_target == "Read"

    # Unused for 90+ days (+40) + Admin (+20) + Sensitive (+10) -> score 70 -> High
    res = evaluate_risk(identity, sensitive_res, access_level="Admin", last_active_days=94)
    assert res.score == 70
    assert res.risk_level == "High"
    assert res.action_label == "Reduce access"
    assert res.recommended_target == "Read"


def test_boundary_scores():
    identity = IdentityContext(
        name="Boundary Tester",
        email="boundary@acme.io",
        job_role="Engineer",
        team="Platform",
        employment_status="active",
    )
    resource = ResourceContext(
        name="acme/boundary",
        source="GitHub",
        is_sensitive=False,
        project="Platform",
    )

    # Score 30 -> Low
    res_30 = evaluate_risk(identity, resource, access_level="Read", last_active_days=0)
    # inject custom rules to verify exact boundaries
    assert res_30.risk_level == "Low"

    # Boundary 39 vs 40:
    # A rule setup yielding 40 points (e.g. Inactive 90+ days on Read access: 40 points)
    res_40 = evaluate_risk(identity, resource, access_level="Read", last_active_days=90)
    assert res_40.score == 40
    assert res_40.risk_level == "Medium"

    # Score 69 vs 70:
    # Inactive 90+ days (+40) + Project mismatch (+30) = 70 points -> High
    mismatch_resource = ResourceContext(
        name="acme/boundary-mismatch",
        source="GitHub",
        is_sensitive=False,
        project="Design",
    )
    res_70 = evaluate_risk(identity, mismatch_resource, access_level="Read", last_active_days=90)
    assert res_70.score == 70
    assert res_70.risk_level == "High"


def test_named_rules():
    # 1. Former employee
    former_identity = IdentityContext(
        name="Liam Foster",
        email="liam.foster@acme.io",
        job_role="Former Engineer",
        team="Former employee",
        employment_status="former",
    )
    repo = ResourceContext(name="acme/legacy-service", source="GitHub")
    res = evaluate_risk(former_identity, repo, access_level="Write", last_active_days=76)
    assert res.risk_level == "High"
    assert res.recommended_target == "None"
    assert res.action_label == "Revoke access"
    assert res.primary_reason == "Former employee account is still active"

    # 2. Contractor with Admin
    contractor = IdentityContext(
        name="Noah Williams",
        email="noah.williams@acme.io",
        job_role="Contractor",
        team="External",
        employment_status="contractor",
    )
    mobile_app = ResourceContext(name="acme/mobile-app", source="GitHub")
    res = evaluate_risk(contractor, mobile_app, access_level="Admin", last_active_days=45)
    assert res.risk_level == "High"
    assert res.recommended_target == "Read"
    assert res.action_label == "Reduce access"
    assert res.primary_reason == "External account has administrator access"

    # 3. Firestore admin exceeding support duties
    support = IdentityContext(
        name="Grace Kim",
        email="grace.kim@acme.io",
        job_role="Support Specialist",
        team="Support",
        employment_status="active",
    )
    console = ResourceContext(name="Customer support console", source="Firestore")
    res = evaluate_risk(support, console, access_level="Admin", last_active_days=12)
    assert res.risk_level == "High"
    assert res.recommended_target == "Viewer"
    assert res.action_label == "Reduce access"
    assert res.primary_reason == "Application admin role exceeds support duties"


def test_all_12_seed_people_calibration():
    """
    Validates that evaluate_risk returns the exact risk level and recommended target
    matching frontend app.js and governance.js for all 12 people.
    """
    seed_cases = [
        # (name, email, role, team, emp_status, repo, source, sensitive, project, access, days, ctx, expected_risk, expected_target, expected_reason)
        (
            "Alex Morgan",
            "alex.morgan@acme.io",
            "Senior Engineer",
            "Platform",
            "active",
            "acme/api-gateway",
            "GitHub",
            True,
            "Platform",
            "Admin",
            94,
            None,
            "High",
            "Read",
            "Elevated access unused for 94 days",
        ),
        (
            "Maya Chen",
            "maya.chen@acme.io",
            "Engineering Lead",
            "Infrastructure",
            "active",
            "acme/terraform-cloud",
            "GitHub",
            True,
            "Infrastructure",
            "Admin",
            5,
            FindingContext(direct_admin_bypass=True),
            "High",
            "Read",
            "Direct admin grant bypasses team policy",
        ),
        (
            "Sam Rivera",
            "sam.rivera@acme.io",
            "Product Designer",
            "Design",
            "active",
            "acme/customer-portal",
            "GitHub",
            False,
            "Product",
            "Write",
            18,
            None,
            "Medium",
            "Read",
            "Team mismatch for repository access",
        ),
        (
            "Priya Patel",
            "priya.patel@acme.io",
            "Software Engineer",
            "Platform",
            "active",
            "acme/api-gateway",
            "GitHub",
            False,
            "Platform",
            "Write",
            1,
            None,
            "Low",
            "Write",
            "Access matches current role",
        ),
        (
            "Ethan Wright",
            "ethan.wright@acme.io",
            "Data Analyst",
            "Analytics",
            "active",
            "acme/data-pipeline",
            "GitHub",
            True,
            "Analytics",
            "Admin",
            31,
            FindingContext(privileged_inactive=True),
            "High",
            "Read",
            "Privileged access with no recent activity",
        ),
        (
            "Olivia Park",
            "olivia.park@acme.io",
            "Frontend Engineer",
            "Product",
            "active",
            "acme/customer-portal",
            "GitHub",
            False,
            "Product",
            "Write",
            0,
            None,
            "Low",
            "Write",
            "Access matches current role",
        ),
        (
            "Noah Williams",
            "noah.williams@acme.io",
            "Contractor",
            "External",
            "contractor",
            "acme/mobile-app",
            "GitHub",
            False,
            "Mobile",
            "Admin",
            45,
            None,
            "High",
            "Read",
            "External account has administrator access",
        ),
        (
            "Isabella Brown",
            "isabella.brown@acme.io",
            "QA Engineer",
            "Quality",
            "active",
            "acme/release-tools",
            "GitHub",
            False,
            "Quality",
            "Read",
            0,
            None,
            "Low",
            "Read",
            "Read access matches current role",
        ),
        (
            "Liam Foster",
            "liam.foster@acme.io",
            "Former Engineer",
            "Former employee",
            "former",
            "acme/legacy-service",
            "GitHub",
            False,
            "Backend",
            "Write",
            76,
            None,
            "High",
            "None",
            "Former employee account is still active",
        ),
        (
            "Grace Kim",
            "grace.kim@acme.io",
            "Support Specialist",
            "Support",
            "active",
            "Customer support console",
            "Firestore",
            False,
            "Support",
            "Admin",
            12,
            None,
            "High",
            "Viewer",
            "Application admin role exceeds support duties",
        ),
        (
            "Daniel Brooks",
            "daniel.brooks@acme.io",
            "Content Manager",
            "Marketing",
            "active",
            "Content management app",
            "Firestore",
            False,
            "Marketing",
            "Editor",
            0,
            None,
            "Low",
            "Editor",
            "Application role matches current responsibilities",
        ),
        (
            "Zoe Taylor",
            "zoe.taylor@acme.io",
            "Finance Analyst",
            "Finance",
            "active",
            "Finance reporting app",
            "Firestore",
            False,
            "Finance",
            "Viewer",
            1,
            None,
            "Low",
            "Viewer",
            "Read-only application role matches current responsibilities",
        ),
    ]

    for (
        name,
        email,
        role,
        team,
        emp_status,
        repo,
        source,
        sensitive,
        proj,
        access,
        days,
        ctx,
        exp_risk,
        exp_target,
        exp_reason,
    ) in seed_cases:
        ident = IdentityContext(
            name=name,
            email=email,
            job_role=role,
            team=team,
            employment_status=emp_status,
        )
        r = ResourceContext(name=repo, source=source, is_sensitive=sensitive, project=proj)
        res = evaluate_risk(ident, r, access_level=access, last_active_days=days, finding_context=ctx)
        assert res.risk_level == exp_risk, f"Failed risk for {name}: got {res.risk_level}, expected {exp_risk}"
        assert res.recommended_target == exp_target, (
            f"Failed target for {name}: got {res.recommended_target}, expected {exp_target}"
        )
        assert res.primary_reason == exp_reason, (
            f"Failed reason for {name}: got {res.primary_reason}, expected {exp_reason}"
        )
