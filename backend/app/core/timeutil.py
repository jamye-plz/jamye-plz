"""Pure timezone utility functions — no DB or external dependencies.

These are module-level, importable, and fully unit-testable.
"""

from datetime import date as date_cls
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def seoul_day_window(date_str: str, tz_name: str = "Asia/Seoul") -> tuple[datetime, datetime]:
    """Return the UTC-aware [start, end) window for a calendar date in the given timezone.

    Example: "2026-06-25" in Asia/Seoul (UTC+9)
      → start = 2026-06-24T15:00:00+00:00
      → end   = 2026-06-25T15:00:00+00:00

    Args:
        date_str: "YYYY-MM-DD" calendar date in tz_name.
        tz_name: IANA timezone name (default "Asia/Seoul").

    Returns:
        (start_utc, end_utc) both tz-aware UTC datetimes.
    """
    tz = ZoneInfo(tz_name)
    year, month, day = map(int, date_str.split("-"))
    # Midnight in local timezone
    local_start = datetime(year, month, day, 0, 0, 0, tzinfo=tz)
    # Next midnight in local timezone — use date arithmetic so month/year
    # rollovers (e.g. June 30 → July 1) don't raise ValueError.
    next_day = date_cls(year, month, day) + timedelta(days=1)
    local_end = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=tz)
    # Convert to UTC
    start_utc = local_start.astimezone(timezone.utc)
    end_utc = local_end.astimezone(timezone.utc)
    return start_utc, end_utc


def today_str(tz_name: str = "Asia/Seoul") -> str:
    """Return today's date string "YYYY-MM-DD" in the given timezone."""
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    return now_local.strftime("%Y-%m-%d")


def topic_is_unread(
    last_read_at: datetime | None,
    topic_created_at: datetime,
    latest_msg_at: datetime | None,
) -> bool:
    """Pure unread predicate — no DB access.

    A topic is unread when:
    - There is no read record (last_read_at is None), OR
    - last_read_at is older than the later of topic_created_at and latest_msg_at.

    All datetimes must be tz-aware (UTC).
    """
    if last_read_at is None:
        return True
    activity = topic_created_at
    if latest_msg_at is not None and latest_msg_at > activity:
        activity = latest_msg_at
    # Ensure both sides are tz-aware before comparing.
    if last_read_at.tzinfo is None:
        last_read_at = last_read_at.replace(tzinfo=timezone.utc)
    if activity.tzinfo is None:
        activity = activity.replace(tzinfo=timezone.utc)
    return last_read_at < activity
