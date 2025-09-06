#!/usr/bin/env python3
"""
Feed Processing Helper Functions (Phase 4)
Utility functions for enhanced feed ingestion robustness
"""

import hashlib
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from urllib.parse import urlparse

import requests
import sqlite3
import logging

from utils.datetime_utils import now_utc, to_utc, parse_entry_to_utc

logger = logging.getLogger(__name__)

def item_identity_hash(guid: Optional[str], link: Optional[str], 
                      title: Optional[str], enclosure_url: Optional[str]) -> str:
    """
    Generate stable hash for item deduplication with normalization
    
    Priority: guid > link > title+enclosure_url
    
    Args:
        guid: RSS guid or Atom id
        link: Item link/URL
        title: Item title
        enclosure_url: Audio/video URL
        
    Returns:
        SHA256 hash (64 chars hex)
    """
    import re
    from urllib.parse import urlparse, urlunparse
    
    # Use guid if available (most reliable) - trimmed and lowercased
    if guid and guid.strip():
        key = guid.strip().lower()
    elif link and link.strip():
        # Normalize link URL: strip UTM, lowercase host, remove trailing slash
        try:
            parsed = urlparse(link.strip())
            # Remove UTM parameters and other tracking
            query_parts = []
            if parsed.query:
                for param in parsed.query.split('&'):
                    if not param.lower().startswith(('utm_', 'fbclid', 'gclid')):
                        query_parts.append(param)
            
            # Reconstruct with normalized components
            normalized = urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip('/') if parsed.path != '/' else parsed.path,
                parsed.params,
                '&'.join(query_parts),
                ''  # Remove fragment
            ))
            key = normalized
        except Exception:
            # Fallback to basic cleaning if URL parsing fails
            key = link.strip().lower().rstrip('/')
    elif title and title.strip():
        # Fallback to title + enclosure combination - both normalized
        title_clean = re.sub(r'\s+', ' ', title.strip())  # Normalize whitespace
        enclosure_clean = (enclosure_url or '').strip().lower().rstrip('/')
        key = f"{title_clean}|{enclosure_clean}"
    else:
        # Last resort - random string that will likely be unique
        key = f"unknown_item_{now_utc().isoformat()}"
    
    return hashlib.sha256(key.encode('utf-8')).hexdigest()

