import sys
sys.path.insert(0, r"D:\AccessReaper-v2\backend")

from app.db.session import SessionLocal
from app.integrations.github.sync import run_github_sync
from app.engine.audit_service import execute_audit_run
from app.db.models import Setting

db = SessionLocal()

print("1. Running live GitHub sync for payhive-eng...")
sync_res = run_github_sync(db, actor_email="admin@payhive-eng.internal", trigger="manual")
print(f"   Sync completed: {sync_res.id}, repos={sync_res.repos_count}, members={sync_res.members_count}, assignments_updated={sync_res.assignments_updated}")

print("2. Running fresh IAM audit run...")
audit_run = execute_audit_run(db, actor="Security Admin", trigger="manual")
print(f"   Audit run completed: {audit_run.id}, assignments={audit_run.assignments}, high={audit_run.high}, medium={audit_run.medium}, healthy={audit_run.healthy}, resolved={audit_run.resolved}")

print("3. Updating settings...")
db.query(Setting).filter(Setting.key == "lastAudit").update({"value": "Just now"})
db.commit()
db.close()
print("Live sync and audit completed successfully.")
