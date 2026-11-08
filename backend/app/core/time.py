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


def calculate_days_inactive(dt: datetime | None, origin: str | None = None) -> int | None:
    """Calculates days inactive relative to current time for live GitHub data, or 2026-10-14 anchor for sample seed records."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    
    if origin == "sample":
        anchor = datetime(2026, 10, 14, 10, 30, tzinfo=dt.tzinfo)
        diff = (anchor - dt).total_seconds()
        return max(0, int(diff // 86400))

    now = datetime.now(timezone.utc)
    diff = (now - dt).total_seconds()
    if diff <= 0:
        return 0

    if origin != "github" and dt <= datetime(2026, 10, 14, 10, 30, tzinfo=dt.tzinfo):
        anchor = datetime(2026, 10, 14, 10, 30, tzinfo=dt.tzinfo)
        diff_anchor = (anchor - dt).total_seconds()
        return max(0, int(diff_anchor // 86400))

    return int(diff // 86400)
