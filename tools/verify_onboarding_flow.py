import os
import sys

sys.path.insert(0, r"D:\AccessReaper-v2\backend")
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Identity, GitHubIdentityMap, Assignment, AccessRequest, AuditLog

client = TestClient(app)
headers = {"X-Dev-User": "admin@payhive-eng.internal"}

print("1. Submitting access request for new employee @suleman-newhire...")
req_payload = {
    "github_login": "suleman-newhire",
    "name": "Suleman Newhire",
    "email": "suleman.newhire@payhive.internal",
    "repo_name": "payhive-eng/payment-gateway",
    "access_level": "Write",
    "duration_hours": 24,
    "business_reason": "Joining payment engineering squad sprint 4 - need repository contributor access."
}

res = client.post("/api/approvals", json=req_payload, headers=headers)
print("Create response code:", res.status_code)
if res.status_code != 200:
    print("Error:", res.text)
    sys.exit(1)

created = res.json()
print("Created request:", created["id"], "| person:", created["person"], "| isNewEmployee:", created["isNewEmployee"])
assert created["isNewEmployee"] is True, f"Expected isNewEmployee=True, got {created.get('isNewEmployee')}"
assert created["githubLogin"] == "suleman-newhire", f"Expected githubLogin=suleman-newhire, got {created.get('githubLogin')}"
req_id = created["id"]
print(f"Request ID: {req_id} generated successfully!")

print("\n2. Querying approval decision queue...")
res = client.get("/api/approvals?status=Pending", headers=headers)
assert res.status_code == 200
pending_list = res.json()
found = next((r for r in pending_list if r["id"] == req_id), None)
assert found is not None, "Created request not found in pending queue"
assert found["isNewEmployee"] is True
print("Pending request successfully verified in queue with isNewEmployee=True!")

print("\n3. Deciding approval with action='Approved' (One-Click Onboard & Grant)...")
decision_payload = {
    "action": "Approved",
    "note": "Approved new employee onboarding. Granted Write permissions on payment-gateway."
}
res = client.post(f"/api/approvals/{req_id}/decision", json=decision_payload, headers=headers)
print("Decision response code:", res.status_code)
if res.status_code != 200:
    print("Error:", res.text)
    sys.exit(1)

decided = res.json()
print("Decided request status:", decided["status"])
assert decided["status"] == "Approved"

print("\n4. Verifying database state post-approval...")
db = SessionLocal()
assignment = None
gh_map = None
identity = None
try:
    # Verify Identity
    identity = db.query(Identity).filter(Identity.email == "suleman.newhire@payhive.internal").first()
    assert identity is not None, "Identity was not provisioned"
    print(f"[OK] Identity provisioned: {identity.name} ({identity.email}), role: {identity.job_role}")

    # Verify GitHubIdentityMap
    gh_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == "suleman-newhire").first()
    assert gh_map is not None, "GitHubIdentityMap entry was not created"
    print(f"[OK] GitHub mapped: @{gh_map.login} -> {gh_map.email}")

    # Verify Assignment
    assignment = db.query(Assignment).filter(
        Assignment.identity_id == identity.id
    ).first()
    assert assignment is not None, "Assignment was not created"
    assert assignment.access_level == "Write", f"Expected Write, got {assignment.access_level}"
    print(f"[OK] Assignment created: {assignment.id} with {assignment.access_level} access, JIT temporary={assignment.is_temporary}")

    # Verify AuditLog
    audit = db.query(AuditLog).filter(AuditLog.request_id == req_id).first()
    assert audit is not None, "AuditLog entry was not written"
    print(f"[OK] AuditLog written: {audit.id} - {audit.title} - {audit.detail}")

    print("\nALL 4 PHASES VERIFIED SUCCESSFULLY WITH 100% ACCURACY AND CONSISTENCY!")
finally:
    # Clean up test rows (except append-only audit log)
    if assignment:
        if assignment.finding:
            db.delete(assignment.finding)
        db.delete(assignment)
    if gh_map:
        db.delete(gh_map)
    req_obj = db.query(AccessRequest).filter(AccessRequest.id == req_id).first()
    if req_obj:
        db.delete(req_obj)
    if identity:
        db.delete(identity)
    db.commit()
    db.close()
    print("Test cleanup completed cleanly.")
