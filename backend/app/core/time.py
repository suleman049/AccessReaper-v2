"""
Timezone and date helpers for AccessReaper v2.
Guarantees Asia/Karachi timezone is always available across platforms.
"""

from datetime import UTC, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    KARACHI_TZ = ZoneInfo("Asia/Karachi")
except Exception:
    KARACHI_TZ = timezone(timedelta(hours=5), name="PKT")


def calculate_days_inactive(dt: datetime | None) -> int | None:
    """Calculates days inactive relative to the 2026-10-14 anchor date."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    anchor = datetime(2026, 10, 14, 10, 30, tzinfo=dt.tzinfo)
    diff = (anchor - dt).total_seconds()
    return max(0, int(diff // 86400))
