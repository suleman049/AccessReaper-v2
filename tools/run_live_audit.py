import sys
sys.path.insert(0, r"D:\AccessReaper-v2\backend")

from app.db.session import SessionLocal
from app.engine.audit_service import execute_audit_run
from app.db.models import AuditRun

db = SessionLocal()
try:
    print("Executing live audit run for payhive-eng...")
    run = execute_audit_run(db=db, actor="Security Admin", trigger="manual")
    db.commit()
    print("Live audit completed successfully!")
    print(f"Run ID: {run.id}, Status: {run.status}, Assignments: {run.assignments}, Identities: {run.identities}")
    print(f"High risk: {run.high}, Medium risk: {run.medium}, Healthy: {run.healthy}, Resolved: {run.resolved}")
    print(f"Sources: {run.sources}")
finally:
    db.close()
