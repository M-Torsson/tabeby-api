# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.

from datetime import datetime, timezone, timedelta
from typing import Optional

# Iraq timezone: UTC+3 (no DST - daylight saving time)
IRAQ_TZ = timezone(timedelta(hours=3))
IRAQ_TZ_NAME = "Asia/Baghdad"


def now_iraq() -> datetime:
    """
    Get current datetime in Iraq timezone (UTC+3)
    Returns timezone-aware datetime object
    """
    return datetime.now(IRAQ_TZ)


def utc_to_iraq(dt: datetime) -> datetime:
    """
    Convert UTC datetime to Iraq timezone
    """
    if dt is None:
        return None
    
    # If naive datetime, assume it's UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Convert to Iraq timezone
    return dt.astimezone(IRAQ_TZ)


def iraq_to_utc(dt: datetime) -> datetime:
    """
    Convert Iraq datetime to UTC
    """
    if dt is None:
        return None
    
    # If naive datetime, assume it's Iraq time
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IRAQ_TZ)
    
    # Convert to UTC
    return dt.astimezone(timezone.utc)


def format_iraq_datetime(dt: Optional[datetime], format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[str]:
    """
    Format datetime in Iraq timezone
    """
    if dt is None:
        return None
    
    iraq_dt = utc_to_iraq(dt)
    return iraq_dt.strftime(format_str)


def parse_iraq_datetime(date_string: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    Parse datetime string as Iraq timezone and return UTC
    """
    # Parse the string as naive datetime
    dt = datetime.strptime(date_string, format_str)
    
    # Set Iraq timezone
    dt = dt.replace(tzinfo=IRAQ_TZ)
    
    # Return as UTC for storage
    return dt.astimezone(timezone.utc)


# Legacy support: keep utcnow for backward compatibility
def now_utc_for_storage() -> datetime:
    """
    Get current UTC time for database storage (standard UTC)
    Returns naive datetime in UTC timezone
    """
    return datetime.utcnow()
