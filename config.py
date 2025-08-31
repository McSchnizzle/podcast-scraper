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
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

class Config:
    """Centralized configuration management"""
    
    def __init__(self):
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
        
        # Feed monitoring settings
        self.FEED_SETTINGS = {
            'check_interval_hours': 24,
            'max_episodes_per_feed': 10,
            'youtube_min_duration': 180,  # 3 minutes
            'user_agent': 'PodcastDigest/1.0 (+https://github.com/McSchnizzle/podcast-scraper)'
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
        
        # Pipeline settings
        self.PIPELINE_SETTINGS = {
            'retention_days': 7,
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
        
        # Validate environment
        self._validate_environment()
    
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
    
    def _validate_environment(self):
        """Validate environment configuration"""
        warnings = []
        errors = []
        
        # Check for critical environment variables
        if not self.GITHUB_TOKEN:
            warnings.append("GITHUB_TOKEN not set - deployment features will be disabled")
        
        if not self.ELEVENLABS_API_KEY:
            warnings.append("ELEVENLABS_API_KEY not set - TTS features will be disabled")
        
        # Check for required tools
        try:
            import subprocess
            subprocess.run(['claude', '--version'], capture_output=True, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            errors.append("Claude Code CLI not found - install from https://claude.ai/code")
        
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
        """Get default feed configuration"""
        return [
            {
                'title': 'The Vergecast',
                'url': 'https://feeds.megaphone.fm/vergecast',
                'type': 'rss',
                'topic_category': 'technology'
            },
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
            }
        ]
    
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