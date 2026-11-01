"""
Seed data script for AccessReaper v2.
Populates initial sample identities, resources, assignments, findings, requests,
audit run, audit snapshots, and seed audit log events.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import (
    AccessRequest,
    AIExplanation,
    Assignment,
    AuditLog,
    AuditRun,
    AuditSnapshot,
    Finding,
    GitHubConfig,
    Identity,
    Notification,
    NotificationPreference,
    Resource,
    RuleConfig,
    Schedule,
    Setting,
    SoDConflict,
)
from app.db.session import SessionLocal, init_db
from app.engine.gemini_service import (
    generate_fallback_executive_summary,
    generate_fallback_finding_explanation,
)
from app.engine.scoring import (
    FindingContext,
    IdentityContext,
    ResourceContext,
    evaluate_risk,
    get_default_rule_config,
)


def parse_iso(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str)


SEED_PEOPLE = [
    {
        "id": "FND-2841",
        "name": "Alex Morgan",
        "email": "alex.morgan@acme.io",
        "initials": "AM",
        "role": "Senior Engineer",
        "team": "Platform",
        "emp_status": "active",
        "repo": "acme/api-gateway",
        "source": "GitHub",
        "sensitive": True,
        "project": "Platform",
        "access": "Admin",
        "last": "94 days ago",
        "last_days": 94,
        "last_active_at": "2026-07-12T10:30:00+05:00",
        "ctx": None,
    },
    {
        "id": "FND-2842",
        "name": "Maya Chen",
        "email": "maya.chen@acme.io",
        "initials": "MC",
        "role": "Engineering Lead",
        "team": "Infrastructure",
        "emp_status": "active",
        "repo": "acme/terraform-cloud",
        "source": "GitHub",
        "sensitive": True,
        "project": "Infrastructure",
        "access": "Admin",
        "last": "5 days ago",
        "last_days": 5,
        "last_active_at": "2026-10-09T10:30:00+05:00",
        "ctx": FindingContext(direct_admin_bypass=True),
    },
    {
        "id": "FND-2843",
        "name": "Sam Rivera",
        "email": "sam.rivera@acme.io",
        "initials": "SR",
        "role": "Product Designer",
        "team": "Design",
        "emp_status": "active",
        "repo": "acme/customer-portal",
        "source": "GitHub",
        "sensitive": False,
        "project": "Product",
        "access": "Write",
        "last": "18 days ago",
        "last_days": 18,
        "last_active_at": "2026-09-26T10:30:00+05:00",
        "ctx": None,
    },
    {
        "id": "FND-2844",
        "name": "Priya Patel",
        "email": "priya.patel@acme.io",
        "initials": "PP",
        "role": "Software Engineer",
        "team": "Platform",
        "emp_status": "active",
        "repo": "acme/api-gateway",
        "source": "GitHub",
        "sensitive": False,
        "project": "Platform",
        "access": "Write",
        "last": "Yesterday",
        "last_days": 1,
        "last_active_at": "2026-10-13T10:30:00+05:00",
        "ctx": None,
    },
    {
        "id": "FND-2845",
        "name": "Ethan Wright",
        "email": "ethan.wright@acme.io",
        "initials": "EW",
        "role": "Data Analyst",
        "team": "Analytics",
        "emp_status": "active",
        "repo": "acme/data-pipeline",
        "source": "GitHub",
        "sensitive": True,
        "project": "Analytics",
        "access": "Admin",
        "last": "31 days ago",
        "last_days": 31,
        "last_active_at": "2026-09-13T10:30:00+05:00",
        "ctx": FindingContext(privileged_inactive=True),
    },
    {
        "id": "FND-2846",
        "name": "Olivia Park",
        "email": "olivia.park@acme.io",
        "initials": "OP",
        "role": "Frontend Engineer",
        "team": "Product",
        "emp_status": "active",
        "repo": "acme/customer-portal",
        "source": "GitHub",
        "sensitive": False,
        "project": "Product",
        "access": "Write",
        "last": "3 hours ago",
        "last_days": 0,
        "last_active_at": "2026-10-14T07:30:00+05:00",
        "ctx": None,
    },
    {
        "id": "FND-2847",
        "name": "Noah Williams",
        "email": "noah.williams@acme.io",
        "initials": "NW",
        "role": "Contractor",
        "team": "External",
        "emp_status": "contractor",
        "repo": "acme/mobile-app",
        "source": "GitHub",
        "sensitive": False,
        "project": "Mobile",
        "access": "Admin",
        "last": "45 days ago",
        "last_days": 45,
        "last_active_at": "2026-08-30T10:30:00+05:00",
        "ctx": None,
    },
    {
        "id": "FND-2848",
        "name": "Isabella Brown",
        "email": "isabella.brown@acme.io",
        "initials": "IB",
        "role": "QA Engineer",
        "team": "Quality",
        "emp_status": "active",
        "repo": "acme/release-tools",
        "source": "GitHub",
        "sensitive": False,
        "project": "Quality",
        "access": "Read",
        "last": "Today",
        "last_days": 0,
        "last_active_at": "2026-10-14T09:00:00+05:00",
        "ctx": None,
    },
    {
        "id": "FND-2849",
        "name": "Liam Foster",
        "email": "liam.foster@acme.io",
        "initials": "LF",
        "role": "Former Engineer",
        "team": "Former employee",
        "emp_status": "former",
        "repo": "acme/legacy-service",
        "source": "GitHub",
        "sensitive": False,
        "project": "Backend",
        "access": "Write",
        "last": "76 days ago",
        "last_days": 76,
        "last_active_at": "2026-07-30T10:30:00+05:00",
        "ctx": None,
    },
    {
        "id": "FND-2850",
        "name": "Grace Kim",
        "email": "grace.kim@acme.io",
        "initials": "GK",
        "role": "Support Specialist",
        "team": "Support",
        "emp_status": "active",
        "repo": "Customer support console",
        "source": "Firestore",
        "sensitive": False,
        "project": "Support",
        "access": "Admin",
        "last": "12 days ago",
        "last_days": 12,
        "last_active_at": "2026-10-02T10:30:00+05:00",
        "ctx": None,
    },
    {
        "id": "FND-2851",
        "name": "Daniel Brooks",
        "email": "daniel.brooks@acme.io",
        "initials": "DB",
        "role": "Content Manager",
        "team": "Marketing",
        "emp_status": "active",
        "repo": "Content management app",
        "source": "Firestore",
        "sensitive": False,
        "project": "Marketing",
        "access": "Editor",
        "last": "Today",
        "last_days": 0,
        "last_active_at": "2026-10-14T09:00:00+05:00",
        "ctx": None,
    },
    {
        "id": "FND-2852",
        "name": "Zoe Taylor",
        "email": "zoe.taylor@acme.io",
        "initials": "ZT",
        "role": "Finance Analyst",
        "team": "Finance",
        "emp_status": "active",
        "repo": "Finance reporting app",
        "source": "Firestore",
        "sensitive": False,
        "project": "Finance",
        "access": "Viewer",
        "last": "Yesterday",
        "last_days": 1,
        "last_active_at": "2026-10-13T10:30:00+05:00",
        "ctx": None,
    },
]

SEED_APPROVALS = [
    {
        "id": "REQ-1042",
        "email": "maya.chen@acme.io",
        "repo": "acme/terraform-cloud",
        "access": "Write",
        "reason": "Replace direct administrator access with repository write access for on-call coverage",
        "requested": "12 min ago",
        "requested_at": "2026-10-14T10:18:00+05:00",
        "type": "Role change",
        "risk": "Medium",
        "status": "Pending",
    },
    {
        "id": "REQ-1041",
        "email": "alex.morgan@acme.io",
        "repo": "acme/api-gateway",
        "access": "Write",
        "reason": "Incident response rotation",
        "requested": "38 min ago",
        "requested_at": "2026-10-14T09:52:00+05:00",
        "type": "Access request",
        "risk": "Low",
        "status": "Pending",
    },
    {
        "id": "REQ-1038",
        "email": "noah.williams@acme.io",
        "repo": "acme/mobile-app",
        "access": "Write",
        "reason": "Limit contractor access to repository write permissions for mobile release support",
        "requested": "2 hours ago",
        "requested_at": "2026-10-14T08:30:00+05:00",
        "type": "Role change",
        "risk": "High",
        "status": "Pending",
    },
    {
        "id": "REQ-1035",
        "email": "sam.rivera@acme.io",
        "repo": "acme/design-system",
        "access": "Write",
        "reason": "Updated product design responsibilities",
        "requested": "Yesterday",
        "requested_at": "2026-10-13T10:30:00+05:00",
        "type": "Access request",
        "risk": "Low",
        "status": "Pending",
    },
    {
        "id": "REQ-1032",
        "email": "olivia.park@acme.io",
        "repo": "acme/api-gateway",
        "access": "Write",
        "reason": "Release support",
        "requested": "Oct 12",
        "requested_at": "2026-10-12T10:30:00+05:00",
        "type": "Access request",
        "risk": "Low",
        "status": "Approved",
    },
    {
        "id": "REQ-1029",
        "email": "ethan.wright@acme.io",
        "repo": "acme/old-billing",
        "access": "Admin",
        "reason": "Legacy migration complete",
        "requested": "Oct 11",
        "requested_at": "2026-10-11T10:30:00+05:00",
        "type": "Access removal",
        "risk": "Low",
        "status": "Approved",
    },
]

SEED_HISTORY = [
    {
        "id": "EVT-SEED-0",
        "actor": "AccessReaper risk engine",
        "tag": "Risk detected",
        "title": "Admin access flagged for review",
        "detail": "acme/api-gateway · Alex Morgan",
        "note": "",
        "source": "GitHub",
        "assignment_id": "FND-2841",
        "request_id": None,
        "audit_id": None,
        "before": None,
        "after": None,
        "tone": "orange",
        "icon": "−",
        "mode": "DRY_RUN",
        "occurred_at": "2026-10-14T09:42:00+05:00",
    },
    {
        "id": "EVT-SEED-1",
        "actor": "Jordan Davis",
        "tag": "Approved",
        "title": "Access request approved",
        "detail": "acme/design-system · Priya Patel",
        "note": "",
        "source": "GitHub",
        "assignment_id": None,
        "request_id": None,
        "audit_id": None,
        "before": None,
        "after": None,
        "tone": "green",
        "icon": "✓",
        "mode": "DRY_RUN",
        "occurred_at": "2026-10-14T10:18:00+05:00",
    },
    {
        "id": "EVT-SEED-2",
        "actor": "Jordan Davis",
        "tag": "Audit",
        "title": "Quarterly access audit completed",
        "detail": "GitHub and Firestore · Access audit completed",
        "note": "",
        "source": "GitHub + Firestore",
        "assignment_id": None,
        "request_id": None,
        "audit_id": "AUD-20261014-001",
        "before": None,
        "after": None,
        "tone": "gray",
        "icon": "↻",
        "mode": "DRY_RUN",
        "occurred_at": "2026-10-14T09:56:00+05:00",
    },
    {
        "id": "EVT-SEED-3",
        "actor": "Maya Chen",
        "tag": "Request",
        "title": "New access request submitted",
        "detail": "acme/terraform-cloud · Admin access",
        "note": "",
        "source": "GitHub",
        "assignment_id": None,
        "request_id": None,
        "audit_id": None,
        "before": None,
        "after": None,
        "tone": "orange",
        "icon": "+",
        "mode": "DRY_RUN",
        "occurred_at": "2026-10-14T09:31:00+05:00",
    },
    {
        "id": "EVT-SEED-4",
        "actor": "Jordan Davis",
        "tag": "Remediated",
        "title": "Admin access removed",
        "detail": "acme/old-billing · Ethan Wright",
        "note": "",
        "source": "GitHub",
        "assignment_id": None,
        "request_id": None,
        "audit_id": None,
        "before": None,
        "after": None,
        "tone": "green",
        "icon": "✓",
        "mode": "DRY_RUN",
        "occurred_at": "2026-10-13T16:12:00+05:00",
    },
    {
        "id": "EVT-SEED-5",
        "actor": "AccessReaper risk engine",
        "tag": "Risk detected",
        "title": "Dormant account identified",
        "detail": "acme/legacy-service · Liam Foster",
        "note": "",
        "source": "GitHub",
        "assignment_id": "FND-2849",
        "request_id": None,
        "audit_id": None,
        "before": None,
        "after": None,
        "tone": "orange",
        "icon": "−",
        "mode": "DRY_RUN",
        "occurred_at": "2026-10-13T14:08:00+05:00",
    },
    {
        "id": "EVT-SEED-6",
        "actor": "Jordan Davis",
        "tag": "Approved",
        "title": "Access request approved",
        "detail": "acme/api-gateway · Olivia Park",
        "note": "",
        "source": "GitHub",
        "assignment_id": None,
        "request_id": "REQ-1032",
        "audit_id": None,
        "before": None,
        "after": None,
        "tone": "green",
        "icon": "✓",
        "mode": "DRY_RUN",
        "occurred_at": "2026-10-13T11:24:00+05:00",
    },
    {
        "id": "EVT-SEED-7",
        "actor": "Jordan Davis",
        "tag": "Audit",
        "title": "Application role audit completed",
        "detail": "Firestore · 3 applications",
        "note": "",
        "source": "Firestore",
        "assignment_id": None,
        "request_id": None,
        "audit_id": None,
        "before": None,
        "after": None,
        "tone": "gray",
        "icon": "↻",
        "mode": "DRY_RUN",
        "occurred_at": "2026-10-02T14:10:00+05:00",
    },
    {
        "id": "EVT-SEED-8",
        "actor": "Jordan Davis",
        "tag": "Audit",
        "title": "Monthly access audit completed",
        "detail": "GitHub and Firestore · Sample workspace",
        "note": "",
        "source": "GitHub + Firestore",
        "assignment_id": None,
        "request_id": None,
        "audit_id": None,
        "before": None,
        "after": None,
        "tone": "gray",
        "icon": "↻",
        "mode": "DRY_RUN",
        "occurred_at": "2026-09-01T11:30:00+05:00",
    },
]


def _ensure_phase2_seeds(db: Session) -> None:
    # 1. RuleConfig v1
    if db.query(RuleConfig).count() == 0:
        rc = RuleConfig(
            version=1,
            payload=get_default_rule_config(),
            created_by="System baseline",
            created_at=parse_iso("2026-10-14T09:00:00+05:00"),
            note="Default baseline rule weights (Phase 1 calibration)",
            is_active=True,
        )
        db.add(rc)

    # 2. Schedule
    if db.query(Schedule).count() == 0:
        sch = Schedule(
            id=1,
            enabled=True,
            frequency="daily",
            time_of_day="02:00",
            day_of_week=None,
            updated_at=parse_iso("2026-10-14T09:00:00+05:00"),
            updated_by="System baseline",
        )
        db.add(sch)

    # 3. SoD Conflict defaults
    if db.query(SoDConflict).count() == 0:
        sod = SoDConflict(
            id="sod-default-infra-billing",
            pattern_a="*terraform*",
            access_a="Admin",
            pattern_b="*payment*",
            access_b="Admin",
            description="Separation of Duties: Infrastructure Admin and Payment/Billing Admin conflict",
            points=50,
            enabled=True,
            created_at=parse_iso("2026-10-14T09:00:00+05:00"),
        )
        db.add(sod)

    # 4. AuditRun findings snapshot
    initial_run = db.query(AuditRun).filter(AuditRun.id == "AUD-20261014-001").first()
    if initial_run and (not initial_run.findings_snapshot or len(initial_run.findings_snapshot) == 0):
        from app.schemas.serializers import serialize_assignment

        assignments = db.query(Assignment).all()
        snapshots = [serialize_assignment(a).model_dump(by_alias=True) for a in assignments]
        initial_run.findings_snapshot = snapshots
        initial_run.rule_version = 1
        initial_run.trigger = "manual"

    # 5. Stage 4 AI Explanations and Notifications seed
    existing_exp = db.query(AIExplanation).filter(AIExplanation.run_id == "AUD-20261014-001").first()
    if not existing_exp and initial_run:
        now_utc = parse_iso("2026-10-14T09:56:00+05:00")
        db.add(AIExplanation(
            id="EXP-SEED-SUMMARY",
            run_id="AUD-20261014-001",
            finding_id=None,
            summary_text=generate_fallback_executive_summary(initial_run),
            recommendation_text=None,
            model="template-fallback",
            status="fallback",
            generated_at=now_utc,
        ))
        for a in db.query(Assignment).filter(Assignment.current_risk.in_(["High", "Medium"])).all():
            expl, recom = generate_fallback_finding_explanation(a)
            db.add(AIExplanation(
                id=f"EXP-SEED-{a.id}",
                run_id="AUD-20261014-001",
                finding_id=a.id,
                summary_text=expl,
                recommendation_text=recom,
                model="template-fallback",
                status="fallback",
                generated_at=now_utc,
            ))

    # Seed initial notifications if empty
    if db.query(Notification).count() == 0:
        notif_time = parse_iso("2026-10-14T10:00:00+05:00")
        db.add(Notification(
            id="NOTIF-SEED-1",
            admin_email="*",
            event_type="audit_completed",
            title="Access audit completed",
            message="Audit AUD-20261014-001 completed (12 assignments checked; 6 High, 1 Medium).",
            link="#audit",
            is_read=False,
            created_at=notif_time,
        ))
        db.add(Notification(
            id="NOTIF-SEED-2",
            admin_email="*",
            event_type="high_findings",
            title="6 High-risk findings require review",
            message="6 assignments hold critical privilege discrepancies that require immediate review.",
            link="#audit",
            is_read=False,
            created_at=notif_time,
        ))
        db.add(Notification(
            id="NOTIF-SEED-3",
            admin_email="*",
            event_type="approval_overdue",
            title="Pending access approval overdue",
            message="Approval request [REQ-1] for Maya Chen (Admin on acme/terraform-cloud) has been pending > 24 hours.",
            link="#approvals",
            is_read=False,
            created_at=notif_time,
        ))

    if not db.query(NotificationPreference).filter(NotificationPreference.admin_email == "admin@acme.corp").first():
        db.add(NotificationPreference(
            admin_email="admin@acme.corp",
            email_digest_enabled=True,
            in_app_enabled=True,
            updated_at=datetime.now(UTC),
        ))

    db.commit()


def seed_database(db: Session, reset_mode: bool = False):
    """
    Seeds the database with baseline entities.
    If reset_mode is True, resets assignments, approvals, findings, and runs,
    but does NOT touch the append-only audit_log.
    """
    if reset_mode:
        db.query(AIExplanation).delete()
        db.query(Finding).delete()
        db.query(Assignment).delete()
        db.query(AccessRequest).delete()
        db.query(Resource).delete()
        db.query(Identity).delete()
        db.query(AuditRun).delete()
        db.query(AuditSnapshot).delete()
        db.commit()

    # Check if identities already seeded
    if db.query(Identity).count() > 0:
        # Ensure Phase 2 tables (RuleConfig & Schedule) and audit run snapshots are initialized
        _ensure_phase2_seeds(db)
        return

    # 1. Identities and Resources
    identities_by_email = {}
    for p in SEED_PEOPLE:
        if p["email"] not in identities_by_email:
            ident = Identity(
                name=p["name"],
                email=p["email"],
                initials=p["initials"],
                job_role=p["role"],
                team=p["team"],
                employment_status=p["emp_status"],
                current_project=p["project"],
            )
            db.add(ident)
            identities_by_email[p["email"]] = ident

    resources_by_name = {}
    for p in SEED_PEOPLE:
        if p["repo"] not in resources_by_name:
            res = Resource(
                name=p["repo"],
                source=p["source"],
                is_sensitive=p["sensitive"],
                project=p["project"],
            )
            db.add(res)
            resources_by_name[p["repo"]] = res

    # Extra resources from approvals if any
    extra_resources = [
        ("acme/design-system", "GitHub", False, "Design"),
        ("acme/old-billing", "GitHub", False, "Billing"),
    ]
    for name, src, sens, proj in extra_resources:
        if name not in resources_by_name:
            res = Resource(name=name, source=src, is_sensitive=sens, project=proj)
            db.add(res)
            resources_by_name[name] = res

    db.flush()

    # 2. Assignments and Findings
    findings_snapshot_list = []
    for p in SEED_PEOPLE:
        ident = identities_by_email[p["email"]]
        res = resources_by_name[p["repo"]]
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
        )

        detected_at = parse_iso("2026-10-14T09:42:00+05:00")
        finding_status = "Healthy" if eval_res.risk_level == "Low" else "Open"

        assignment = Assignment(
            id=p["id"],
            identity_id=ident.id,
            resource_id=res.id,
            access_level=p["access"],
            last_active_at=parse_iso(p["last_active_at"]),
            last_active_text=p["last"],
            resolved=False,
            reviewed_at=None,
            current_risk=eval_res.risk_level,
            reason=eval_res.primary_reason,
            direct_admin_bypass=bool(p["ctx"] and p["ctx"].direct_admin_bypass),
            privileged_inactive=bool(p["ctx"] and p["ctx"].privileged_inactive),
            origin="sample",
        )
        db.add(assignment)

        finding = Finding(
            id=p["id"],
            assignment_id=p["id"],
            original_reason=eval_res.primary_reason,
            original_severity=eval_res.risk_level,
            original_access=p["access"],
            detected_at=detected_at,
            status=finding_status,
            snapshot={
                "role": p["role"],
                "team": p["team"],
                "source": p["source"],
                "lastActiveAt": p["last_active_at"],
                "lastActivity": p["last"],
            },
            evidence=eval_res.evidence,
        )
        db.add(finding)

        findings_snapshot_list.append(
            {
                "id": p["id"],
                "person": p["name"],
                "email": p["email"],
                "initials": p["initials"],
                "role": p["role"],
                "team": p["team"],
                "repo": p["repo"],
                "source": p["source"],
                "access": p["access"],
                "risk": eval_res.risk_level,
                "score": eval_res.score,
                "reason": eval_res.primary_reason,
                "target": eval_res.recommended_target,
                "action": eval_res.action_label,
                "status": finding_status,
                "detectedAt": "2026-10-14T09:42:00+05:00",
                "evidence": eval_res.evidence,
            }
        )

    db.flush()

    # 3. Access Requests
    for a in SEED_APPROVALS:
        ident = identities_by_email[a["email"]]
        res = resources_by_name[a["repo"]]
        req = AccessRequest(
            id=a["id"],
            identity_id=ident.id,
            resource_id=res.id,
            requested_access=a["access"],
            type=a["type"],
            business_reason=a["reason"],
            risk=a["risk"],
            status=a["status"],
            requested_at=parse_iso(a["requested_at"]),
            requested_text=a["requested"],
            decided_by="Jordan Davis" if a["status"] == "Approved" else None,
            decided_at=parse_iso(a["requested_at"]) if a["status"] == "Approved" else None,
        )
        db.add(req)

    # 4. Initial Audit Run
    audit_run = AuditRun(
        id="AUD-20261014-001",
        completed_at=parse_iso("2026-10-14T09:56:00+05:00"),
        status="Completed",
        actor="Jordan Davis",
        scope=["GitHub", "Firestore"],
        assignments=12,
        identities=12,
        high=6,
        medium=1,
        healthy=5,
        resolved=0,
        sources=[
            {"source": "GitHub", "assignments": 9, "resources": 6},
            {"source": "Firestore", "assignments": 3, "resources": 3},
        ],
        sample=True,
        mode="DRY_RUN",
        rule_version=1,
        trigger="manual",
        findings_snapshot=findings_snapshot_list,
    )
    db.add(audit_run)
    db.flush()

    # 5. Initial Audit Snapshot
    snapshot = AuditSnapshot(
        at=parse_iso("2026-10-14T09:56:00+05:00"),
        label="Initial sample baseline",
        high=6,
        medium=1,
        healthy=5,
        resolved=0,
        assignments=12,
        remediated=1,
    )
    db.add(snapshot)

    # 6. Audit Log Events (only if empty)
    if db.query(AuditLog).count() == 0:
        for evt in SEED_HISTORY:
            log_entry = AuditLog(
                id=evt["id"],
                actor=evt["actor"],
                tag=evt["tag"],
                title=evt["title"],
                detail=evt["detail"],
                note=evt["note"],
                source=evt["source"],
                assignment_id=evt["assignment_id"],
                request_id=evt["request_id"],
                audit_id=evt["audit_id"],
                before=evt["before"],
                after=evt["after"],
                tone=evt["tone"],
                icon=evt["icon"],
                mode=evt["mode"],
                occurred_at=parse_iso(evt["occurred_at"]),
            )
            db.add(log_entry)

    # 7. Initial Rule Config (v1 active)
    if db.query(RuleConfig).count() == 0:
        rc = RuleConfig(
            version=1,
            payload=get_default_rule_config(),
            created_by="System baseline",
            created_at=parse_iso("2026-10-14T09:00:00+05:00"),
            note="Default baseline rule weights (Phase 1 calibration)",
            is_active=True,
        )
        db.add(rc)

    # 8. Initial Schedule
    if db.query(Schedule).count() == 0:
        sch = Schedule(
            id=1,
            enabled=True,
            frequency="daily",
            time_of_day="02:00",
            day_of_week=None,
            updated_at=parse_iso("2026-10-14T09:00:00+05:00"),
            updated_by="System baseline",
        )
        db.add(sch)

    # 9. Initial GitHub Integration Config
    if db.query(GitHubConfig).count() == 0:
        ghc = GitHubConfig(
            id=1,
            org_name=None,
            encrypted_token=None,
            token_last4=None,
            connected=False,
            sync_before_audit=False,
        )
        db.add(ghc)

    # 10. Initial SoD Conflicts
    if db.query(SoDConflict).count() == 0:
        sod = SoDConflict(
            id="sod-default-infra-billing",
            pattern_a="*terraform*",
            access_a="Admin",
            pattern_b="*payment*",
            access_b="Admin",
            description="Separation of Duties: Infrastructure Admin and Payment/Billing Admin conflict",
            points=50,
            enabled=True,
            created_at=parse_iso("2026-10-14T09:00:00+05:00"),
        )
        db.add(sod)

    # 11. Settings
    settings_data = {
        "organizationName": "Acme, Inc.",
        "mode": "DRY_RUN",
        "dataMode": "sample",
        "data_mode": "sample",
        "lastAudit": "Oct 14, 2026, 9:56 AM",
    }
    for k, v in settings_data.items():
        existing = db.query(Setting).filter(Setting.key == k).first()
        if not existing:
            db.add(Setting(key=k, value=v))
        else:
            existing.value = v

    # 12. Stage 4 AI Explanations and Notifications seed
    existing_exp = db.query(AIExplanation).filter(AIExplanation.run_id == "AUD-20261014-001").first()
    if not existing_exp:
        init_run = db.query(AuditRun).filter(AuditRun.id == "AUD-20261014-001").first()
        if init_run:
            now_utc = parse_iso("2026-10-14T09:56:00+05:00")
            db.add(AIExplanation(
                id="EXP-SEED-SUMMARY",
                run_id="AUD-20261014-001",
                finding_id=None,
                summary_text=generate_fallback_executive_summary(init_run),
                recommendation_text=None,
                model="template-fallback",
                status="fallback",
                generated_at=now_utc,
            ))
            for a in db.query(Assignment).filter(Assignment.current_risk.in_(["High", "Medium"])).all():
                expl, recom = generate_fallback_finding_explanation(a)
                db.add(AIExplanation(
                    id=f"EXP-SEED-{a.id}",
                    run_id="AUD-20261014-001",
                    finding_id=a.id,
                    summary_text=expl,
                    recommendation_text=recom,
                    model="template-fallback",
                    status="fallback",
                    generated_at=now_utc,
                ))

    # Seed initial notifications if empty
    if db.query(Notification).count() == 0:
        notif_time = parse_iso("2026-10-14T10:00:00+05:00")
        db.add(Notification(
            id="NOTIF-SEED-1",
            admin_email="*",
            event_type="audit_completed",
            title="Access audit completed",
            message="Audit AUD-20261014-001 completed (12 assignments checked; 6 High, 1 Medium).",
            link="#audit",
            is_read=False,
            created_at=notif_time,
        ))
        db.add(Notification(
            id="NOTIF-SEED-2",
            admin_email="*",
            event_type="high_findings",
            title="6 High-risk findings require review",
            message="6 assignments hold critical privilege discrepancies that require immediate review.",
            link="#audit",
            is_read=False,
            created_at=notif_time,
        ))
        db.add(Notification(
            id="NOTIF-SEED-3",
            admin_email="*",
            event_type="approval_overdue",
            title="Pending access approval overdue",
            message="Approval request [REQ-1] for Maya Chen (Admin on acme/terraform-cloud) has been pending > 24 hours.",
            link="#approvals",
            is_read=False,
            created_at=notif_time,
        ))

    # Default admin preference
    if not db.query(NotificationPreference).filter(NotificationPreference.admin_email == "admin@acme.corp").first():
        db.add(NotificationPreference(
            admin_email="admin@acme.corp",
            email_digest_enabled=True,
            in_app_enabled=True,
            updated_at=datetime.now(UTC),
        ))

    db.commit()
    print("Database seeded successfully!")


if __name__ == "__main__":
    init_db()
    with SessionLocal() as session:
        seed_database(session)
