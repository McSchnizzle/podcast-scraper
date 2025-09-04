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
from datetime import datetime, timedelta
from urllib.parse import urlparse
from youtube_transcript_api import YouTubeTranscriptApi
import re

class FeedMonitor:
    def __init__(self, db_path="podcast_monitor.db"):
        self.db_path = db_path
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
        
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        print(f"🕐 Looking for episodes newer than {cutoff_time.isoformat()} ({hours_back}h lookback)")
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
                # Use proper headers for better compatibility
                headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
                response = requests.get(url, headers=headers, timeout=30)
                feed = feedparser.parse(response.content)
                
                # Track newest entry for feed freshness
                pub_dates = []
                
                for entry in feed.entries:
                    # Parse publication date
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = datetime(*entry.updated_parsed[:6])
                    elif hasattr(entry, 'published'):
                        # Try to parse ISO format date string
                        try:
                            from dateutil import parser
                            pub_date = parser.parse(entry.published).replace(tzinfo=None)
                        except:
                            print(f"Could not parse date: {entry.published}")
                    
                    # Extract episode information for logging
                    episode_title = entry.get('title', '(untitled)')
                    
                    # Skip with explicit logging
                    if not pub_date:
                        print(f"  SKIP no-date: {title} :: {episode_title}")
                        continue
                    
                    pub_dates.append(pub_date)  # Track for newest calculation
                    
                    if pub_date < cutoff_time:
                        print(f"  SKIP old-entry: {title} :: {episode_title} ({pub_date.isoformat()} < {cutoff_time.isoformat()})")
                        continue
                    
                    # Create episode ID
                    raw_episode_id = entry.get('id') or entry.get('guid') or entry.get('link')
                    import hashlib
                    episode_id = hashlib.md5(raw_episode_id.encode()).hexdigest()[:8]
                    
                    # Check if already processed
                    cursor.execute('SELECT id FROM episodes WHERE episode_id = ?', (episode_id,))
                    if cursor.fetchone():
                        print(f"  SKIP duplicate episode_id: {episode_id} :: {episode_title}")
                        continue
                    
                    # Get audio URL
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
                    
                    # Add new episode with pre-download status
                    cursor.execute('''
                        INSERT INTO episodes (feed_id, episode_id, title, published_date, audio_url, status)
                        VALUES (?, ?, ?, ?, ?, 'pre-download')
                    ''', (feed_id, episode_id, episode_title, pub_date, audio_url))
                    
                    print(f"  ✅ Added new episode: {episode_title} ({pub_date.isoformat()})")
                    
                    new_episodes.append({
                        'feed_title': title,
                        'topic_category': topic_category,
                        'episode_title': episode_title,
                        'published_date': pub_date,
                        'audio_url': audio_url,
                        'type': feed_type
                    })
                
                # Show feed freshness
                if pub_dates:
                    newest_seen = max(pub_dates)
                    print(f"  📅 Newest in {title}: {newest_seen.isoformat()} (cutoff {cutoff_time.isoformat()})")
                else:
                    print(f"  ⚠️ No dated entries found in {title}")
                
                # Update last checked time
                cursor.execute('UPDATE feeds SET last_checked = datetime("now") WHERE id = ?', (feed_id,))
                
            except Exception as e:
                print(f"Error checking feed {title}: {e}")
        
        conn.commit()
        conn.close()
        
        return new_episodes
    
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