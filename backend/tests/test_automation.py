"""
Tests for Stage 1: Fully Automated 24-Hour IAM Audits.
Verifies status queries, countdown calculation, pause/resume validation with required notes,
audit logging of configuration changes, catch-up logic, and manual audit endpoint restrictions.
"""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AuditLog, AuditRun, Schedule, utc_now
from app.engine.automation import (
    check_and_run_catchup,
)


def test_get_automation_status(client: TestClient, auth_headers: dict):
    resp = client.get("/api/automation/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["intervalHours"] == 24
    assert data["timeOfDay"] in ("02:00", "09:00", "04:30")
    assert "nextRunAt" in data
    assert "secondsUntilNext" in data
    assert "serverTime" in data
    assert "isRunning" in data


def test_pause_automation_requires_note(client: TestClient, auth_headers: dict):
    # Attempting to pause without a note must fail with 422
    resp = client.put(
        "/api/automation/config",
        headers=auth_headers,
        json={"enabled": False, "timeOfDay": "02:00", "note": ""},
    )
    assert resp.status_code == 422
    err = resp.json()
    assert err["error"]["code"] == "NOTE_REQUIRED"


def test_pause_and_resume_automation_with_audit_log(client: TestClient, auth_headers: dict, db_session: Session):
    # 1. Pause with note
    pause_note = "Scheduled data center maintenance window"
    resp = client.put(
        "/api/automation/config",
        headers=auth_headers,
        json={"enabled": False, "timeOfDay": "02:00", "note": pause_note},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False
    assert data["pauseNote"] == pause_note
    assert data["nextRunAt"] is None
    assert data["secondsUntilNext"] == 0

    # Verify audit log event
    log_pause = (
        db_session.query(AuditLog)
        .filter(AuditLog.title == "Automatic audits paused")
        .order_by(AuditLog.occurred_at.desc())
        .first()
    )
    assert log_pause is not None
    assert log_pause.note == pause_note
    assert log_pause.actor == "Jordan Davis"

    # 2. Resume
    resp2 = client.put(
        "/api/automation/config",
        headers=auth_headers,
        json={"enabled": True, "timeOfDay": "02:00", "note": "Maintenance concluded"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["enabled"] is True
    assert data2["pauseNote"] is None
    assert data2["nextRunAt"] is not None
    assert data2["secondsUntilNext"] > 0

    # Verify resume audit log event
    log_resume = (
        db_session.query(AuditLog)
        .filter(AuditLog.title == "Automatic audits resumed")
        .order_by(AuditLog.occurred_at.desc())
        .first()
    )
    assert log_resume is not None
    assert log_resume.actor == "Jordan Davis"


def test_update_time_of_day(client: TestClient, auth_headers: dict):
    resp = client.put(
        "/api/automation/config",
        headers=auth_headers,
        json={"enabled": True, "timeOfDay": "04:30", "note": "Adjusted time to off-peak"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["timeOfDay"] == "04:30"
    assert data["enabled"] is True


def test_manual_audit_endpoint_restriction(client: TestClient, auth_headers: dict, monkeypatch):
    # When ALLOW_MANUAL_AUDIT is False, POST /api/audits/run must return 403
    monkeypatch.setattr(settings, "ALLOW_MANUAL_AUDIT", False)
    resp = client.post("/api/audits/run", headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "MANUAL_AUDIT_DISABLED"

    # When ALLOW_MANUAL_AUDIT is True, it succeeds
    monkeypatch.setattr(settings, "ALLOW_MANUAL_AUDIT", True)
    resp2 = client.post("/api/audits/run", headers=auth_headers)
    assert resp2.status_code == 200
    assert "id" in resp2.json()


def test_catchup_audit_execution(db_session: Session):
    # Simulate an enabled schedule where last automatic run was 26 hours ago
    sch = db_session.query(Schedule).first()
    sch.enabled = True
    sch.last_run_at = utc_now() - timedelta(hours=26)
    db_session.commit()

    initial_run_count = db_session.query(AuditRun).filter(AuditRun.trigger == "scheduled").count()

    # Trigger catchup check with the active test session
    check_and_run_catchup(db=db_session)

    final_run_count = db_session.query(AuditRun).filter(AuditRun.trigger == "scheduled").count()
    assert final_run_count == initial_run_count + 1

    latest_run = (
        db_session.query(AuditRun)
        .filter(AuditRun.trigger == "scheduled")
        .order_by(AuditRun.completed_at.desc())
        .first()
    )
    assert latest_run is not None
    assert latest_run.actor == "Automatic audit (catch-up)"
