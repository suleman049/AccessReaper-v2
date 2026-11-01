"""
Pydantic schemas for risk rule configuration in AccessReaper v2.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RulePoints(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dormant: int = Field(ge=0, le=100)
    projectMismatch: int = Field(ge=0, le=100)
    elevatedAccess: int = Field(ge=0, le=100)
    sensitiveResource: int = Field(ge=0, le=100)
    formerEmployee: int = Field(ge=0, le=100)
    contractorAdmin: int = Field(ge=0, le=100)
    firestoreAdmin: int = Field(ge=0, le=100)
    directAdminBypass: int = Field(ge=0, le=100)
    privilegedInactive: int = Field(ge=0, le=100)
    unmatchedAccount: int = Field(default=40, ge=0, le=100)
    unmatchedAccountElevated: int = Field(default=70, ge=0, le=100)
    sodConflict: int = Field(default=50, ge=0, le=100)
    busFactor: int = Field(default=30, ge=0, le=100)
    archivedRepo: int = Field(default=40, ge=0, le=100)
    inactiveOutsideCollaborator: int = Field(default=50, ge=0, le=100)
    dormantIdentity: int = Field(default=30, ge=0, le=100)


class RuleThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    highMin: int = Field(ge=1, le=200)
    mediumMin: int = Field(ge=1, le=200)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "RuleThresholds":
        if self.mediumMin >= self.highMin:
            raise ValueError("mediumMin must be strictly less than highMin")
        return self


class RulesEnabled(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dormant: bool = True
    projectMismatch: bool = True
    elevatedAccess: bool = True
    sensitiveResource: bool = True
    formerEmployee: bool = True
    contractorAdmin: bool = True
    firestoreAdmin: bool = True
    directAdminBypass: bool = True
    privilegedInactive: bool = True
    unmatchedAccount: bool = True
    sodConflict: bool = True
    busFactor: bool = True
    archivedRepo: bool = True
    inactiveOutsideCollaborator: bool = True
    dormantIdentity: bool = True


class RuleConfigPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dormantDays: int = Field(ge=1, le=3650)
    unknownActivityCountsAsDormant: bool = False
    inactiveOutsideCollaboratorDays: int = Field(default=30, ge=1, le=3650)
    dormantIdentityDays: int = Field(default=90, ge=1, le=3650)
    sodConflicts: list[dict[str, Any]] = Field(default_factory=list)
    thresholds: RuleThresholds
    points: RulePoints
    rulesEnabled: RulesEnabled


class RuleConfigCreate(BaseModel):
    config: RuleConfigPayload
    note: str = Field(min_length=1, max_length=500)


class RuleConfigRead(BaseModel):
    version: int
    payload: dict[str, Any]
    createdBy: str
    createdAt: datetime
    note: str
    isActive: bool


class RuleConfigSummary(BaseModel):
    version: int
    createdBy: str
    createdAt: datetime
    note: str
    isActive: bool


class RulePreviewRequest(BaseModel):
    config: RuleConfigPayload


class RulePreviewChange(BaseModel):
    assignmentId: str
    name: str
    resource: str
    oldRisk: str
    newRisk: str
    oldScore: int
    newScore: int


class RulePreviewSummary(BaseModel):
    high: int
    medium: int
    low: int
    currentHigh: int
    currentMedium: int
    currentLow: int


class RulePreviewResponse(BaseModel):
    summary: RulePreviewSummary
    changes: list[RulePreviewChange]


class SoDConflictSchema(BaseModel):
    id: str
    pattern_a: str
    access_a: str
    pattern_b: str
    access_b: str
    description: str
    points: int
    enabled: bool


class SoDConflictCreate(BaseModel):
    pattern_a: str = Field(min_length=1, max_length=100)
    access_a: str = Field(default="Admin", max_length=20)
    pattern_b: str = Field(min_length=1, max_length=100)
    access_b: str = Field(default="Admin", max_length=20)
    description: str = Field(min_length=1, max_length=255)
    points: int = Field(default=50, ge=0, le=100)
    enabled: bool = True
    note: str = Field(min_length=1, max_length=500)


class SoDConflictUpdate(BaseModel):
    pattern_a: str | None = None
    access_a: str | None = None
    pattern_b: str | None = None
    access_b: str | None = None
    description: str | None = None
    points: int | None = None
    enabled: bool | None = None
    note: str = Field(min_length=1, max_length=500)
