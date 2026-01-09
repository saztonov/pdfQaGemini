"""Time utilities for timezone conversion"""

from datetime import datetime, timedelta


# UTC offset in hours (Moscow time: UTC+3)
UTC_OFFSET_HOURS = 3


def utc_to_local(dt: datetime) -> datetime:
    """
    Convert UTC datetime to local time.

    Args:
        dt: UTC datetime object

    Returns:
        datetime: Local datetime (UTC + offset)
    """
    if dt is None:
        return None

    # Add offset to convert from UTC to local time
    return dt + timedelta(hours=UTC_OFFSET_HOURS)


def format_time(dt: datetime, format_str: str = "%H:%M:%S") -> str:
    """
    Format UTC datetime as local time string.

    Args:
        dt: UTC datetime object
        format_str: strftime format string

    Returns:
        str: Formatted local time string
    """
    if dt is None:
        return ""

    local_dt = utc_to_local(dt)
    return local_dt.strftime(format_str)
