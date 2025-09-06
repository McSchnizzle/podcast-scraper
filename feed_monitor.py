#!/usr/bin/env python3
"""
Podcast & YouTube Feed Monitor (Phase 4 Enhanced)
Monitors RSS feeds and YouTube channels with enhanced robustness:
- Per-feed lookback controls with grace periods
- HTTP caching (ETag/Last-Modified)
- Deterministic handling of date-less items
- Structured 2-line INFO logging per feed
- Telemetry integration
"""

import os
import feedparser
import sqlite3
import json
import requests
import logging
import time
import hashlib
from datetime import datetime, timedelta, UTC
from utils.db import get_connection
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse
from youtube_transcript_api import YouTubeTranscriptApi
import re

# Import utilities
from utils.datetime_utils import now_utc, cutoff_utc, parse_entry_to_utc, to_utc
from utils.feed_helpers import (
    item_identity_hash, content_hash, get_or_set_first_seen,
    detect_typical_order, get_effective_lookback_hours, compute_cutoff_with_grace,
    should_suppress_warning, update_warning_timestamp,
    handle_conditional_get, extract_http_cache_headers,
    update_feed_cache_headers, get_feed_cache_headers,
    ensure_feed_metadata_exists, cleanup_old_item_seen_records,
    format_feed_stats
)

# Import configuration
from config import config

# Set up logging
from utils.logging_setup import configure_logging
configure_logging()
logger = logging.getLogger(__name__)

