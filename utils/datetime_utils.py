#!/usr/bin/env python3
"""
Centralized UTC datetime utilities for podcast scraper system.
Provides timezone-aware datetime functions to prevent naive/aware comparison issues.
"""

import time
from datetime import datetime, timezone, timedelta
from typing import Optional


def now_utc() -> datetime:
    """
    Get current time as timezone-aware UTC datetime.
    
    Returns:
        datetime: Current UTC time with timezone info
    """
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """
    Convert a datetime to UTC timezone.
    
    Args:
        dt: Input datetime (naive or timezone-aware)
    
    Returns:
        datetime: UTC timezone-aware datetime
    """
    if dt.tzinfo is None:
        # Assume naive datetime is already in UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def cutoff_utc(hours: int) -> datetime:
    """
    Get UTC datetime N hours ago.
    
    Args:
        hours: Number of hours back from current time
    
    Returns:
        datetime: UTC datetime N hours ago
    """
    return now_utc() - timedelta(hours=hours)


def ensure_aware_utc(dt: datetime) -> datetime:
    """
    Ensure datetime is timezone-aware and in UTC.
    Alias for to_utc() for backwards compatibility.
    
    Args:
        dt: Input datetime
    
    Returns:
        datetime: UTC timezone-aware datetime
    """
    return to_utc(dt)


def parse_rss_datetime(time_struct) -> Optional[datetime]:
    """
    Parse RSS feed time struct to UTC datetime.
    
    Args:
        time_struct: RSS time struct from feedparser (published_parsed/updated_parsed)
    
    Returns:
        datetime: UTC datetime or None if parsing fails
    """
    if not time_struct:
        return None
    
    try:
        # Convert time struct to naive datetime, then make UTC-aware
        naive_dt = datetime(*time_struct[:6])
        return naive_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None


def set_system_timezone_utc():
    """
    Set system timezone to UTC if possible.
    Call this once at process start for consistency.
    """
    import os
    os.environ['TZ'] = 'UTC'
    
    # Call tzset if available (Unix-like systems)
    if hasattr(time, 'tzset'):
        time.tzset()


# Default timezone constant
DEFAULT_TZ = "UTC"