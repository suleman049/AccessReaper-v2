"""
Rate limiter and daily token budget manager for LLM providers.
Enforces Groq free tier constraints (~30 RPM, 200k daily tokens).
Tracks daily token consumption in the database Settings table.
"""

import logging
import threading
import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Setting

logger = logging.getLogger("accessreaper.llm.budget")

_rate_limit_lock = threading.Lock()
_last_call_timestamp: float = 0.0
# Minimum seconds between outbound calls to prevent burst 429s (e.g. 2.0s = max 30 calls/min)
MIN_SECONDS_BETWEEN_CALLS = 1.0


def wait_for_rate_limit() -> None:
    """
    Simple token-bucket spacing to keep request rates well within Groq limits.
    """
    global _last_call_timestamp
    with _rate_limit_lock:
        now = time.time()
        elapsed = now - _last_call_timestamp
        if elapsed < MIN_SECONDS_BETWEEN_CALLS:
            time.sleep(MIN_SECONDS_BETWEEN_CALLS - elapsed)
        _last_call_timestamp = time.time()


def _get_today_key() -> str:
    return f"llm_tokens_{datetime.now(UTC).strftime('%Y-%m-%d')}"


def get_daily_token_usage(db: Session) -> int:
    """
    Reads the total tokens consumed today from the Setting table.
    """
    key = _get_today_key()
    row = db.query(Setting).filter(Setting.key == key).first()
    if row and row.value:
        try:
            return int(row.value)
        except ValueError:
            return 0
    return 0


def record_token_usage(db: Session, tokens: int) -> int:
    """
    Increments today's token counter in the Setting table.
    """
    if tokens <= 0:
        return get_daily_token_usage(db)

    key = _get_today_key()
    row = db.query(Setting).filter(Setting.key == key).first()
    current = 0
    if row and row.value:
        try:
            current = int(row.value)
        except ValueError:
            current = 0

    new_total = current + tokens
    if row:
        row.value = str(new_total)
    else:
        db.add(Setting(key=key, value=str(new_total)))

    try:
        db.flush()
    except Exception as exc:
        logger.warning("Failed to flush token usage: %s", exc)

    return new_total


def is_budget_exceeded(db: Session, estimated_tokens: int = 500) -> bool:
    """
    Checks if calling an LLM would breach LLM_DAILY_TOKEN_BUDGET.
    """
    budget = settings.LLM_DAILY_TOKEN_BUDGET
    if budget <= 0:
        return False
    used = get_daily_token_usage(db)
    return (used + estimated_tokens) > budget
