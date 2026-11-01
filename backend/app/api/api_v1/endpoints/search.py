"""
Global workspace search endpoint.
Supplies structured search results matching the command palette groups:
People, Resources, Requests, and Activity.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.security import UserClaims, require_role
from app.db.models import (
    AccessRequest,
    Assignment,
    AuditLog,
)
from app.db.session import get_db

router = APIRouter()


@router.get("/search")
def search_workspace(
    q: str | None = Query("", description="Search term"),
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    query_str = (q or "").strip().lower()
    if not query_str:
        return {
            "identities": [],
            "resources": [],
            "requests": [],
            "events": [],
        }

    # 1. Search Identities / Assignments
    assignments = (
        db.query(Assignment)
        .options(
            joinedload(Assignment.identity),
            joinedload(Assignment.resource),
        )
        .all()
    )

    matching_assignments = [
        a
        for a in assignments
        if query_str in f"{a.identity.name} {a.identity.email} {a.resource.name} {a.resource.source}".lower()
    ]

    seen_emails = set()
    identities_list = []
    for a in matching_assignments:
        if a.identity.email not in seen_emails:
            seen_emails.add(a.identity.email)
            identities_list.append(
                {
                    "id": a.id,
                    "name": a.identity.name,
                    "email": a.identity.email,
                    "role": a.identity.job_role,
                    "team": a.identity.team,
                    "assignmentId": a.id,
                }
            )
            if len(identities_list) >= 5:
                break

    # 2. Search Resources
    seen_resources = set()
    resources_list = []
    for a in matching_assignments:
        key = f"{a.resource.source}:{a.resource.name}"
        if key not in seen_resources:
            seen_resources.add(key)
            resources_list.append(
                {
                    "name": a.resource.name,
                    "source": a.resource.source,
                }
            )
            if len(resources_list) >= 5:
                break

    # 3. Search Requests
    requests = (
        db.query(AccessRequest)
        .options(
            joinedload(AccessRequest.identity),
            joinedload(AccessRequest.resource),
        )
        .all()
    )
    matching_requests = [
        r for r in requests if query_str in f"{r.id} {r.identity.name} {r.resource.name} {r.status}".lower()
    ]
    requests_list = [
        {
            "id": r.id,
            "person": r.identity.name,
            "repo": r.resource.name,
            "status": r.status,
            "access": r.requested_access,
        }
        for r in matching_requests[:4]
    ]

    # 4. Search Activity Events
    events = db.query(AuditLog).order_by(AuditLog.occurred_at.desc()).all()
    matching_events = [
        e for e in events if query_str in f"{e.id} {e.title} {e.detail} {e.note or ''} {e.request_id or ''}".lower()
    ]
    events_list = [
        {
            "id": e.id,
            "title": e.title,
            "detail": e.detail,
            "actor": e.actor,
            "tag": e.tag,
        }
        for e in matching_events[:4]
    ]

    return {
        "identities": identities_list,
        "resources": resources_list,
        "requests": requests_list,
        "events": events_list,
    }
