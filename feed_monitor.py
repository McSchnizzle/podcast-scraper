#!/usr/bin/env python3
"""
Podcast & YouTube Feed Monitor
Monitors RSS feeds and YouTube channels for new content in the last 24 hours
"""

import os
import feedparser
import sqlite3
import json
import requests
import logging
from datetime import datetime, timedelta, UTC
from utils.datetime_utils import now_utc, cutoff_utc, parse_entry_to_utc, to_utc
from urllib.parse import urlparse
from youtube_transcript_api import YouTubeTranscriptApi
import re

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
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for tracking feeds and episodes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
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
        
        conn.commit()
        conn.close()
    
    def add_rss_feed(self, url, topic_category, title=None):
        """Add RSS feed to monitoring list"""
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
        """Check feeds for new episodes in the last N hours
        
        Args:
            hours_back: How many hours to look back for new episodes.
                       If None, uses FEED_LOOKBACK_HOURS env var (default 48)
            feed_types: List of feed types to check ('rss', 'youtube'). 
                       If None, checks all types. In GitHub Actions, should be ['rss']
        """
        # Use environment variable if hours_back not specified
        if hours_back is None:
            hours_back = int(os.getenv("FEED_LOOKBACK_HOURS", "48"))
        
        # Use UTC for cutoff time to match database storage
        cutoff_time = cutoff_utc(hours_back)
        print(f"🕐 Looking for episodes newer than {cutoff_time.isoformat()}Z UTC ({hours_back}h lookback)")
        new_episodes = []
        
        # Check if running in GitHub Actions
        is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
        
        # In GitHub Actions, only check RSS feeds (YouTube processed locally)
        if is_github_actions and feed_types is None:
            feed_types = ['rss']
            print("🔧 GitHub Actions mode: Only checking RSS feeds (YouTube processed locally)")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build query with feed type filter if specified
        if feed_types:
            placeholders = ', '.join('?' for _ in feed_types)
            query = f'SELECT id, url, title, type, topic_category FROM feeds WHERE active = 1 AND type IN ({placeholders})'
            cursor.execute(query, feed_types)
        else:
            cursor.execute('SELECT id, url, title, type, topic_category FROM feeds WHERE active = 1')
            
        feeds = cursor.fetchall()
        
        for feed_id, url, title, feed_type, topic_category in feeds:
            print(f"Checking {title}...")
            
            try:
                # Use network utilities with retries
                from utils.network import get_with_backoff
                
                response = get_with_backoff(
                    url,
                    tries=self.feed_settings['max_retries'],
                    base_delay=self.feed_settings['backoff_base_delay'],
                    timeout=self.feed_settings['request_timeout']
                )
                feed = feedparser.parse(response.content)
                
                # Apply feed item limits to reduce processing
                max_items = self.feed_settings['max_episodes_per_feed']
                entries_to_process = feed.entries[:max_items] if max_items > 0 else feed.entries
                
                # INFO: Header line per feed
                print(f"▶ {title} (entries={len(entries_to_process)}/{len(feed.entries)}, limit={max_items}, cutoff={cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}Z)")
                
                # Track processing stats
                pub_dates = []
                old_skipped = 0
                dup_count = 0 
                new_count = 0
                no_date_count = 0
                
                for i, entry in enumerate(entries_to_process, 1):
                    # Parse publication date and normalize to UTC
                    pub_date = self._parse_date_to_utc(entry)
                    
                    # Extract episode information for logging
                    episode_title = entry.get('title', '(untitled)')
                    
                    # Skip with debug logging
                    if not pub_date:
                        logger.debug(f"SKIP no-date: {title} :: {episode_title}")
                        no_date_count += 1
                        continue
                    
                    pub_dates.append(pub_date)  # Track for newest calculation
                    
                    if pub_date < cutoff_time:
                        old_skipped += 1
                        logger.debug(f"SKIP old-entry: {title} :: {episode_title} ({pub_date.isoformat()} < {cutoff_time.isoformat()})")
                        
                        # Break on old if enabled and feed appears to be reverse-chronological
                        if self.feed_settings['break_on_old'] and old_skipped == 1:
                            print(f"  🚀 Early break: {title} appears reverse-chronological, stopping scan")
                            break
                        continue
                    
                    # Create episode ID
                    raw_episode_id = entry.get('id') or entry.get('guid') or entry.get('link')
                    import hashlib
                    episode_id = hashlib.md5(raw_episode_id.encode()).hexdigest()[:8]
                    
                    # Get audio URL first for duplicate detection
                    audio_url = None
                    if hasattr(entry, 'enclosures') and entry.enclosures:
                        for enclosure in entry.enclosures:
                            if 'audio' in enclosure.get('type', ''):
                                audio_url = enclosure.get('href')
                                break
                    
                    # For YouTube, audio URL is the video URL
                    if feed_type == 'youtube':
                        video_id = self._extract_video_id_from_entry(entry)
                        if video_id:
                            audio_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    # Robust duplicate detection with composite checks
                    if self._is_duplicate_episode(cursor, episode_id, audio_url, episode_title, pub_date):
                        dup_count += 1
                        logger.debug(f"SKIP duplicate episode: {episode_id} :: {episode_title}")
                        continue
                    
                    # Add new episode with pre-download status
                    cursor.execute('''
                        INSERT INTO episodes (feed_id, episode_id, title, published_date, audio_url, status)
                        VALUES (?, ?, ?, ?, ?, 'pre-download')
                    ''', (feed_id, episode_id, episode_title, pub_date.isoformat(), audio_url))
                    
                    new_count += 1
                    logger.debug(f"Added new episode: {episode_title} ({pub_date.isoformat()})")
                    
                    new_episodes.append({
                        'feed_title': title,
                        'topic_category': topic_category,
                        'episode_title': episode_title,
                        'published_date': pub_date,
                        'audio_url': audio_url,
                        'type': feed_type
                    })
                
                # INFO: Totals line per feed
                print(f"   totals: new={new_count} dup={dup_count} older={old_skipped} no_date={no_date_count}")
                
                # Show feed freshness
                if pub_dates:
                    newest_seen = max(pub_dates)
                    print(f"  📅 Newest in {title}: {newest_seen.isoformat()}Z UTC")
                    
                    # Check for stale feeds
                    stale_threshold = now_utc() - timedelta(days=self.feed_settings['stale_feed_days'])
                    if newest_seen < stale_threshold:
                        print(f"  ⚠️  STALE FEED WARNING: {title} - newest episode is {(now_utc() - newest_seen).days} days old (threshold: {self.feed_settings['stale_feed_days']} days)")
                else:
                    # INFO: Single line for feeds with no dates (avoiding spam)
                    print(f"⚠️ {title}: no dated entries (skipped gracefully)")
                
                # Update last checked time
                cursor.execute('UPDATE feeds SET last_checked = datetime("now") WHERE id = ?', (feed_id,))
                
            except Exception as e:
                print(f"Error checking feed {title}: {e}")
        
        conn.commit()
        conn.close()
        
        return new_episodes
    
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
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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