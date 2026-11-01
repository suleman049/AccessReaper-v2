import os
import sys

sys.path.insert(0, r"D:\AccessReaper-v2\backend")
from app.db.session import SessionLocal
from app.db.models import Identity, GitHubIdentityMap, Assignment, AccessRequest

db = SessionLocal()
try:
    identity = db.query(Identity).filter(Identity.email == "suleman.newhire@payhive.internal").first()
    if identity:
        assignments = db.query(Assignment).filter(Assignment.identity_id == identity.id).all()
        for a in assignments:
            if a.finding:
                db.delete(a.finding)
            db.delete(a)
        print("Cleaned up assignments")
        db.delete(identity)
        print("Cleaned up identity")

    gh_map = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == "suleman-newhire").first()
    if gh_map:
        db.delete(gh_map)
        print("Cleaned up gh_map")

    reqs = db.query(AccessRequest).filter(AccessRequest.id.in_(["REQ-1050", "REQ-1051", "REQ-1052"])).all()
    for r in reqs:
        db.delete(r)
        print(f"Cleaned up request {r.id}")

    db.commit()
    print("Cleanup successful without touching immutable audit logs!")
finally:
    db.close()
