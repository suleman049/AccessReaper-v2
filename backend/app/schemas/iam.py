"""
Pydantic schemas for AccessReaper v2.
Matches the exact JSON property shapes expected by the frontend (camelCase).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class AIExplanationSchema(BaseModel):
    id: str
    runId: str
    findingId: str | None = None
    summaryText: str
    recommendationText: str | None = None
    model: str
    status: str
    generatedAt: str


class NotificationSchema(BaseModel):
    id: str
    eventType: str
    title: str
    message: str
    link: str | None = None
    isRead: bool
    createdAt: str


class NotificationsResponse(BaseModel):
    unreadCount: int
    notifications: list[NotificationSchema]


class NotificationPreferenceSchema(BaseModel):
    emailDigestEnabled: bool
    inAppEnabled: bool = True


class TestEmailResponse(BaseModel):
    success: bool
    configured: bool
    message: str


class FindingSnapshot(BaseModel):
    role: str
    team: str
    source: str
    lastActiveAt: str | None = None
    lastActivity: str | None = None


class FindingSchema(BaseModel):
    id: str
    originalReason: str
    originalSeverity: str
    originalAccess: str
    detectedAt: str
    status: str
    snapshot: dict[str, Any]
    evidence: list[str]
    aiExplanation: str | None = None
    aiRecommendation: str | None = None
    aiStatus: str | None = None
    aiModel: str | None = None


class PersonSchema(BaseModel):
    id: str
    name: str
    email: str
    initials: str
    role: str
    team: str
    repo: str
    source: str
    access: str
    risk: str
    last: str
    lastActiveAt: str | None = None
    reason: str
    resolved: bool = False
    score: int = 0
    scoreBreakdown: list[dict[str, Any]] = Field(default_factory=list)
    reviewedAt: str | None = None
    isTemporary: bool = False
    expiresAt: str | None = None
    employmentStatus: str | None = None
    finding: FindingSchema


class ApprovalSchema(BaseModel):
    id: str
    person: str
    email: str
    initials: str
    repo: str
    access: str
    reason: str
    requested: str
    requestedAt: str | None = None
    durationHours: float | None = None
    expiresAt: str | None = None
    type: str
    risk: str
    status: str
    githubLogin: str | None = None
    isNewEmployee: bool = False


class HistoryEventChange(BaseModel):
    field: str
    before: str | None = None
    after: str | None = None


class HistoryEventSchema(BaseModel):
    id: str
    day: str
    date: str
    time: str
    occurredAt: str
    icon: str
    tone: str
    title: str
    actor: str
    detail: str
    tag: str
    note: str = ""
    source: str = ""
    assignmentId: str | None = None
    requestId: str | None = None
    auditId: str | None = None
    before: str | None = None
    after: str | None = None
    mode: str = "LIVE_GITHUB"
    changes: list[HistoryEventChange] = []


class SourceBreakdown(BaseModel):
    source: str
    assignments: int
    resources: int


class AuditRunSchema(BaseModel):
    id: str
    completedAt: str
    status: str
    actor: str
    scope: list[str]
    assignments: int
    identities: int
    high: int
    medium: int
    healthy: int
    resolved: int
    sources: list[SourceBreakdown]
    sample: bool = True
    mode: str = "LIVE_GITHUB"
    ruleVersion: int = 1
    trigger: str = "manual"
    degradedReason: str | None = None
    aiSummary: AIExplanationSchema | None = None


class AuditSnapshotSchema(BaseModel):
    at: str
    label: str
    high: int
    medium: int
    healthy: int
    resolved: int
    assignments: int
    remediated: int


class BootstrapResponse(BaseModel):
    people: list[PersonSchema]
    approvals: list[ApprovalSchema]
    history: list[HistoryEventSchema]
    auditRuns: list[AuditRunSchema]
    auditSnapshots: list[AuditSnapshotSchema]
    lastAudit: str
    dataMode: str = "sample"
    automation: dict[str, Any] | None = None
    llmStatus: dict[str, Any] | None = None
    unmatchedGitHub: list[dict[str, Any]] | None = None


class UserMeResponse(BaseModel):
    uid: str
    email: str
    name: str
    role: str
    status: str
    organizationId: str


class DashboardSummary(BaseModel):
    identities: int
    assignments: int
    github: int
    firestore: int
    high: int
    medium: int
    healthy: int
    resolved: int
    pending: int
    healthScore: int = 100
    healthGrade: str = "A+"
    healthStatus: str = "Optimal"
    activeJitCount: int = 0
    dormantCount: int = 0


class TrendPoint(BaseModel):
    date: str
    high: int | None = None
    remediated: int | None = None


class NoteRequest(BaseModel):
    note: str = Field(..., min_length=1, max_length=500, description="Business rationale for decision")
    target_access: str | None = Field(None, description="Optional target access level (e.g. None to revoke completely, Read to reduce)")
    action: str | None = Field(None, description="Optional action type (e.g. 'revoke' or 'reduce')")


class ApprovalDecisionRequest(BaseModel):
    action: Literal["Approved", "Declined"]
    note: str = Field(..., min_length=1, max_length=500, description="Business rationale for decision")


class CreateApprovalRequest(BaseModel):
    identity_id: str | None = None
    email: str | None = None
    name: str | None = None
    github_login: str | None = None
    repo_name: str
    access_level: str = "Write"
    type: str = "Access request"
    duration_hours: float | None = None
    business_reason: str = Field(..., min_length=1, max_length=500, description="Business reason for access")


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
