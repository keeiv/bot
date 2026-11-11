"""Time helpers: one place for the time zone and formatting."""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

# The UTC+8 time zone
TZ_OFFSET = timezone(timedelta(hours=8))


def get_current_time_str() -> str:
    """The current time, formatted (month/day hour:minute)."""
    return datetime.now(TZ_OFFSET).strftime("%m/%d %H:%M")


def format_datetime(dt: datetime) -> str:
    """Format a datetime as a full time string (year/month/day hour:minute:second), converted to UTC+8."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_OFFSET).strftime("%Y/%m/%d %H:%M:%S")


def get_now() -> datetime:
    """The current datetime in UTC+8."""
    return datetime.now(TZ_OFFSET)
