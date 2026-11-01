"""
Pydantic schemas for GitHub IAM integration endpoints.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GitHubConfigPayload(BaseModel):
    org: str = Field(min_length=1, max_length=100)
    token: str = Field(min_length=1)
    sync_before_audit: bool | None = None


class GitHubTestPayload(BaseModel):
    org: str | None = None
    token: str | None = None


class GitHubSyncRunSummary(BaseModel):
    id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    request_count: int
    repos_count: int
    members_count: int
    collaborators_count: int
    assignments_created: int
    assignments_updated: int
    assignments_revoked: int
    error_summary: str | None = None


class GitHubStatusResponse(BaseModel):
    connected: bool
    org_name: str | None = None
    token_last4: str | None = None
    scopes: list[str] = Field(default_factory=list)
    last_sync: GitHubSyncRunSummary | None = None
    sync_before_audit: bool = False
    data_mode: str = "sample"


class GitHubTestResponse(BaseModel):
    ok: bool
    message: str
    user: str | None = None
    org: str | None = None
    scopes: list[str] = Field(default_factory=list)


class GitHubMapPayload(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class GitHubUnmatchedItem(BaseModel):
    login: str
    name: str | None = None
    assignments_count: int
    highest_risk: str
    assignments: list[dict[str, Any]] = Field(default_factory=list)
    account_type: str = "user"
    note: str | None = None


class BulkMapItem(BaseModel):
    login: str
    email: str


class BulkMapPayload(BaseModel):
    mappings: list[BulkMapItem]


class ClassificationPayload(BaseModel):
    accountType: str = Field(pattern="^(user|bot|service|ignored)$")
    note: str | None = None


class AutoSuggestItem(BaseModel):
    login: str
    suggestedEmail: str
    suggestedName: str
    confidence: float


class DataModePayload(BaseModel):
    data_mode: str = Field(pattern="^(sample|live)$")


class IdentityUpdatePayload(BaseModel):
    employment_status: str = Field(pattern="^(active|former|contractor)$")
    note: str = Field(min_length=1, max_length=500)
