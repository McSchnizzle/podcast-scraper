#!/usr/bin/env python3
"""
Production Configuration for Podcast Scraper

- Environment-driven base URLs
- UTC timezone standardization
- Content-based stable GUIDs
- Quota management guardrails
- Security boundary enforcement
- OpenAI client settings (explicit)
"""

import os
import re
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from utils.datetime_utils import now_utc
from typing import Dict, Optional, Any, List


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name, default)
    return val


@dataclass
class ProductionConfig:
    # ---- Environment & URLs ----
    ENV: str = "production"
    PODCAST_BASE_URL: str = _env("PODCAST_BASE_URL", "https://podcast.paulrbrown.org")
    AUDIO_BASE_URL: str = _env("AUDIO_BASE_URL", "https://paulrbrown.org/audio")

    # ---- Directories / Filenames ----
    TRANSCRIPTS_DIR: str = _env("TRANSCRIPTS_DIR", "transcripts")
    OUTPUT_DIR: str = _env("OUTPUT_DIR", "daily_digests")
    RSS_FILENAME: str = _env("RSS_FILENAME", "daily-digest.xml")

    # ---- OpenAI settings expected by codebase ----
    OPENAI_API_KEY: Optional[str] = _env("OPENAI_API_KEY")  # required at runtime
    # For modules that do: config.OPENAI_SETTINGS
    OPENAI_SETTINGS: Dict[str, Any] = None  # filled in __post_init__
    # For modules that do: config.OPENAI_MODELS["role"]
    OPENAI_MODELS: Dict[str, str] = None  # filled in __post_init__

    # ---- Model choices (align with your verified config) ----
    SUMMARY_MODEL: str = _env("SUMMARY_MODEL", "gpt-5-mini")
    SCORER_MODEL: str = _env("SCORER_MODEL", "gpt-5-mini")
    PROSE_VALIDATOR_MODEL: str = _env("PROSE_VALIDATOR_MODEL", "gpt-5-mini")

    # ---- Quotas / limits (guardrails, can be tuned via env) ----
    DAILY_TOKEN_LIMIT: int = int(_env("DAILY_TOKEN_LIMIT", "200000"))   # example
    DAILY_REQUEST_LIMIT: int = int(_env("DAILY_REQUEST_LIMIT", "2000")) # example
    RETRY_MAX_ATTEMPTS: int = int(_env("RETRY_MAX_ATTEMPTS", "4"))
    RETRY_JITTER_SECS: float = float(_env("RETRY_JITTER_SECS", "0.25"))

    # ---- Duration thresholds ----
    MIN_DURATION_SECONDS: int = 180  # skip if < 3:00, per your tests
    MAX_TOPICS: int = 6
    SELECTOR_THRESHOLD: float = 0.65

    def __post_init__(self):
        # Feed monitoring settings
        self.FEED_SETTINGS = {
            'check_interval_hours': 24,
            'max_episodes_per_feed': int(_env('FEED_MAX_ITEMS_PER_FEED', '50')),
            'break_on_old': _env('FEED_BREAK_ON_OLD', '1') == '1',
            'stale_feed_days': int(_env('FEED_STALE_DAYS', '21')),
            'youtube_min_duration': 180,  # 3 minutes
            'user_agent': 'PodcastDigest/2.0 (+https://github.com/McSchnizzle/podcast-scraper)',
            'request_timeout': int(_env('REQUEST_TIMEOUT', '30')),
            'max_retries': int(_env('MAX_RETRIES', '4')),
            'backoff_base_delay': float(_env('BACKOFF_BASE_DELAY', '0.5'))
        }
        # Provide complete OPENAI_SETTINGS structure expected by the codebase
        self.OPENAI_SETTINGS = {
            # Model configuration - using actual OpenAI model names
            'digest_model': _env('DIGEST_MODEL', 'gpt-5'),
            'scoring_model': _env('SCORING_MODEL', 'gpt-5-mini'),  # Cost-effective for scoring
            'validator_model': _env('VALIDATOR_MODEL', 'gpt-5-mini'),  # Cost-effective for validation
            
            # Digest generation settings
            'digest_temperature': 0.7,
            'digest_presence_penalty': 0.1,
            'digest_frequency_penalty': 0.2,
            'digest_max_tokens': 4000,
            
            # Scoring settings
            'scoring_temperature': 0.1,
            'scoring_max_tokens': 500,
            'timeout_seconds': 60,
            'batch_size': 5,  # Number of episodes to score in one batch
            'rate_limit_delay': 1,  # Seconds between API calls
            'relevance_threshold': 0.65,  # CRITICAL: Minimum score to include in topic digest
            
            # Map-reduce settings for token optimization
            'max_episodes_per_topic': 6,  # Top-N cap per topic
            'max_episode_summary_tokens': 450,  # Per-episode summary token limit
            'max_reduce_tokens': 6000,  # Total tokens for final digest prompt
            'max_retries': 4,  # Exponential backoff retries
            'backoff_base_delay': 0.5,  # Starting delay for exponential backoff
            
            # Legacy keys for backward compatibility
            "model": self.SUMMARY_MODEL,
            "temperature": float(_env("SUMMARY_TEMPERATURE", "0.2")),
            "max_tokens": int(_env("SUMMARY_MAX_TOKENS", "1600")),
            "timeout": int(_env("OPENAI_TIMEOUT_SECS", "60")),
            
            'topics': {
                'AI News': {
                    'description': 'Artificial intelligence developments, AI research, machine learning breakthroughs, AI industry news, AI policy and ethics',
                    'prompt': 'artificial intelligence, AI news, machine learning, deep learning, AI research, AI breakthroughs, AI industry, AI policy, AI ethics, AI regulation, generative AI, LLMs, AI startups, AI funding'
                },
                'Tech Product Releases': {
                    'description': 'New technology product launches, hardware releases, software updates, gadget reviews, product announcements',
                    'prompt': 'product launch, product release, new products, hardware launch, software release, gadget announcement, tech products, product reviews, device launch, tech hardware, consumer electronics'
                },
                'Tech News and Tech Culture': {
                    'description': 'Technology industry news, tech company developments, tech culture discussions, digital trends, tech policy',
                    'prompt': 'tech news, technology industry, tech companies, tech culture, digital trends, tech policy, tech regulation, tech industry analysis, tech leadership, tech innovation, startup news'
                },
                'Community Organizing': {
                    'description': 'Grassroots organizing, community activism, local organizing efforts, civic engagement, community building strategies',
                    'prompt': 'community organizing, grassroots activism, local organizing, civic engagement, community building, activist organizing, community mobilization, grassroots campaigns, community advocacy, local activism'
                },
                'Social Justice': {
                    'description': 'Social justice movements, civil rights, equity and inclusion, systemic justice issues, advocacy and activism',
                    'prompt': 'social justice, civil rights, equity, inclusion, systemic justice, social equity, human rights, justice advocacy, social activism, civil rights movement, racial justice, economic justice'
                },
                'Societal Culture Change': {
                    'description': 'Cultural shifts, social movements, changing social norms, generational changes, cultural transformation',
                    'prompt': 'cultural change, social movements, cultural shifts, social transformation, generational change, cultural evolution, social change, cultural trends, societal transformation, cultural movements'
                }
            }
        }
        self.OPENAI_MODELS = {
            "summary": self.SUMMARY_MODEL,
            "scorer": self.SCORER_MODEL,
            "prose_validator": self.PROSE_VALIDATOR_MODEL,
        }
        
        # ---- Phase 2 GPT-5 Integration Configuration ----
        
        # GPT-5 Models for each component
        self.GPT5_MODELS = {
            'summary': _env('GPT5_SUMMARY_MODEL', 'gpt-5-mini'),
            'scorer': _env('GPT5_SCORER_MODEL', 'gpt-5-mini'),
            'digest': _env('GPT5_DIGEST_MODEL', 'gpt-5'),
            'validator': _env('GPT5_VALIDATOR_MODEL', 'gpt-5-mini')
        }
        
        # Token limits for each component
        self.OPENAI_TOKENS = {
            'summary': int(_env('OPENAI_SUMMARY_TOKENS', '1500')),
            'scorer': int(_env('OPENAI_SCORER_TOKENS', '500')),
            'digest': int(_env('OPENAI_DIGEST_TOKENS', '4000')),
            'validator': int(_env('OPENAI_VALIDATOR_TOKENS', '2000'))
        }
        
        # Reasoning effort levels
        self.REASONING_EFFORT = {
            'summary': _env('REASONING_SUMMARY', 'minimal'),
            'scorer': _env('REASONING_SCORER', 'minimal'),
            'digest': _env('REASONING_DIGEST', 'medium'),
            'validator': _env('REASONING_VALIDATOR', 'minimal')
        }
        
        # Feature flags for staged rollout
        self.FEATURE_FLAGS = {
            'use_gpt5_summaries': _env('USE_GPT5_SUMMARIES', '1') == '1',
            'use_gpt5_digest': _env('USE_GPT5_DIGEST', '1') == '1',
            'use_gpt5_validator': _env('USE_GPT5_VALIDATOR', '1') == '1',
            'enable_idempotency': _env('ENABLE_IDEMPOTENCY', '1') == '1',
            'enable_observability': _env('ENABLE_OBSERVABILITY', '1') == '1'
        }

    # ---------- Time / Labels ----------
    @staticmethod
    def get_utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def format_rss_date(dt: Optional[datetime] = None) -> str:
        """
        RFC-822 style date for RSS, e.g., Thu, 04 Sep 2025 06:01:26 +0000
        """
        if dt is None:
            dt = ProductionConfig.get_utc_now()
        return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")

    @staticmethod
    def get_weekday_label(dt: Optional[datetime] = None) -> str:
        """
        Friday -> Weekly Digest
        Monday -> Catch-up Digest
        Else -> Daily Digest
        """
        dt = dt or ProductionConfig.get_utc_now()
        wd = dt.weekday()  # Monday=0 .. Sunday=6
        if wd == 4:
            return "Weekly Digest"
        if wd == 0:
            return "Catch-up Digest"
        return "Daily Digest"

    # ---------- GUID / Stability ----------
    def stable_guid_for_digest(self, topic: str, date: datetime, episode_ids: Optional[List[str]]) -> str:
        """
        Stable, content-based GUID:
        base/digest/YYYY-mm-dd/topic-slug/hash12
        """
        safe_topic = re.sub(r"[^a-z0-9\-]+", "-", topic.lower().replace("&", "and"))
        sorted_ids = ",".join(sorted(episode_ids)) if episode_ids else "no-episodes"
        ident = f"{topic}|{date.strftime('%Y-%m-%d')}|{sorted_ids}"
        content_hash = hashlib.md5(ident.encode("utf-8")).hexdigest()[:12]
        return f"{self.PODCAST_BASE_URL}/digest/{date.strftime('%Y-%m-%d')}/{safe_topic}/{content_hash}"

    # ---------- Feed Management ----------
    def get_feed_config(self) -> list:
        """Get complete feed configuration with all monitored feeds
        
        Note: topic_category is informational only. Content selection is 100% score-based
        using AI relevance scoring against the 6 defined topics.
        """
        return [
            # Technology RSS Feeds
            {
                'title': 'The Vergecast',
                'url': 'https://feeds.megaphone.fm/vergecast',
                'type': 'rss',
                'topic_category': 'technology'
            },
            
            # AI-focused YouTube Channels
            {
                'title': 'Wes Roth',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCqcbQf6yw5KzRoDDcZ_wBSw',
                'type': 'youtube',
                'topic_category': 'technology'
            },
            {
                'title': 'Matt Wolfe',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UChpleBmo18P08aKCIgti38g',
                'type': 'youtube',
                'topic_category': 'technology'
            },
            {
                'title': 'How I AI',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCRYY7IEbkHLH_ScJCu9eWDQ',
                'type': 'youtube',
                'topic_category': 'technology'
            },
            {
                'title': 'The AI Advantage',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCHhYXsLBEVVnbvsq57n1MTQ',
                'type': 'youtube',
                'topic_category': 'technology'
            },
            {
                'title': 'AI Daily Brief',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCKelCK4ZaO6HeEI1KQjqzWA',
                'type': 'youtube',
                'topic_category': 'technology'
            },
            {
                'title': 'All About AI',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCR9j1jqqB5Rse69wjUnbYwA',
                'type': 'youtube',
                'topic_category': 'technology'
            },
            {
                'title': 'Indy Dev Dan',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UC_x36zCEGilGpB1m-V4gmjg',
                'type': 'youtube',
                'topic_category': 'technology'
            },
            {
                'title': 'Robin',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCy71Sv5TVBbn5BYETRQV22Q',
                'type': 'youtube',
                'topic_category': 'technology'
            },
            
            # Business & Entrepreneurship
            {
                'title': 'Leading the Shift: AI innovation talks with Microsoft Azure',
                'url': 'https://media.rss.com/leading-the-shift/feed.xml',
                'type': 'rss',
                'topic_category': 'business'
            },
            {
                'title': 'The Diary Of A CEO with Steven Bartlett',
                'url': 'https://feeds.megaphone.fm/thediaryofaceo',
                'type': 'rss',
                'topic_category': 'business'
            },
            
            # Philosophy & Society
            {
                'title': 'Slo Mo: A Podcast with Mo Gawdat',
                'url': 'https://feeds.buzzsprout.com/843595.rss',
                'type': 'rss',
                'topic_category': 'philosophy'
            },
            {
                'title': 'Team Human',
                'url': 'https://feeds.acast.com/public/shows/58ad887a1608b1752663b04a',
                'type': 'rss',
                'topic_category': 'philosophy'
            },
            {
                'title': 'The Great Simplification with Nate Hagens',
                'url': 'https://thegreatsimplification.libsyn.com/rss',
                'type': 'rss',
                'topic_category': 'philosophy'
            },
            
            # Political & Social Commentary - CORRECTED RSS FEEDS
            {
                'title': 'Movement Memos',
                'url': 'https://feeds.megaphone.fm/movementmemos',
                'type': 'rss',
                'topic_category': 'politics'
            },
            {
                'title': 'Real Sankara Hours',
                'url': 'https://feed.podbean.com/realsankarahours/feed.xml',
                'type': 'rss',
                'topic_category': 'politics'
            },
            {
                'title': 'Millennials Are Killing Capitalism',
                'url': 'https://millennialsarekillingcapitalism.libsyn.com/rss',
                'type': 'rss',
                'topic_category': 'politics'
            },
            {
                'title': 'THIS IS REVOLUTION',
                'url': 'https://feed.podbean.com/bitterlake/feed.xml',
                'type': 'rss',
                'topic_category': 'politics'
            },
            {
                'title': 'The Red Nation Podcast',
                'url': 'https://therednation.libsyn.com/rss',
                'type': 'rss',
                'topic_category': 'politics'
            },
            
            # Black Culture & History - CORRECTED RSS FEEDS
            {
                'title': 'The Black Myths Podcast',
                'url': 'https://blackmyths.libsyn.com/rss',
                'type': 'rss',
                'topic_category': 'culture'
            },
            {
                'title': 'The Malcolm Effect',
                'url': 'https://feed.podbean.com/kultural/feed.xml',
                'type': 'rss',
                'topic_category': 'culture'
            },
            {
                'title': 'Black Autonomy Podcast',
                'url': 'https://blackautonomy.libsyn.com/rss',
                'type': 'rss',
                'topic_category': 'culture'
            },
            {
                'title': 'The Dugout | a black anarchist podcast',
                'url': 'https://anchor.fm/dugoutpodcast/rss',
                'type': 'rss',
                'topic_category': 'culture'
            }
        ]
    
    def sync_feeds_to_database(self, db_path: str = "podcast_monitor.db", force_update: bool = False):
        """Sync feed configuration to database (database is source of truth)"""
        import sqlite3
        import logging
        
        logger = logging.getLogger(__name__)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current feeds from database
        cursor.execute("SELECT COUNT(*) FROM feeds")
        db_feed_count = cursor.fetchone()[0]
        
        # Only sync from config if database is empty or force_update is True
        if db_feed_count == 0 or force_update:
            logger.info(f"Syncing {len(self.get_feed_config())} feeds to database...")
            
            for feed in self.get_feed_config():
                cursor.execute('''
                    INSERT OR REPLACE INTO feeds (url, title, type, topic_category, active, last_checked)
                    VALUES (?, ?, ?, ?, 1, datetime('now'))
                ''', (feed['url'], feed['title'], feed['type'], feed['topic_category']))
            
            conn.commit()
            logger.info(f"✅ Synced {len(self.get_feed_config())} feeds to database")
        else:
            logger.info(f"Database has {db_feed_count} feeds - using database as source of truth")
        
        conn.close()
    
    def get_active_feeds_from_db(self, db_path: str = "podcast_monitor.db") -> list:
        """Get active feeds from database (single source of truth)"""
        import sqlite3
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, url, title, type, topic_category
                FROM feeds
                WHERE active = 1
                ORDER BY id
            ''')
            
            feeds = []
            for row in cursor.fetchall():
                feeds.append({
                    'id': row[0],
                    'url': row[1],
                    'title': row[2],
                    'type': row[3],
                    'topic_category': row[4]
                })
            
            conn.close()
            return feeds
        except Exception as e:
            logger.error(f"Error getting feeds from database: {e}")
            return []
    
    def add_feed_to_db(self, url: str, title: str, feed_type: str, topic_category: str, 
                       db_path: str = "podcast_monitor.db") -> bool:
        """Add new feed to database"""
        import sqlite3
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO feeds (url, title, type, topic_category, active, last_checked)
                VALUES (?, ?, ?, ?, 1, datetime('now'))
            ''', (url, title, feed_type, topic_category))
            
            conn.commit()
            conn.close()
            logger.info(f"✅ Added feed: {title} ({feed_type})")
            return True
        except Exception as e:
            logger.error(f"Error adding feed: {e}")
            return False
    
    def validate_feed_url(self, url: str) -> tuple[bool, str]:
        """Validate that a feed URL is accessible and returns a 200 status"""
        import requests
        
        try:
            headers = {
                'User-Agent': 'PodcastDigest/2.0 (+https://github.com/McSchnizzle/podcast-scraper)'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return True, "OK"
            else:
                return False, f"HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "Request timeout"
        except requests.exceptions.ConnectionError:
            return False, "Connection error"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def add_feed_with_validation(self, url: str, title: str, feed_type: str, topic_category: str, 
                                db_path: str = "podcast_monitor.db") -> tuple[bool, str]:
        """Add new feed to database with validation"""
        import logging
        
        logger = logging.getLogger(__name__)
        
        # First validate the feed URL
        is_valid, error_msg = self.validate_feed_url(url)
        if not is_valid:
            logger.error(f"❌ Feed validation failed for {title}: {error_msg}")
            return False, error_msg
        
        # If validation passes, add to database
        success = self.add_feed_to_db(url, title, feed_type, topic_category, db_path)
        if success:
            logger.info(f"✅ Feed validated and added: {title}")
            return True, "Successfully added"
        else:
            return False, "Database error"
    
    def remove_feed_from_db(self, feed_id: int, db_path: str = "podcast_monitor.db") -> bool:
        """Remove feed from database"""
        import sqlite3
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get feed info before deletion for logging
            cursor.execute("SELECT title FROM feeds WHERE id = ?", (feed_id,))
            result = cursor.fetchone()
            feed_title = result[0] if result else f"Feed ID {feed_id}"
            
            cursor.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"✅ Removed feed: {feed_title}")
                result = True
            else:
                logger.warning(f"Feed ID {feed_id} not found")
                result = False
                
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error removing feed: {e}")
            return False

    # ---------- Quotas ----------
    def validate_quota_usage(self, tokens_used: int, requests_made: int) -> Dict[str, Any]:
        over_tokens = tokens_used > self.DAILY_TOKEN_LIMIT
        over_reqs = requests_made > self.DAILY_REQUEST_LIMIT
        return {
            "ok": not (over_tokens or over_reqs),
            "over_tokens": over_tokens,
            "over_requests": over_reqs,
            "limit_tokens": self.DAILY_TOKEN_LIMIT,
            "limit_requests": self.DAILY_REQUEST_LIMIT,
        }


# Singleton exported for `from config.production import ProductionConfig` use
production_config = ProductionConfig()

# Convenience re-exports expected by parts of the codebase that import from `config`:
def get_utc_now() -> datetime:
    return production_config.get_utc_now()

def format_rss_date(date: Optional[datetime] = None) -> str:
    return production_config.format_rss_date(date)

def get_weekday_label(date: Optional[datetime] = None) -> str:
    return production_config.get_weekday_label(date)

def validate_quota_usage(tokens_used: int, requests_made: int) -> Dict[str, Any]:
    return production_config.validate_quota_usage(tokens_used, requests_made)
