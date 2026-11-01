"""
API router registering all v1 endpoints.
"""

from fastapi import APIRouter

from app.api.api_v1.endpoints import (
    admin,
    approvals,
    assignments,
    audits,
    auth,
    automation,
    bootstrap,
    dashboard,
    github,
    health,
    history,
    identities,
    llm,
    notifications,
    rules,
    schedules,
    search,
    users,
    webhooks,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, tags=["Auth"])
api_router.include_router(bootstrap.router, tags=["Bootstrap"])
api_router.include_router(automation.router, tags=["Automation"])
api_router.include_router(dashboard.router, tags=["Dashboard"])
api_router.include_router(assignments.router, tags=["Assignments"])
api_router.include_router(approvals.router, tags=["Approvals"])
api_router.include_router(audits.router, tags=["Audits"])
api_router.include_router(history.router, tags=["History"])
api_router.include_router(search.router, tags=["Search"])
api_router.include_router(admin.router, tags=["Admin"])
api_router.include_router(users.router, tags=["Users"])
api_router.include_router(rules.router, tags=["Rules"])
api_router.include_router(schedules.router, tags=["Schedules"])
api_router.include_router(github.router, tags=["GitHub Integration"])
api_router.include_router(identities.router, tags=["Identities"])
api_router.include_router(llm.router, tags=["LLM"])
api_router.include_router(notifications.router, tags=["Notifications"])
api_router.include_router(webhooks.router, tags=["Webhooks"])
