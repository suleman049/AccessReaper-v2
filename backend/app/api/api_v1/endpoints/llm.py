"""
LLM Status and management endpoints for AccessReaper v2.
Exposes read-only configuration status (provider order, configured flags, token budget vs usage).
Zero API keys or secrets are ever exposed.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import UserClaims, require_role
from app.db.session import get_db
from app.services.llm.manager import llm_manager

router = APIRouter()


@router.get("/llm/status", response_model=dict[str, Any])
def get_llm_status(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Returns read-only operational status of LLM providers.
    Safe for frontend and audit display: reports only configured boolean,
    daily token budget, and current day's token usage.
    """
    return llm_manager.get_status(db)
