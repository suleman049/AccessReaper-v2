"""
Tests for in-process audit scheduling (Feature 3).
Validates schedule configuration, next-run calculations, overlap protection,
and audit log event generation.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.engine.audit_service import _audit_lock, execute_audit_run


def test_schedule_configuration_and_next_run(client: TestClient, auth_headers: dict):
    # 1. Initial schedule state
    resp = client.get("/api/schedule", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "frequency" in data
    assert "timeOfDay" in data

    # 2. Configure daily schedule at 04:30 PKT
    update_payload = {
        "enabled": True,
        "frequency": "daily",
        "timeOfDay": "04:30",
        "dayOfWeek": None,
    }
    put_resp = client.put("/api/schedule", headers=auth_headers, json=update_payload)
    assert put_resp.status_code == 200
    updated_data = put_resp.json()
    assert updated_data["enabled"] is True
    assert updated_data["frequency"] == "daily"
    assert updated_data["timeOfDay"] == "04:30"
    assert updated_data["nextRun"] is not None
    assert "PKT" in updated_data["formattedNextRun"]

    # 3. Query next-run endpoint
    next_resp = client.get("/api/schedule/next-run", headers=auth_headers)
    assert next_resp.status_code == 200
    next_data = next_resp.json()
    assert next_data["nextRun"] is not None
    assert "PKT" in next_data["formatted"]

    # 4. Configure weekly schedule on Friday at 15:00 PKT
    weekly_payload = {
        "enabled": True,
        "frequency": "weekly",
        "timeOfDay": "15:00",
        "dayOfWeek": "fri",
    }
    put_weekly = client.put("/api/schedule", headers=auth_headers, json=weekly_payload)
    assert put_weekly.status_code == 200
    assert put_weekly.json()["frequency"] == "weekly"
    assert put_weekly.json()["dayOfWeek"] == "fri"

    # 5. Disable schedule (frequency: off)
    off_payload = {
        "enabled": False,
        "frequency": "off",
        "timeOfDay": "09:00",
        "dayOfWeek": None,
    }
    put_off = client.put("/api/schedule", headers=auth_headers, json=off_payload)
    assert put_off.status_code == 200
    assert put_off.json()["enabled"] is False
    assert put_off.json()["nextRun"] is None

    # 6. Verify audit log event recorded Schedule tag
    hist_resp = client.get("/api/history?action=Schedule", headers=auth_headers)
    assert hist_resp.status_code == 200
    events = hist_resp.json()["items"]
    assert len(events) >= 1
    assert any("Audit schedule updated" in e["title"] for e in events)


def test_scheduler_overlap_guard(db_session: Session):
    """
    Asserts that if an audit run is already in progress, a scheduled audit
    skips cleanly without throwing or corrupting state.
    """
    # Acquire the global lock to simulate an in-progress audit
    acquired = _audit_lock.acquire(blocking=False)
    assert acquired, "Could not acquire lock for test"
    try:
        # Scheduled run while locked must return None (skip cleanly)
        result = execute_audit_run(db_session, actor="Scheduled audit", trigger="scheduled")
        assert result is None
    finally:
        _audit_lock.release()

    # Once released, an audit executes normally
    normal_run = execute_audit_run(db_session, actor="Scheduled audit", trigger="scheduled")
    assert normal_run is not None
    assert normal_run.trigger == "scheduled"
    assert normal_run.actor == "Scheduled audit"