class FeedMonitor:
    def __init__(self, db_path="podcast_monitor.db"):
        self.db_path = db_path
        self.feed_settings = config.FEED_SETTINGS
        # Create HTTP session with connection pooling
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.feed_settings['user_agent']})
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for tracking feeds and episodes (Phase 4 Enhanced)"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Feeds table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                type TEXT NOT NULL, -- 'rss' or 'youtube'
                topic_category TEXT NOT NULL,
                last_checked TIMESTAMP,
                active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Episodes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER,
                episode_id TEXT UNIQUE, -- RSS guid or YouTube video ID
                title TEXT NOT NULL,
                published_date TIMESTAMP,
                audio_url TEXT,
                transcript_path TEXT,
                processed BOOLEAN DEFAULT 0,
                priority_score REAL DEFAULT 0.0,
                content_type TEXT, -- 'announcement', 'interview', 'discussion'
                FOREIGN KEY (feed_id) REFERENCES feeds (id)
            )
        ''')
        
        # Phase 4: Feed metadata table for enhanced features
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feed_metadata (
                feed_id INTEGER PRIMARY KEY,
                has_dates BOOLEAN DEFAULT 1,
                typical_order TEXT CHECK(typical_order IN ('reverse_chronological','chronological','unknown')) DEFAULT 'reverse_chronological',
                last_no_date_warning TIMESTAMP NULL,
                lookback_hours_override INTEGER NULL,
                etag TEXT NULL,
                last_modified_http TEXT NULL,
                notes TEXT NULL,
                created_at TIMESTAMP DEFAULT (datetime('now', 'UTC')),
                updated_at TIMESTAMP DEFAULT (datetime('now', 'UTC')),
                FOREIGN KEY (feed_id) REFERENCES feeds (id) ON DELETE CASCADE
            )
        ''')
        
        # Phase 4: Item tracking for deduplication and date-less handling
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS item_seen (
                feed_id INTEGER NOT NULL,
                item_id_hash TEXT NOT NULL,
                first_seen_utc TIMESTAMP NOT NULL,
                last_seen_utc TIMESTAMP NOT NULL,
                content_hash TEXT NULL,
                guid TEXT NULL,
                link TEXT NULL,
                title TEXT NULL,
                enclosure_url TEXT NULL,
                created_at TIMESTAMP DEFAULT (datetime('now', 'UTC')),
                PRIMARY KEY (feed_id, item_id_hash),
                FOREIGN KEY (feed_id) REFERENCES feeds (id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for performance
        self._create_indexes(cursor)
        
        # Create triggers
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS feed_metadata_updated_at 
            AFTER UPDATE ON feed_metadata
            BEGIN
                UPDATE feed_metadata SET updated_at = datetime('now', 'UTC') WHERE feed_id = NEW.feed_id;
            END
        ''')
        
        conn.commit()
        conn.close()
        
    def _create_indexes(self, cursor):
        """Create performance indexes for Phase 4 tables"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_item_seen_feed_last_seen ON item_seen(feed_id, last_seen_utc)",
            "CREATE INDEX IF NOT EXISTS ix_item_seen_first_seen ON item_seen(first_seen_utc)",
            "CREATE INDEX IF NOT EXISTS ix_item_seen_content_hash ON item_seen(feed_id, content_hash)",
            "CREATE INDEX IF NOT EXISTS ix_feed_metadata_lookback ON feed_metadata(lookback_hours_override)",
            "CREATE INDEX IF NOT EXISTS ix_feed_metadata_etag ON feed_metadata(etag)",
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except sqlite3.OperationalError:
                # Index might already exist
                pass
    
    def add_rss_feed(self, url, topic_category, title=None):
        """Add RSS feed to monitoring list"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Parse feed to get title if not provided, using proper headers
            if not title:
                headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
                try:
                    response = requests.get(url, headers=headers, timeout=15)
                    if response.status_code == 200:
                        feed = feedparser.parse(response.content)
                        title = feed.feed.get('title', 'Unknown Feed')
                        
                        # Validate feed has episodes
                        if not feed.entries:
                            print(f"Warning: Feed {url} has no episodes")
                        else:
                            print(f"Found {len(feed.entries)} episodes in feed")
                    else:
                        print(f"HTTP {response.status_code} for {url}")
                        title = 'Unknown Feed'
                except Exception as parse_error:
                    print(f"Error parsing feed {url}: {parse_error}")
                    title = 'Unknown Feed'
            
            cursor.execute('''
                INSERT OR REPLACE INTO feeds (url, title, type, topic_category, last_checked)
                VALUES (?, ?, 'rss', ?, datetime('now'))
            ''', (url, title, topic_category))
            
            conn.commit()
            print(f"Added RSS feed: {title} ({topic_category})")
            
        except Exception as e:
            print(f"Error adding RSS feed {url}: {e}")
        finally:
            conn.close()
    
    def add_youtube_channel(self, channel_url, topic_category, title=None, channel_id=None):
        """Add YouTube channel to monitoring list"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Use provided channel_id or try to extract from URL
            if channel_id:
                extracted_id = channel_id
            else:
                extracted_id = self._extract_youtube_channel_id(channel_url)
            
            if not extracted_id:
                print(f"Could not extract channel ID from {channel_url}")
                print("Please provide the channel_id parameter manually")
                return
            
            # Convert to RSS feed URL
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={extracted_id}"
            
            if not title:
                # Try to get channel title from RSS feed
                feed = feedparser.parse(rss_url)
                title = feed.feed.get('title', 'Unknown YouTube Channel')
            
            cursor.execute('''
                INSERT OR REPLACE INTO feeds (url, title, type, topic_category, last_checked)
                VALUES (?, ?, 'youtube', ?, datetime('now'))
            ''', (rss_url, title, topic_category))
            
            conn.commit()
            print(f"Added YouTube channel: {title} ({topic_category})")
            
        except Exception as e:
            print(f"Error adding YouTube channel {channel_url}: {e}")
        finally:
            conn.close()
    
    def _extract_youtube_channel_id(self, url):
        """Extract channel ID from various YouTube URL formats"""
        patterns = [
            r'youtube\.com\/channel\/([a-zA-Z0-9_-]+)',
            r'youtube\.com\/@([a-zA-Z0-9_-]+)',
            r'youtube\.com\/c\/([a-zA-Z0-9_-]+)',
            r'youtube\.com\/user\/([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                channel_identifier = match.group(1)
                
                # If it's a @username, we need to resolve it to channel ID
                if '@' in url:
                    return self._resolve_channel_handle_to_id(channel_identifier)
                else:
                    return channel_identifier
        
        return None
    
    def _resolve_channel_handle_to_id(self, handle):
        """Resolve @username to channel ID via RSS feed attempt"""
        try:
            # Try the RSS URL with the handle
            test_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={handle}"
            response = requests.head(test_url, timeout=10)
            if response.status_code == 200:
                return handle
        except:
            pass
        
        # If that doesn't work, we'll need the user to provide the channel ID
        print(f"Could not resolve channel handle @{handle} to channel ID")
        print("Please provide the channel ID manually or use the full channel URL")
        return None
    
    def check_new_episodes(self, hours_back=None, feed_types=None):
        """Check feeds for new episodes with Phase 4 enhanced robustness
        
        Features:
        - Per-feed lookback controls with grace periods
        - HTTP caching (ETag/Last-Modified)
        - Deterministic handling of date-less items
        - 2-line INFO logging per feed
        - Telemetry integration
        
        Args:
            hours_back: Global lookback override (feed-specific overrides take precedence)
            feed_types: List of feed types to check ('rss', 'youtube'). 
                       If None, checks all types. In GitHub Actions, should be ['rss']
        """
        start_time = time.time()
        
        # Check if running in GitHub Actions
        is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
        
        # In GitHub Actions, only check RSS feeds (YouTube processed locally)
        if is_github_actions and feed_types is None:
            feed_types = ['rss']
            logger.info("🔧 GitHub Actions mode: Only checking RSS feeds")
        
        # Global settings
        grace_minutes = self.feed_settings['grace_minutes']
        enable_http_caching = self.feed_settings['enable_http_caching']
        global_lookback = hours_back or self.feed_settings['lookback_hours']
        
        logger.info(f"🕐 Feed monitoring started: global_lookback={global_lookback}h grace={grace_minutes}m caching={enable_http_caching}")
        
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Cleanup old item_seen records
            cleanup_old_item_seen_records(cursor, self.feed_settings['item_seen_retention_days'])
            
            # Get feeds to process
            feeds = self._get_feeds_to_process(cursor, feed_types)
            
            new_episodes = []
            feed_stats = {
                'total_feeds': len(feeds),
                'processed_feeds': 0,
                'new_episodes': 0,
                'http_cache_hits': 0,
                'errors': 0
            }
            
            for feed_id, url, title, feed_type, topic_category in feeds:
                feed_start_time = time.time()
                
                try:
                    # Ensure feed metadata exists
                    ensure_feed_metadata_exists(cursor, feed_id, feed_type)
                    
                    # Get effective lookback for this feed
                    effective_lookback = get_effective_lookback_hours(cursor, feed_id, global_lookback)
                    cutoff_time = compute_cutoff_with_grace(effective_lookback, grace_minutes)
                    
                    # Process feed with enhanced features
                    feed_result = self._process_single_feed(
                        cursor, feed_id, url, title, feed_type, topic_category,
                        cutoff_time, effective_lookback, enable_http_caching
                    )
                    
                    # Collect results
                    new_episodes.extend(feed_result['episodes'])
                    feed_stats['processed_feeds'] += 1
                    feed_stats['new_episodes'] += feed_result['stats']['new']
                    if feed_result['cached']:
                        feed_stats['http_cache_hits'] += 1
                    
                except Exception as e:
                    feed_stats['errors'] += 1
                    logger.error(f"❌ Error processing {title}: {e}")
                    # Emit structured error log
                    self._log_feed_error(title, feed_type, str(e))
                
                # Add politeness delay between feeds
                if self.feed_settings['politeness_delay_ms'] > 0:
                    time.sleep(self.feed_settings['politeness_delay_ms'] / 1000.0)
            
            conn.commit()
            
            # Summary logging and telemetry
            total_duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"🎉 Feed monitoring completed: "
                f"feeds={feed_stats['processed_feeds']}/{feed_stats['total_feeds']} "
                f"new={feed_stats['new_episodes']} "
                f"cached={feed_stats['http_cache_hits']} "
                f"errors={feed_stats['errors']} "
                f"duration_ms={total_duration_ms}"
            )
            
            # Emit telemetry
            self._emit_run_telemetry(feed_stats, total_duration_ms)
            
            return new_episodes
            
        finally:
            conn.close()
    
    def _get_feeds_to_process(self, cursor: sqlite3.Cursor, feed_types: Optional[List[str]]) -> List[Tuple]:
        """Get list of active feeds to process"""
        if feed_types:
            placeholders = ', '.join('?' for _ in feed_types)
            query = f'SELECT id, url, title, type, topic_category FROM feeds WHERE active = 1 AND type IN ({placeholders}) ORDER BY id'
            cursor.execute(query, feed_types)
        else:
            cursor.execute('SELECT id, url, title, type, topic_category FROM feeds WHERE active = 1 ORDER BY id')
        
        return cursor.fetchall()
    
    def _process_single_feed(self, cursor: sqlite3.Cursor, feed_id: int, url: str, 
                           title: str, feed_type: str, topic_category: str,
                           cutoff_time: datetime, lookback_hours: int, 
                           enable_caching: bool) -> Dict[str, Any]:
        """Process a single feed with Phase 4 enhancements"""
        start_time = time.time()
        stats = {'new': 0, 'updated': 0, 'duplicate': 0, 'skipped': 0, 'errors': 0, 'nodate': 0}
        cached = False
        
        try:
            # HTTP caching logic
            if enable_caching:
                cache_headers = get_feed_cache_headers(cursor, feed_id)
                response, cached = handle_conditional_get(
                    self.session, url, 
                    cache_headers['etag'], 
                    cache_headers['last_modified'],
                    self.feed_settings['request_timeout']
                )
                
                if cached:
                    # 304 Not Modified - no new content
                    duration_ms = int((time.time() - start_time) * 1000)
                    logger.info(f"📦 {title} items=0 dated=0 nodate=0 cutoff={cutoff_time.strftime('%Y-%m-%dT%H:%M:%S')}Z lookback={lookback_hours}h etag_hit=true")
                    logger.info(f"   {format_feed_stats(dict(stats, duration_ms=duration_ms))}")
                    
                    # Update last checked time
                    cursor.execute('UPDATE feeds SET last_checked = datetime("now", "UTC") WHERE id = ?', (feed_id,))
                    
                    return {'episodes': [], 'stats': stats, 'cached': True}
                
                # Update cache headers for successful responses
                new_headers = extract_http_cache_headers(response)
                update_feed_cache_headers(cursor, feed_id, new_headers['etag'], new_headers['last_modified'])
                
                # Check response size
                if len(response.content) > self.feed_settings['max_feed_bytes']:
                    raise ValueError(f"Feed too large: {len(response.content)} bytes > {self.feed_settings['max_feed_bytes']}")
                
                feed_data = feedparser.parse(response.content)
                
            else:
                # Non-cached request
                from utils.network import get_with_backoff
                response = get_with_backoff(
                    url,
                    tries=self.feed_settings['max_retries'],
                    base_delay=self.feed_settings['backoff_base_delay'],
                    timeout=self.feed_settings['request_timeout']
                )
                
                if len(response.content) > self.feed_settings['max_feed_bytes']:
                    raise ValueError(f"Feed too large: {len(response.content)} bytes")
                
                feed_data = feedparser.parse(response.content)
            
            # Process feed entries
            episodes = self._process_feed_entries(
                cursor, feed_id, feed_data, cutoff_time, title, feed_type, topic_category, stats
            )
            
            # Update feed metadata if auto-detection enabled
            if self.feed_settings['detect_feed_order'] and len(feed_data.entries) >= 3:
                typical_order = detect_typical_order(feed_data.entries)
                cursor.execute(
                    "UPDATE feed_metadata SET typical_order = ? WHERE feed_id = ?",
                    (typical_order, feed_id)
                )
            
            # Update last checked time
            cursor.execute('UPDATE feeds SET last_checked = datetime("now", "UTC") WHERE id = ?', (feed_id,))
            
            # Log results (Phase 4: 2-line format)
            duration_ms = int((time.time() - start_time) * 1000)
            total_items = len(feed_data.entries)
            dated_items = total_items - stats['nodate']
            
            logger.info(
                f"📦 {title} items={total_items} dated={dated_items} nodate={stats['nodate']} "
                f"cutoff={cutoff_time.strftime('%Y-%m-%dT%H:%M:%S')}Z lookback={lookback_hours}h etag_hit={cached}"
            )
            logger.info(f"   {format_feed_stats(dict(stats, duration_ms=duration_ms))}")
            
            # Check for feed-level warnings (suppressed to avoid spam)
            self._check_feed_warnings(cursor, feed_id, title, feed_data.entries, stats)
            
            return {'episodes': episodes, 'stats': stats, 'cached': cached}
            
        except requests.exceptions.RequestException as e:
            stats['errors'] += 1
            raise Exception(f"HTTP error: {e}")
        except Exception as e:
            stats['errors'] += 1
            raise
    
    def _process_feed_entries(self, cursor: sqlite3.Cursor, feed_id: int, 
                            feed_data, cutoff_time: datetime, title: str, 
                            feed_type: str, topic_category: str, 
                            stats: Dict[str, int]) -> List[Dict[str, Any]]:
        """Process individual feed entries with Phase 4 enhancements"""
        episodes = []
        current_time = now_utc()
        
        # Apply item limits
        max_items = self.feed_settings['max_episodes_per_feed']
        entries_to_process = feed_data.entries[:max_items] if max_items > 0 else feed_data.entries
        
        for entry in entries_to_process:
            try:
                # Extract basic info
                entry_title = entry.get('title', '(untitled)')
                entry_guid = entry.get('id') or entry.get('guid')
                entry_link = entry.get('link')
                
                # Get enclosure URL
                enclosure_url = None
                if hasattr(entry, 'enclosures') and entry.enclosures:
                    for enclosure in entry.enclosures:
                        if 'audio' in enclosure.get('type', ''):
                            enclosure_url = enclosure.get('href')
                            break
                
                # For YouTube, use video URL as enclosure
                if feed_type == 'youtube':
                    video_id = self._extract_video_id_from_entry(entry)
                    if video_id:
                        enclosure_url = f"https://www.youtube.com/watch?v={video_id}"
                
                # Generate stable item hash
                item_hash = item_identity_hash(entry_guid, entry_link, entry_title, enclosure_url)
                
                # Parse publication date
                pub_date, _ = parse_entry_to_utc(entry)
                
                if not pub_date:
                    # Handle date-less items with deterministic timestamps
                    pub_date = get_or_set_first_seen(
                        cursor, feed_id, item_hash, entry_title, 
                        entry_guid or '', entry_link or '', enclosure_url or '', current_time
                    )
                    stats['nodate'] += 1
                    logger.debug(f"SYNTHETIC DATE: {title} :: {entry_title} -> {pub_date.isoformat()}Z")
                else:
                    # Update last_seen for existing items
                    cursor.execute(
                        "UPDATE item_seen SET last_seen_utc = ? WHERE feed_id = ? AND item_id_hash = ?",
                        (current_time.isoformat() + 'Z', feed_id, item_hash)
                    )
                
                # Check cutoff time
                if pub_date < cutoff_time:
                    stats['skipped'] += 1
                    logger.debug(f"SKIP OLD: {title} :: {entry_title} ({pub_date.isoformat()})")
                    continue
                
                # Check for duplicates using enhanced detection
                if self._is_enhanced_duplicate(cursor, feed_id, item_hash, entry_title, pub_date):
                    stats['duplicate'] += 1
                    logger.debug(f"SKIP DUP: {title} :: {entry_title}")
                    continue
                
                # Create episode ID for episodes table (legacy compatibility)
                episode_id = hashlib.md5((entry_guid or entry_link or entry_title).encode()).hexdigest()[:8]
                
                # Insert new episode
                cursor.execute('''
                    INSERT INTO episodes (feed_id, episode_id, title, published_date, audio_url, status)
                    VALUES (?, ?, ?, ?, ?, 'pre-download')
                ''', (feed_id, episode_id, entry_title, pub_date.isoformat() + 'Z', enclosure_url))
                
                stats['new'] += 1
                logger.debug(f"NEW: {title} :: {entry_title} ({pub_date.isoformat()}Z)")
                
                episodes.append({
                    'feed_title': title,
                    'topic_category': topic_category,
                    'episode_title': entry_title,
                    'published_date': pub_date,
                    'audio_url': enclosure_url,
                    'type': feed_type
                })
                
            except Exception as e:
                stats['errors'] += 1
                logger.debug(f"ERROR processing entry in {title}: {e}")
        
        return episodes
    
    def _is_enhanced_duplicate(self, cursor: sqlite3.Cursor, feed_id: int, 
                             item_hash: str, title: str, pub_date: datetime) -> bool:
        """Enhanced duplicate detection using item_seen table"""
        # Check item_seen table first (most reliable)
        cursor.execute(
            "SELECT 1 FROM item_seen WHERE feed_id = ? AND item_id_hash = ?",
            (feed_id, item_hash)
        )
        if cursor.fetchone():
            return True
        
        # Fallback: check episodes table for legacy compatibility
        cursor.execute(
            "SELECT 1 FROM episodes WHERE feed_id = ? AND title = ? AND date(published_date) = ?",
            (feed_id, title, pub_date.strftime('%Y-%m-%d'))
        )
        return bool(cursor.fetchone())
    
    def _check_feed_warnings(self, cursor: sqlite3.Cursor, feed_id: int, 
                           title: str, entries: List, stats: Dict[str, int]):
        """Check and emit feed-level warnings with suppression"""
        # Stale feed warning
        if entries and stats['nodate'] == 0:
            # Only check for staleness if we have dated entries
            newest_dates = []
            for entry in entries[:10]:  # Check first 10 entries
                pub_date, _ = parse_entry_to_utc(entry)
                if pub_date:
                    newest_dates.append(pub_date)
            
            if newest_dates:
                newest = max(newest_dates)
                stale_threshold = now_utc() - timedelta(days=self.feed_settings['stale_feed_days'])
                
                if newest < stale_threshold:
                    days_old = (now_utc() - newest).days
                    if not should_suppress_warning(cursor, feed_id, 'stale_feed', 24):
                        logger.warning(
                            f"⚠️ STALE FEED: {title} - newest episode is {days_old} days old "
                            f"(threshold: {self.feed_settings['stale_feed_days']} days)"
                        )
                        # Note: We don't update stale warning timestamp as it's different from no_date
        
        # No-date warning with suppression
        if len(entries) > 0 and stats['nodate'] == len(entries):
            if not should_suppress_warning(cursor, feed_id, 'no_dates', 24):
                logger.warning(f"⚠️ NO DATES: {title} - all {len(entries)} entries lack dates")
                update_warning_timestamp(cursor, feed_id, 'no_dates')
    
    def _emit_run_telemetry(self, stats: Dict[str, Any], duration_ms: int):
        """Emit telemetry metrics for the feed monitoring run"""
        try:
            from utils.telemetry_manager import get_telemetry_manager
            telemetry = get_telemetry_manager()
            
            run_id = f"feed_monitor_{int(time.time())}"
            
            # Emit counters
            telemetry.record_metric("ingest.feeds.total.count", stats['total_feeds'], run_id=run_id)
            telemetry.record_metric("ingest.feeds.processed.count", stats['processed_feeds'], run_id=run_id)
            telemetry.record_metric("ingest.feeds.errors.count", stats['errors'], run_id=run_id)
            telemetry.record_metric("ingest.episodes.new.count", stats['new_episodes'], run_id=run_id)
            telemetry.record_metric("ingest.http.cache_hits.count", stats['http_cache_hits'], run_id=run_id)
            
            # Emit duration
            telemetry.record_metric("ingest.run.duration.ms", duration_ms, run_id=run_id)
            
        except Exception as e:
            logger.debug(f"Telemetry emission failed: {e}")
    
    def _log_feed_error(self, title: str, feed_type: str, error: str):
        """Log structured error information"""
        logger.error(
            f"FEED_ERROR feed=\"{title}\" type={feed_type} error=\"{error}\""
        )
    
    def _is_duplicate_episode(self, cursor, episode_id: str, audio_url: str, title: str, pub_date: datetime) -> bool:
        """
        Robust duplicate detection with composite checks
        
        Args:
            cursor: Database cursor
            episode_id: Generated episode ID (hash)
            audio_url: Episode audio/video URL
            title: Episode title
            pub_date: Published date
            
        Returns:
            True if this episode is a duplicate
        """
        # Check 1: Episode ID (GUID/ID hash)
        if episode_id:
            cursor.execute("SELECT 1 FROM episodes WHERE episode_id = ?", (episode_id,))
            if cursor.fetchone():
                return True
        
        # Check 2: Audio URL (exact match)
        if audio_url:
            cursor.execute("SELECT 1 FROM episodes WHERE audio_url = ?", (audio_url,))
            if cursor.fetchone():
                return True
        
        # Check 3: Title + date combo (fallback for unstable GUIDs)
        if title and pub_date:
            # Check for exact title and date match
            cursor.execute(
                "SELECT 1 FROM episodes WHERE title = ? AND published_date = ?", 
                (title, pub_date.isoformat())
            )
            if cursor.fetchone():
                return True
            
            # Check for title match within same day (timezone variations)
            pub_date_str = pub_date.strftime('%Y-%m-%d')
            cursor.execute(
                "SELECT 1 FROM episodes WHERE title = ? AND date(published_date) = ?", 
                (title, pub_date_str)
            )
            if cursor.fetchone():
                return True
        
        return False
    
    def _parse_date_to_utc(self, entry) -> datetime:
        """
        Parse entry date and normalize to UTC
        
        Args:
            entry: Feed entry object
            
        Returns:
            datetime object in UTC (timezone-aware) or None if parsing fails
        """
        try:
            # Use the centralized parser from datetime_utils
            pub_date, source_key = parse_entry_to_utc(entry)
            
            if pub_date is None:
                return None
                
            # Ensure timezone-aware UTC datetime for consistent comparisons
            return to_utc(pub_date)
            
        except Exception as e:
            print(f"Could not parse date from entry: {e}")
            return None
    
    def _extract_video_id_from_entry(self, entry):
        """Extract YouTube video ID from RSS entry"""
        video_url = entry.get('link', '')
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:watch\?v=)([0-9A-Za-z_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)
        return None
    
    def list_feeds(self):
        """List all monitored feeds grouped by topic"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT topic_category, title, type, url, active 
            FROM feeds 
            ORDER BY topic_category, title
        ''')
        
        feeds_by_topic = {}
        for topic, title, feed_type, url, active in cursor.fetchall():
            if topic not in feeds_by_topic:
                feeds_by_topic[topic] = []
            feeds_by_topic[topic].append({
                'title': title,
                'type': feed_type,
                'url': url,
                'active': bool(active)
            })
        
        conn.close()
        return feeds_by_topic
    
    def get_topic_categories(self):
        """Get list of current topic categories and feed counts"""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT topic_category, COUNT(*) as feed_count
            FROM feeds 
            WHERE active = 1
            GROUP BY topic_category
        ''')
        
        categories = dict(cursor.fetchall())
        conn.close()
        return categories

def main():
    """CLI interface for feed management"""
    monitor = FeedMonitor()
    
    print("Daily Podcast Digest - Feed Monitor")
    print("===================================")
    
    # Show current feeds
    feeds = monitor.list_feeds()
    if feeds:
        print("\nCurrent feeds by topic:")
        for topic, feed_list in feeds.items():
            print(f"\n{topic.upper()}:")
            for feed in feed_list:
                status = "✅" if feed['active'] else "❌"
                print(f"  {status} {feed['title']} ({feed['type']})")
    else:
        print("\nNo feeds configured yet.")
    
    # Show topic statistics
    categories = monitor.get_topic_categories()
    print(f"\nTopic categories: {categories}")
    
    # Check for new episodes
    print(f"\nChecking for new episodes in last 24 hours...")
    new_episodes = monitor.check_new_episodes()
    
    if new_episodes:
        print(f"Found {len(new_episodes)} new episodes:")
        for episode in new_episodes:
            print(f"  📺 {episode['episode_title']}")
            print(f"     Source: {episode['feed_title']} ({episode['topic_category']})")
            print(f"     Published: {episode['published_date']}")
            print()
    else:
        print("No new episodes found.")

if __name__ == "__main__":
    main()