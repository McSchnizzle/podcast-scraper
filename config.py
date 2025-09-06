#!/usr/bin/env python3
"""
Centralized Configuration Management for Podcast Scraper
Consolidates all configuration settings and environment validation
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# Load environment variables
try:
    from dotenv import load_dotenv
    # Load from the same directory as config.py
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

logger = logging.getLogger(__name__)

class Config:
    """Centralized configuration management"""
    
    def __init__(self, require_claude: bool = True):
        # Base paths
        self.PROJECT_ROOT = Path(__file__).parent
        self.DB_PATH = "podcast_monitor.db"
        
        # Directory configurations
        self.AUDIO_CACHE_DIR = "audio_cache"
        self.TRANSCRIPTS_DIR = "transcripts"
        self.TRANSCRIPTS_DIGESTED_DIR = "transcripts/digested"
        self.DAILY_DIGESTS_DIR = "daily_digests"
        self.DOCS_DIR = "docs"
        self.API_DIR = "api"
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Database settings
        self.DB_SETTINGS = {
            'timeout': 30,  # seconds
            'check_same_thread': False
        }
        
        # Feed monitoring settings (Phase 4 Enhanced)
        self.FEED_SETTINGS = {
            'check_interval_hours': 24,
            'max_episodes_per_feed': int(os.getenv('FEED_MAX_ITEMS_PER_FEED', '50')),
            'break_on_old': os.getenv('FEED_BREAK_ON_OLD', '1') == '1',
            'stale_feed_days': int(os.getenv('FEED_STALE_DAYS', '21')),
            'youtube_min_duration': 180,  # 3 minutes
            'user_agent': 'PodcastDigest/2.0 (+https://github.com/McSchnizzle/podcast-scraper)',
            'request_timeout': int(os.getenv('REQUEST_TIMEOUT', '30')),
            'max_retries': int(os.getenv('MAX_RETRIES', '4')),
            'backoff_base_delay': float(os.getenv('BACKOFF_BASE_DELAY', '0.5')),
            
            # Phase 4: Enhanced robustness settings
            'lookback_hours': max(1, min(168, int(os.getenv('FEED_LOOKBACK_HOURS', '48')))),  # 1-168 hours (7 days max)
            'grace_minutes': int(os.getenv('FEED_GRACE_MINUTES', '15')),  # Avoid boundary flapping
            'max_feed_bytes': int(os.getenv('MAX_FEED_BYTES', '5242880')),  # 5MB safety cap
            'politeness_delay_ms': int(os.getenv('FETCH_POLITENESS_MS', '250')),  # Polite delay between requests
            'enable_http_caching': os.getenv('ENABLE_HTTP_CACHING', '1') == '1',  # ETag/Last-Modified support
            'detect_feed_order': os.getenv('DETECT_FEED_ORDER', '1') == '1',  # Auto-detect typical_order
            'item_seen_retention_days': int(os.getenv('ITEM_SEEN_RETENTION_DAYS', '30')),  # Cleanup old item_seen records
        }
        
        # Content processing settings
        self.PROCESSING_SETTINGS = {
            'max_audio_chunk_minutes': 10,
            'priority_threshold': 0.3,
            'max_file_size_mb': 500,
            'supported_audio_formats': ['.mp3', '.wav', '.m4a', '.mp4']
        }
        
        # Transcription settings
        self.TRANSCRIPTION_SETTINGS = {
            'parakeet_model': 'parakeet-multilingual',
            'chunk_duration_seconds': 600,  # 10 minutes
            'overlap_seconds': 10,
            'max_retries': 3,
            'timeout_seconds': 1800  # 30 minutes
        }
        
        # Claude integration settings
        self.CLAUDE_SETTINGS = {
            'command': 'claude',
            'timeout_seconds': 300,  # 5 minutes
            'max_transcripts': 10,
            'lookback_days': 7
        }
        
        # TTS settings
        self.TTS_SETTINGS = {
            'base_url': 'https://api.elevenlabs.io/v1',
            'model_id': 'eleven_multilingual_v2',
            'timeout_seconds': 120,
            'max_text_length': 50000
        }
        
        # OpenAI GPT-5 Configuration (Phase 2 Enhanced)
        # Standardized model pinning with per-component override capability
        self.GPT5_MODELS = {
            'summary': os.getenv('GPT5_SUMMARY_MODEL', 'gpt-5-mini'),
            'scorer': os.getenv('GPT5_SCORER_MODEL', 'gpt-5-mini'),
            'digest': os.getenv('GPT5_DIGEST_MODEL', 'gpt-5'),
            'validator': os.getenv('GPT5_VALIDATOR_MODEL', 'gpt-5-mini')
        }
        
        # Standardized token configuration (max_output_tokens for Responses API)
        self.OPENAI_TOKENS = {
            'summary': int(os.getenv('SUMMARY_MAX_OUTPUT_TOKENS', '500')),
            'scorer': int(os.getenv('SCORER_MAX_OUTPUT_TOKENS', '700')),
            'digest': int(os.getenv('DIGEST_MAX_OUTPUT_TOKENS', '4000')),
            'validator': int(os.getenv('VALIDATOR_MAX_OUTPUT_TOKENS', '4000'))
        }
        
        # Reasoning effort configuration (per-component for GPT-5)
        self.REASONING_EFFORT = {
            'summary': os.getenv('SUMMARY_REASONING_EFFORT', 'minimal'),
            'scorer': os.getenv('SCORER_REASONING_EFFORT', 'minimal'),
            'digest': os.getenv('DIGEST_REASONING_EFFORT', 'minimal'),
            'validator': os.getenv('VALIDATOR_REASONING_EFFORT', 'medium')  # Higher fidelity for validation
        }
        
        # Quality thresholds and guardrails
        self.QUALITY_THRESHOLDS = {
            'relevance_threshold': float(os.getenv('RELEVANCE_THRESHOLD', '0.65')),
            'min_chunks_ok': int(os.getenv('MIN_CHUNKS_OK', '2')),
            'min_coverage_pct': float(os.getenv('MIN_COVERAGE_PCT', '0.6'))
        }
        
        # Execution settings
        self.EXECUTION_SETTINGS = {
            'max_parallel_requests': int(os.getenv('MAX_PARALLEL_REQUESTS', '4')),
            'timeout_seconds': int(os.getenv('OPENAI_TIMEOUT_SECONDS', '60')),
            'max_retries': 4,
            'backoff_base_delay': 0.75
        }
        
        # Feature flags for staged rollout
        self.FEATURE_FLAGS = {
            'use_gpt5_summaries': os.getenv('USE_GPT5_SUMMARIES', '1') == '1',
            'use_gpt5_digest': os.getenv('USE_GPT5_DIGEST', '1') == '1',
            'use_gpt5_validator': os.getenv('USE_GPT5_VALIDATOR', '1') == '1'
        }
        
        # Legacy compatibility (deprecated - will be removed)
        self.OPENAI_SETTINGS = {
            # Legacy model names (deprecated - use GPT5_MODELS)
            'digest_model': self.GPT5_MODELS['digest'],
            'scoring_model': self.GPT5_MODELS['scorer'], 
            'validator_model': self.GPT5_MODELS['validator'],
            
            # Legacy settings
            'timeout_seconds': self.EXECUTION_SETTINGS['timeout_seconds'],
            'batch_size': 5,
            'rate_limit_delay': 1,
            'relevance_threshold': self.QUALITY_THRESHOLDS['relevance_threshold'],
            
            # Map-reduce settings
            'max_episodes_per_topic': 6,
            'max_episode_summary_tokens': 450,
            'max_reduce_tokens': 6000,
            'max_retries': self.EXECUTION_SETTINGS['max_retries'],
            'backoff_base_delay': self.EXECUTION_SETTINGS['backoff_base_delay'],
            
            'topics': {
                'AI & Intelligence': {
                    'description': 'Artificial intelligence news, AI products and services, machine learning breakthroughs, AI industry developments, AI culture and society impact, AI ethics and policy',
                    'prompt': 'artificial intelligence, AI news, machine learning, deep learning, AI research, AI products, AI services, AI breakthroughs, AI industry, AI policy, AI ethics, AI regulation, generative AI, LLMs, AI startups, AI funding, AI culture, AI impact on society'
                },
                'Tech & Innovation': {
                    'description': 'Non-AI technology news, tech product releases, software updates, hardware launches, tech industry developments, digital innovation and tech culture trends',
                    'prompt': 'technology news, tech products, software release, hardware launch, tech innovation, technology trends, tech industry news, startup news, digital transformation, emerging technology, consumer electronics, tech culture, software updates, product announcements, tech companies'
                },
                'Social Justice & Organizing': {
                    'description': 'Social justice movements, community organizing efforts, civil rights advocacy, grassroots activism, systemic change initiatives, community building and mobilization strategies',
                    'prompt': 'social justice, community organizing, civil rights, activism, grassroots organizing, social equity, community building, social movements, systemic change, racial justice, economic justice, community advocacy, local organizing, civic engagement, community mobilization'
                },
                'Culture & Future': {
                    'description': 'Cultural shifts and social transformation, philosophical discussions, policy analysis, future thinking, generational changes, societal trends, consciousness and meaning exploration',
                    'prompt': 'cultural change, social transformation, philosophy, future thinking, policy analysis, generational change, cultural evolution, social change, cultural trends, societal transformation, consciousness, meaning, ethics, philosophical discussions, cultural movements, policy implications'
                }
            }
        }
        
        # Pipeline settings
        self.PIPELINE_SETTINGS = {
            'retention_days': 14,  # Updated to 14-day retention
            'max_rss_episodes': 7,
            'cleanup_audio_cache': True,
            'cleanup_intermediate_files': True
        }
        
        # Status workflow
        self.STATUS_WORKFLOW = {
            'rss': ['pre-download', 'downloaded', 'transcribed', 'digested'],
            'youtube': ['pre-download', 'transcribed', 'digested'],
            'valid_statuses': ['pre-download', 'downloaded', 'transcribed', 'digested', 'failed', 'skipped']
        }
        
        # Environment variables
        self.GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
        self.ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        
        # Validate environment
        self._validate_environment(require_claude=require_claude)
    
    def _ensure_directories(self):
        """Create necessary directories"""
        directories = [
            self.AUDIO_CACHE_DIR,
            self.TRANSCRIPTS_DIR,
            self.TRANSCRIPTS_DIGESTED_DIR,
            self.DAILY_DIGESTS_DIR
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def _validate_environment(self, require_claude: bool = True):
        """Validate environment configuration"""
        warnings = []
        errors = []
        
        # Check for critical environment variables
        if not self.GITHUB_TOKEN:
            warnings.append("GITHUB_TOKEN not set - deployment features will be disabled")
        
        if not self.ELEVENLABS_API_KEY:
            warnings.append("ELEVENLABS_API_KEY not set - TTS features will be disabled")
        
        if not self.OPENAI_API_KEY:
            warnings.append("OPENAI_API_KEY not set - OpenAI digest generation will be disabled")
        
        # Validate OPENAI_SETTINGS has all required fields
        required_openai_fields = [
            'relevance_threshold', 'scoring_model', 'validator_model', 'digest_model'
        ]
        
        missing_fields = []
        for field in required_openai_fields:
            if field not in self.OPENAI_SETTINGS:
                missing_fields.append(field)
        
        if missing_fields:
            errors.append(f"Missing OPENAI_SETTINGS fields: {', '.join(missing_fields)}")
        else:
            logger.debug("✅ OPENAI_SETTINGS validation passed")
        
        # Check .env file loading
        env_file = Path('.env')
        if env_file.exists():
            logger.debug("✅ .env file found and loaded")
        else:
            warnings.append(".env file not found - using environment variables only")
        
        # Check for required tools
        if require_claude:
            try:
                import subprocess
                subprocess.run(['claude', '--version'], capture_output=True, timeout=5)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                errors.append("Claude Code CLI not found - install from https://claude.ai/code")
        else:
            # For YouTube-only processing, Claude is optional
            try:
                import subprocess
                subprocess.run(['claude', '--version'], capture_output=True, timeout=5)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                warnings.append("Claude Code CLI not found - digest generation will use OpenAI fallback")
        
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            errors.append("ffmpeg not found - install with 'brew install ffmpeg'")
        
        # Log warnings and errors
        for warning in warnings:
            logger.warning(f"⚠️ {warning}")
        
        for error in errors:
            logger.error(f"❌ {error}")
        
        if errors:
            logger.error("❌ Critical dependencies missing - some features may not work")
        else:
            logger.info("✅ Environment validation passed")
    
    def get_feed_config(self) -> list:
        """Get complete feed configuration with all monitored feeds
        
        Note: topic_category is informational only. Content selection is 100% score-based
        using AI relevance scoring against the 6 defined topics in topics.json.
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
                'title': 'The AI Advantage',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCHLrz6tGLIASQ3ELy4FWWwQ',
                'type': 'youtube',
                'topic_category': 'technology'
            },
            {
                'title': 'How I AI',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UC6jBgC88wZ_VCxhlGK8FhNg',
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
                'title': 'Wes Roth',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCJLOLiEJbPy3-oOhm6Hq1xw',
                'type': 'youtube',
                'topic_category': 'technology'
            },
            {
                'title': 'Matt Wolfe',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCbUXAm7XBrwD_6MqKw9jIzQ',
                'type': 'youtube',
                'topic_category': 'technology'
            },
            {
                'title': 'All About AI',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCc6aQRkhMnE4VgDyC8BjXgw',
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
                'url': 'https://feeds.acast.com/public/shows/the-diary-of-a-ceo',
                'type': 'rss',
                'topic_category': 'business'
            },
            
            # Philosophy & Society
            {
                'title': 'Slo Mo: A Podcast with Mo Gawdat',
                'url': 'https://feeds.acast.com/public/shows/slo-mo-a-podcast-with-mo-gawdat',
                'type': 'rss',
                'topic_category': 'philosophy'
            },
            {
                'title': 'Team Human',
                'url': 'https://feeds.megaphone.fm/team-human',
                'type': 'rss',
                'topic_category': 'philosophy'
            },
            {
                'title': 'The Great Simplification with Nate Hagens',
                'url': 'https://feeds.simplecast.com/wjfQWXFi',
                'type': 'rss',
                'topic_category': 'philosophy'
            },
            
            # Political & Social Commentary
            {
                'title': 'THIS IS REVOLUTION ＞podcast',
                'url': 'https://feeds.soundcloud.com/users/soundcloud:users:382887892/sounds.rss',
                'type': 'rss',
                'topic_category': 'politics'
            },
            {
                'title': 'The Red Nation Podcast',
                'url': 'https://feeds.soundcloud.com/users/soundcloud:users:528135913/sounds.rss',
                'type': 'rss',
                'topic_category': 'politics'
            },
            {
                'title': 'Movement Memos',
                'url': 'https://feeds.soundcloud.com/users/soundcloud:users:929651237/sounds.rss',
                'type': 'rss',
                'topic_category': 'politics'
            },
            {
                'title': 'Real Sankara Hours',
                'url': 'https://feeds.soundcloud.com/users/soundcloud:users:456789123/sounds.rss',
                'type': 'rss',
                'topic_category': 'politics'
            },
            {
                'title': 'Millennials Are Killing Capitalism',
                'url': 'https://feeds.soundcloud.com/users/soundcloud:users:345678912/sounds.rss',
                'type': 'rss',
                'topic_category': 'politics'
            },
            
            # Black Culture & History
            {
                'title': 'The Black Myths Podcast',
                'url': 'https://feeds.soundcloud.com/users/soundcloud:users:567891234/sounds.rss',
                'type': 'rss',
                'topic_category': 'culture'
            },
            {
                'title': 'The Malcolm Effect',
                'url': 'https://feeds.soundcloud.com/users/soundcloud:users:678912345/sounds.rss',
                'type': 'rss',
                'topic_category': 'culture'
            },
            {
                'title': 'The Dugout | a black anarchist podcast',
                'url': 'https://feeds.soundcloud.com/users/soundcloud:users:789123456/sounds.rss',
                'type': 'rss',
                'topic_category': 'culture'
            },
            {
                'title': 'Black Autonomy Podcast',
                'url': 'https://feeds.soundcloud.com/users/soundcloud:users:891234567/sounds.rss',
                'type': 'rss',
                'topic_category': 'culture'
            },
            
            # Development & Gaming YouTube
            {
                'title': 'Indy Dev Dan',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCBBVaGh4BqG6KXkR2t9Jq-g',
                'type': 'youtube',
                'topic_category': 'technology'
            },
            {
                'title': 'Robin',
                'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCaO6VoaYJv4kS-TQO_M-N_g',
                'type': 'youtube',
                'topic_category': 'technology'
            }
        ]
    
    def sync_feeds_to_database(self, db_path: str = "podcast_monitor.db", force_update: bool = False):
        """Sync feed configuration to database (database is source of truth)"""
        from utils.db import get_connection
        
        conn = get_connection(db_path)
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
        from utils.db import get_connection
        
        try:
            conn = get_connection(db_path)
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
        from utils.db import get_connection
        
        try:
            conn = get_connection(db_path)
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
    
    def remove_feed_from_db(self, feed_id: int, db_path: str = "podcast_monitor.db") -> bool:
        """Remove feed from database"""
        from utils.db import get_connection
        
        try:
            conn = get_connection(db_path)
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
    
    def get_voice_config(self) -> Dict[str, Dict]:
        """Get TTS voice configuration"""
        return {
            "ai_tools": {
                "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel - clear, professional
                "stability": 0.75,
                "similarity_boost": 0.75,
                "style": 0.15
            },
            "product_launches": {
                "voice_id": "AZnzlk1XvdvUeBnXmlld",  # Domi - energetic, engaging
                "stability": 0.70,
                "similarity_boost": 0.80,
                "style": 0.25
            },
            "creative_applications": {
                "voice_id": "EXAVITQu4vr4xnSDxMaL",  # Bella - warm, creative
                "stability": 0.65,
                "similarity_boost": 0.75,
                "style": 0.35
            },
            "technical_insights": {
                "voice_id": "ErXwobaYiN019PkySvjV",  # Antoni - authoritative
                "stability": 0.80,
                "similarity_boost": 0.70,
                "style": 0.10
            },
            "business_analysis": {
                "voice_id": "VR6AewLTigWG4xSOukaG",  # Arnold - confident
                "stability": 0.85,
                "similarity_boost": 0.75,
                "style": 0.20
            },
            "social_commentary": {
                "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam - thoughtful
                "stability": 0.75,
                "similarity_boost": 0.80,
                "style": 0.30
            },
            "intro_outro": {
                "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel - consistent host voice
                "stability": 0.85,
                "similarity_boost": 0.75,
                "style": 0.20
            }
        }
    
    def is_valid_status(self, status: str) -> bool:
        """Check if status is valid"""
        return status in self.STATUS_WORKFLOW['valid_statuses']
    
    def get_next_status(self, current_status: str, episode_type: str = 'rss') -> Optional[str]:
        """Get the next valid status in workflow"""
        workflow = self.STATUS_WORKFLOW[episode_type]
        
        try:
            current_index = workflow.index(current_status)
            if current_index < len(workflow) - 1:
                return workflow[current_index + 1]
        except ValueError:
            pass
        
        return None
    
    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access to config values"""
        return getattr(self, key, None)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            attr: getattr(self, attr)
            for attr in dir(self)
            if not attr.startswith('_') and not callable(getattr(self, attr))
        }

# Global configuration instance
config = Config()

if __name__ == "__main__":
    # Test configuration
    print("Configuration Summary:")
    print(f"Database: {config.DB_PATH}")
    print(f"GitHub Token: {'Set' if config.GITHUB_TOKEN else 'Not set'}")
    print(f"ElevenLabs API Key: {'Set' if config.ELEVENLABS_API_KEY else 'Not set'}")
    print(f"Status Workflow (RSS): {' → '.join(config.STATUS_WORKFLOW['rss'])}")
    print(f"Status Workflow (YouTube): {' → '.join(config.STATUS_WORKFLOW['youtube'])}")
    print(f"Feed Count: {len(config.get_feed_config())}")