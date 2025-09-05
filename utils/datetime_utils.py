#!/usr/bin/env python3
"""
Centralized UTC datetime utilities for podcast scraper system.
Provides timezone-aware datetime functions to prevent naive/aware comparison issues.
"""

import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from email.utils import parsedate_to_datetime


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


def parse_struct_time_to_utc(time_struct) -> Optional[datetime]:
    """
    Parse RSS feed time struct to UTC datetime.
    Feedparser *_parsed structs are effectively UTC.
    
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


def parse_entry_to_utc(entry) -> Tuple[Optional[datetime], str]:
    """
    Parse RSS entry to UTC datetime with fallback chain.
    
    Args:
        entry: RSS entry object from feedparser
    
    Returns:
        tuple: (datetime or None, source_key) indicating which field was used
    """
    # First try struct time fields (most reliable)
    for key in ("published_parsed", "updated_parsed"):
        time_struct = getattr(entry, key, None) or (entry.get(key) if hasattr(entry, "get") else None)
        dt = parse_struct_time_to_utc(time_struct)
        if dt:
            return to_utc(dt), key
    
    # Fallback to string fields with multiple parsing attempts
    for key in ("published", "updated", "date"):
        date_str = getattr(entry, key, None) or (entry.get(key) if hasattr(entry, "get") else None)
        if not date_str:
            continue
        
        # Try RFC2822 parsing (most common in RSS)
        try:
            dt = parsedate_to_datetime(date_str)
            return to_utc(dt), key
        except Exception:
            pass
        
        # Try ISO8601 parsing (handle Z suffix)
        try:
            clean_str = date_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            return to_utc(dt), key
        except Exception:
            pass
    
    return None, "none"


# Backward compatibility alias
def parse_rss_datetime(time_struct) -> Optional[datetime]:
    """
    Legacy function name - use parse_struct_time_to_utc() for new code.
    """
    return parse_struct_time_to_utc(time_struct)


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