"""
Tests for audit log immutability.
Verifies that SQLite triggers prohibit UPDATE and DELETE on audit_log.
"""

import pytest
from sqlalchemy.exc import DBAPIError

from app.db.models import AuditLog
from app.db.session import SessionLocal, init_db


def test_audit_log_update_prevented():
    init_db()
    with SessionLocal() as db:
        first_evt = db.query(AuditLog).first()
        assert first_evt is not None, "Audit log should have at least one seed event"

        # Attempt update
        first_evt.title = "Altered title"
        with pytest.raises(DBAPIError) as exc_info:
            db.commit()
        db.rollback()
        assert "audit_log is append-only: UPDATE is prohibited" in str(exc_info.value)


def test_audit_log_delete_prevented():
    init_db()
    with SessionLocal() as db:
        first_evt = db.query(AuditLog).first()
        assert first_evt is not None

        # Attempt delete
        db.delete(first_evt)
        with pytest.raises(DBAPIError) as exc_info:
            db.commit()
        db.rollback()
        assert "audit_log is append-only: DELETE is prohibited" in str(exc_info.value)
