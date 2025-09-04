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
        # Provide defaults for OPENAI_SETTINGS / OPENAI_MODELS used by the codebase
        self.OPENAI_SETTINGS = {
            "model": self.SUMMARY_MODEL,
            "temperature": float(_env("SUMMARY_TEMPERATURE", "0.2")),
            "max_tokens": int(_env("SUMMARY_MAX_TOKENS", "1600")),
            "timeout": int(_env("OPENAI_TIMEOUT_SECS", "60")),
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
