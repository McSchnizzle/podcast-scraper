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
    SUMMARY_MODEL: str = _env("SUMMARY_MODEL", "gpt-4o-mini")
    SCORER_MODEL: str = _env("SCORER_MODEL", "gpt-4o-mini")
    PROSE_VALIDATOR_MODEL: str = _env("PROSE_VALIDATOR_MODEL", "gpt-4-turbo-preview")

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
        # Provide complete OPENAI_SETTINGS structure expected by the codebase
        self.OPENAI_SETTINGS = {
            # Model configuration - using actual OpenAI model names
            'digest_model': _env('DIGEST_MODEL', 'gpt-4-turbo-preview'),
            'scoring_model': _env('SCORING_MODEL', 'gpt-4o-mini'),  # Cost-effective for scoring
            'validator_model': _env('VALIDATOR_MODEL', 'gpt-4o-mini'),  # Cost-effective for validation
            
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