def content_hash(title: Optional[str], description: Optional[str]) -> str:
    """
    Generate content hash to detect item updates
    
    Args:
        title: Item title
        description: Item description/summary
        
    Returns:
        SHA256 hash (64 chars hex)
    """
    content = f"{title or ''}|{description or ''}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def get_or_set_first_seen(cursor: sqlite3.Cursor, feed_id: int, 
                         item_hash: str, title: str, guid: str, link: str, 
                         enclosure_url: str, current_time: datetime) -> datetime:
    """
    Get first_seen timestamp for item or set it if first time seen
    
    This provides deterministic timestamps for date-less items
    
    Args:
        cursor: Database cursor
        feed_id: Feed ID
        item_hash: Item identity hash
        title: Item title for storage
        guid: Item GUID for storage
        link: Item link for storage
        enclosure_url: Item enclosure URL for storage
        current_time: Current UTC timestamp
        
    Returns:
        first_seen_utc timestamp
    """
    # Check if item already seen
    cursor.execute(
        "SELECT first_seen_utc FROM item_seen WHERE feed_id = ? AND item_id_hash = ?",
        (feed_id, item_hash)
    )
    result = cursor.fetchone()
    
    if result:
        # Parse stored timestamp back to datetime
        first_seen_str = result[0]
        try:
            if first_seen_str.endswith('Z'):
                first_seen = datetime.fromisoformat(first_seen_str[:-1]).replace(tzinfo=None)
            else:
                first_seen = datetime.fromisoformat(first_seen_str)
            return to_utc(first_seen)
        except (ValueError, TypeError):
            logger.warning(f"Invalid timestamp in item_seen: {first_seen_str}")
            # Fall through to create new record
    
    # First time seeing this item - record it
    cursor.execute('''
        INSERT OR REPLACE INTO item_seen (
            feed_id, item_id_hash, first_seen_utc, last_seen_utc,
            content_hash, guid, link, title, enclosure_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        feed_id, item_hash, current_time.isoformat() + 'Z', current_time.isoformat() + 'Z',
        None, guid, link, title, enclosure_url
    ))
    
    return current_time

def detect_typical_order(entries: List[Any]) -> str:
    """
    Auto-detect typical feed ordering from dated entries
    
    Args:
        entries: List of feed entries
        
    Returns:
        'reverse_chronological', 'chronological', or 'unknown'
    """
    dated_entries = []
    
    # Extract up to 10 entries with valid dates
    for entry in entries[:20]:  # Check first 20 for dates
        pub_date, _ = parse_entry_to_utc(entry)
        if pub_date:
            dated_entries.append(pub_date)
        
        if len(dated_entries) >= 10:
            break
    
    if len(dated_entries) < 3:
        return 'unknown'
    
    # Check if dates are in descending order (reverse chronological)
    reverse_chrono = all(
        dated_entries[i] >= dated_entries[i + 1] 
        for i in range(len(dated_entries) - 1)
    )
    
    if reverse_chrono:
        return 'reverse_chronological'
    
    # Check if dates are in ascending order (chronological)  
    chrono = all(
        dated_entries[i] <= dated_entries[i + 1] 
        for i in range(len(dated_entries) - 1)
    )
    
    if chrono:
        return 'chronological'
    
    return 'unknown'

def get_effective_lookback_hours(cursor: sqlite3.Cursor, feed_id: int, 
                                default_hours: int) -> int:
    """
    Get effective lookback hours for feed (override or default)
    
    Args:
        cursor: Database cursor
        feed_id: Feed ID
        default_hours: Global default lookback hours
        
    Returns:
        Effective lookback hours (1-168 range enforced)
    """
    cursor.execute(
        "SELECT lookback_hours_override FROM feed_metadata WHERE feed_id = ?",
        (feed_id,)
    )
    result = cursor.fetchone()
    
    if result and result[0] is not None:
        # Use per-feed override
        override_hours = result[0]
        # Enforce bounds: 1-168 hours (7 days max)
        return max(1, min(168, override_hours))
    
    # Use global default with bounds enforcement
    return max(1, min(168, default_hours))

def compute_cutoff_with_grace(lookback_hours: int, grace_minutes: int) -> datetime:
    """
    Compute cutoff time with grace period to avoid boundary flapping
    
    Args:
        lookback_hours: How far back to look
        grace_minutes: Grace period to add
        
    Returns:
        UTC cutoff datetime
    """
    base_cutoff = now_utc() - timedelta(hours=lookback_hours)
    cutoff_with_grace = base_cutoff - timedelta(minutes=grace_minutes)
    return cutoff_with_grace

def should_suppress_warning(cursor: sqlite3.Cursor, feed_id: int, 
                           warning_type: str, suppress_hours: int = 24) -> bool:
    """
    Check if warning should be suppressed (already shown recently)
    
    Args:
        cursor: Database cursor
        feed_id: Feed ID
        warning_type: Type of warning ('no_dates', 'stale_feed', etc.)
        suppress_hours: Hours to suppress repeated warnings
        
    Returns:
        True if warning should be suppressed
    """
    suppress_cutoff = now_utc() - timedelta(hours=suppress_hours)
    
    if warning_type == 'no_dates':
        cursor.execute(
            "SELECT last_no_date_warning FROM feed_metadata WHERE feed_id = ?",
            (feed_id,)
        )
        result = cursor.fetchone()
        
        if result and result[0]:
            try:
                last_warning = datetime.fromisoformat(result[0].replace('Z', ''))
                return to_utc(last_warning) > suppress_cutoff
            except (ValueError, TypeError):
                pass
    
    return False

def update_warning_timestamp(cursor: sqlite3.Cursor, feed_id: int, 
                           warning_type: str):
    """
    Update warning timestamp to suppress future warnings
    
    Args:
        cursor: Database cursor
        feed_id: Feed ID
        warning_type: Type of warning
    """
    current_time = now_utc().isoformat() + 'Z'
    
    if warning_type == 'no_dates':
        cursor.execute(
            "UPDATE feed_metadata SET last_no_date_warning = ? WHERE feed_id = ?",
            (current_time, feed_id)
        )

def get_feed_cache_headers(cursor: sqlite3.Cursor, feed_id: int) -> Dict[str, Optional[str]]:
    """
    Get stored cache headers for a feed
    
    Args:
        cursor: Database cursor
        feed_id: Feed ID
        
    Returns:
        Dictionary with etag and last_modified keys
    """
    cursor.execute(
        "SELECT etag, last_modified_http FROM feed_metadata WHERE feed_id = ?",
        (feed_id,)
    )
    result = cursor.fetchone()
    
    if result:
        return {
            'etag': result[0],
            'last_modified': result[1]
        }
    else:
        return {'etag': None, 'last_modified': None}

def update_feed_cache_headers(cursor: sqlite3.Cursor, feed_id: int, 
                            etag: Optional[str], last_modified: Optional[str]):
    """
    Update cache headers for a feed
    
    Args:
        cursor: Database cursor
        feed_id: Feed ID
        etag: ETag header value
        last_modified: Last-Modified header value
    """
    # Ensure feed_metadata record exists
    ensure_feed_metadata_exists(cursor, feed_id, 'rss')
    
    cursor.execute(
        "UPDATE feed_metadata SET etag = ?, last_modified_http = ? WHERE feed_id = ?",
        (etag, last_modified, feed_id)
    )

def extract_http_cache_headers(response: requests.Response) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract cache headers from HTTP response
    
    Args:
        response: HTTP response object
        
    Returns:
        Tuple of (etag, last_modified) values
    """
    etag = response.headers.get('ETag')
    last_modified = response.headers.get('Last-Modified')
    return etag, last_modified

def handle_conditional_get(session: requests.Session, url: str, 
                          etag: Optional[str], last_modified: Optional[str],
                          timeout: int = 30) -> Tuple[requests.Response, bool]:
    """
    Perform HTTP conditional GET with ETag/Last-Modified headers
    
    Args:
        session: Requests session
        url: Feed URL
        etag: Previously stored ETag
        last_modified: Previously stored Last-Modified
        timeout: Request timeout seconds
        
    Returns:
        (response, is_cached) tuple where is_cached=True for 304 responses
    """
    headers = {}
    
    if etag:
        headers['If-None-Match'] = etag
    if last_modified:
        headers['If-Modified-Since'] = last_modified
    
    try:
        response = session.get(url, headers=headers, timeout=timeout)
        
        # 304 Not Modified - feed unchanged
        if response.status_code == 304:
            return response, True
        
        # Successful response with content
        response.raise_for_status()
        return response, False
        
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP error for {url}: {e}")
        raise

def extract_http_cache_headers(response: requests.Response) -> Dict[str, Optional[str]]:
    """
    Extract caching headers from HTTP response
    
    Args:
        response: HTTP response
        
    Returns:
        Dictionary with 'etag' and 'last_modified' keys
    """
    return {
        'etag': response.headers.get('ETag'),
        'last_modified': response.headers.get('Last-Modified')
    }

def update_feed_cache_headers(cursor: sqlite3.Cursor, feed_id: int, 
                             etag: Optional[str], last_modified: Optional[str]):
    """
    Update feed metadata with HTTP caching headers
    
    Args:
        cursor: Database cursor
        feed_id: Feed ID
        etag: ETag header value
        last_modified: Last-Modified header value
    """
    cursor.execute('''
        UPDATE feed_metadata 
        SET etag = ?, last_modified_http = ?
        WHERE feed_id = ?
    ''', (etag, last_modified, feed_id))

def get_feed_cache_headers(cursor: sqlite3.Cursor, feed_id: int) -> Dict[str, Optional[str]]:
    """
    Get stored HTTP caching headers for feed
    
    Args:
        cursor: Database cursor
        feed_id: Feed ID
        
    Returns:
        Dictionary with 'etag' and 'last_modified' keys
    """
    cursor.execute(
        "SELECT etag, last_modified_http FROM feed_metadata WHERE feed_id = ?",
        (feed_id,)
    )
    result = cursor.fetchone()
    
    if result:
        return {
            'etag': result[0],
            'last_modified': result[1]
        }
    
    return {'etag': None, 'last_modified': None}

def ensure_feed_metadata_exists(cursor: sqlite3.Cursor, feed_id: int, feed_type: str):
    """
    Ensure feed_metadata record exists for feed
    
    Args:
        cursor: Database cursor
        feed_id: Feed ID
        feed_type: Feed type ('rss' or 'youtube')
    """
    cursor.execute("SELECT 1 FROM feed_metadata WHERE feed_id = ?", (feed_id,))
    
    if not cursor.fetchone():
        # Create default metadata record
        cursor.execute('''
            INSERT INTO feed_metadata (
                feed_id, has_dates, typical_order, notes
            ) VALUES (?, ?, ?, ?)
        ''', (
            feed_id,
            True,  # Assume has dates until proven otherwise
            'reverse_chronological',  # Most common for RSS
            f'Auto-created for {feed_type} feed'
        ))

def cleanup_old_item_seen_records(cursor: sqlite3.Cursor, retention_days: int):
    """
    Clean up old item_seen records beyond retention period
    
    Args:
        cursor: Database cursor
        retention_days: How many days to retain records
    """
    cutoff = now_utc() - timedelta(days=retention_days)
    cutoff_str = cutoff.isoformat() + 'Z'
    
    cursor.execute(
        "DELETE FROM item_seen WHERE last_seen_utc < ?",
        (cutoff_str,)
    )
    
    deleted_count = cursor.rowcount
    if deleted_count > 0:
        logger.info(f"🧹 Cleaned up {deleted_count} old item_seen records")

def validate_feed_url(url: str) -> bool:
    """
    Basic validation for feed URLs
    
    Args:
        url: Feed URL to validate
        
    Returns:
        True if URL appears valid
    """
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme in ['http', 'https'] and parsed.netloc)
    except Exception:
        return False

def format_feed_stats(stats: Dict[str, Any]) -> str:
    """
    Format feed processing statistics for structured logging
    
    Args:
        stats: Statistics dictionary
        
    Returns:
        Formatted statistics string
    """
    return (
        f"new={stats.get('new', 0)} "
        f"updated={stats.get('updated', 0)} "
        f"skipped={stats.get('skipped', 0)} "
        f"errors={stats.get('errors', 0)} "
        f"duration_ms={stats.get('duration_ms', 0)}"
    )