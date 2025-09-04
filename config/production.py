#!/usr/bin/env python3
"""
Production Configuration Management for Podcast Scraper

Addresses critical production hardening issues:
1. Environment-driven base URL configuration
2. UTC timezone standardization 
3. Content-based GUID generation
4. Quota management settings
5. Security boundary enforcement
"""

import os
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class ProductionConfig:
    """Production configuration with environment validation"""
    
    def __init__(self):
        self._validate_environment()
        self._load_configuration()
    
    def _validate_environment(self):
        """Validate required environment variables"""
        
        required_vars = {
            'PODCAST_BASE_URL': 'Base URL for podcast feed (e.g., https://podcast.example.com)',
            'AUDIO_BASE_URL': 'Base URL for audio files (e.g., https://example.com/audio)'
        }
        
        missing_vars = []
        for var, description in required_vars.items():
            if not os.getenv(var):
                missing_vars.append(f"{var}: {description}")
        
        if missing_vars:
            logger.warning("⚠️ Missing environment variables for production:")
            for var in missing_vars:
                logger.warning(f"  - {var}")
    
    def _load_configuration(self):
        """Load production configuration from environment"""
        
        # Base URLs - environment driven with fallbacks
        self.PODCAST_BASE_URL = os.getenv('PODCAST_BASE_URL', 'https://podcast.paulrbrown.org')
        self.AUDIO_BASE_URL = os.getenv('AUDIO_BASE_URL', 'https://paulrbrown.org/audio')
        
        # Ensure URLs don't have trailing slashes
        self.PODCAST_BASE_URL = self.PODCAST_BASE_URL.rstrip('/')
        self.AUDIO_BASE_URL = self.AUDIO_BASE_URL.rstrip('/')
        
        # Validate URLs
        if not self._is_valid_url(self.PODCAST_BASE_URL):
            raise ValueError(f"Invalid PODCAST_BASE_URL: {self.PODCAST_BASE_URL}")
        if not self._is_valid_url(self.AUDIO_BASE_URL):
            raise ValueError(f"Invalid AUDIO_BASE_URL: {self.AUDIO_BASE_URL}")
        
        # Environment detection
        self.ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
        self.IS_PRODUCTION = self.ENVIRONMENT.lower() == 'production'
        
        # Quota management
        self.OPENAI_DAILY_TOKEN_LIMIT = int(os.getenv('OPENAI_DAILY_TOKEN_LIMIT', '50000'))
        self.YOUTUBE_DAILY_REQUEST_LIMIT = int(os.getenv('YOUTUBE_DAILY_REQUEST_LIMIT', '1000'))
        self.MAX_EPISODES_PER_RUN = int(os.getenv('MAX_EPISODES_PER_RUN', '20'))
        
        # Security settings
        self.MAX_FILENAME_LENGTH = 200  # Conservative limit
        self.MAX_XML_CONTENT_LENGTH = 10000  # Prevent XML bombs
        self.ENABLE_CONTENT_VALIDATION = True
        
        # Timezone standardization
        self.DEFAULT_TIMEZONE = timezone.utc
        
        logger.info(f"🔧 Production config loaded:")
        logger.info(f"  Environment: {self.ENVIRONMENT}")
        logger.info(f"  Podcast URL: {self.PODCAST_BASE_URL}")
        logger.info(f"  Audio URL: {self.AUDIO_BASE_URL}")
        
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None
    
    def generate_stable_guid(self, topic: str, episode_ids: list, date: datetime = None) -> str:
        """
        Generate stable GUID based on content, not runtime
        
        This addresses the critical GUID immutability issue by using:
        1. Topic name
        2. Episode IDs (content-based)  
        3. Date (canonical date, not runtime)
        
        Same content always produces same GUID.
        """
        
        if date is None:
            date = datetime.now(self.DEFAULT_TIMEZONE)
        
        # Create content hash from episode IDs (sorted for consistency)
        sorted_episode_ids = sorted(episode_ids) if episode_ids else ['no-episodes']
        content_identifier = f"{topic}|{date.strftime('%Y-%m-%d')}|{','.join(sorted_episode_ids)}"
        
        # Generate stable hash
        content_hash = hashlib.md5(content_identifier.encode()).hexdigest()[:12]
        
        # Create stable GUID
        date_str = date.strftime('%Y-%m-%d')
        topic_slug = topic.lower().replace(' ', '-').replace('&', 'and')
        
        stable_guid = f"{self.PODCAST_BASE_URL}/digest/{date_str}/{topic_slug}/{content_hash}"
        
        return stable_guid
    
    def get_utc_now(self) -> datetime:
        """Get current UTC time - standardized timezone handling"""
        return datetime.now(self.DEFAULT_TIMEZONE)
    
    def get_weekday_label(self, date: datetime = None) -> str:
        """
        Get weekday label using UTC time consistently
        
        Addresses timezone consistency issue
        """
        if date is None:
            date = self.get_utc_now()
        
        weekday = date.strftime('%A')
        
        if weekday == 'Friday':
            return 'Weekly Digest'
        elif weekday == 'Monday':
            return 'Catch-up Digest'
        else:
            return f'{weekday} Digest'
    
    def format_rss_date(self, date: datetime = None) -> str:
        """Format date for RSS feed in UTC"""
        if date is None:
            date = self.get_utc_now()
        
        # Ensure UTC timezone
        if date.tzinfo is None:
            date = date.replace(tzinfo=self.DEFAULT_TIMEZONE)
        elif date.tzinfo != self.DEFAULT_TIMEZONE:
            date = date.astimezone(self.DEFAULT_TIMEZONE)
        
        return date.strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    def validate_quota_usage(self, tokens_used: int, requests_made: int) -> Dict[str, Any]:
        """Validate quota usage against limits"""
        
        return {
            'tokens': {
                'used': tokens_used,
                'limit': self.OPENAI_DAILY_TOKEN_LIMIT,
                'percentage': (tokens_used / self.OPENAI_DAILY_TOKEN_LIMIT) * 100,
                'within_limit': tokens_used <= self.OPENAI_DAILY_TOKEN_LIMIT
            },
            'requests': {
                'made': requests_made,
                'limit': self.YOUTUBE_DAILY_REQUEST_LIMIT,
                'percentage': (requests_made / self.YOUTUBE_DAILY_REQUEST_LIMIT) * 100,
                'within_limit': requests_made <= self.YOUTUBE_DAILY_REQUEST_LIMIT
            },
            'should_continue': (
                tokens_used <= self.OPENAI_DAILY_TOKEN_LIMIT and
                requests_made <= self.YOUTUBE_DAILY_REQUEST_LIMIT
            )
        }
    
    def get_rss_channel_info(self) -> Dict[str, str]:
        """Get RSS channel information with environment-driven URLs"""
        
        return {
            'title': 'Daily Tech & Society Digest',
            'description': 'AI-generated daily digest covering technology, society, and culture from leading podcasts and creators, organized by topic',
            'link': f"{self.PODCAST_BASE_URL}/daily-digest",
            'language': 'en-US',
            'copyright': '© 2025 Paul Brown',
            'managing_editor': 'podcast@paulrbrown.org (Paul Brown)',
            'webmaster': 'podcast@paulrbrown.org (Paul Brown)',
            'author': 'Paul Brown',
            'summary': 'AI-generated daily digest covering technology, society, and culture from leading podcasts and creators, organized by topic',
            'owner': 'Paul Brown',
            'artwork_url': f"{self.PODCAST_BASE_URL}/podcast-artwork.jpg",
            'category': 'Technology',
            'explicit': 'no',
            'feed_url': f"{self.PODCAST_BASE_URL}/daily-digest.xml"
        }
    
    def get_audio_url(self, filename: str) -> str:
        """Get audio URL for a given filename"""
        return f"{self.AUDIO_BASE_URL}/{filename}"
    
    def get_episode_link(self, timestamp: str) -> str:
        """Get episode permalink"""
        return f"{self.PODCAST_BASE_URL}/daily-digest/{timestamp}"

# Global production config instance
production_config = ProductionConfig()

# Convenience functions
def get_stable_guid(topic: str, episode_ids: list, date: datetime = None) -> str:
    """Generate stable GUID - content-based, not runtime-based"""
    return production_config.generate_stable_guid(topic, episode_ids, date)

def get_utc_now() -> datetime:
    """Get current UTC time consistently"""
    return production_config.get_utc_now()

def format_rss_date(date: datetime = None) -> str:
    """Format date for RSS feed consistently"""
    return production_config.format_rss_date(date)

def get_weekday_label(date: datetime = None) -> str:
    """Get weekday label consistently"""
    return production_config.get_weekday_label(date)

def validate_quota_usage(tokens_used: int, requests_made: int) -> Dict[str, Any]:
    """Validate quota usage"""
    return production_config.validate_quota_usage(tokens_used, requests_made)