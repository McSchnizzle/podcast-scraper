#!/usr/bin/env python3
"""
Episode Summary Generator - GPT-5 Implementation (Phase 2)
Generates per-episode summaries using GPT-5 Responses API with chunking and robust error handling
"""

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.datetime_utils import now_utc
from utils.db import get_connection

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from config import config
from utils.logging_setup import configure_logging
from utils.openai_helpers import (
    call_openai_with_backoff,
    generate_idempotency_key,
    get_json_schema,
)

configure_logging()
logger = logging.getLogger(__name__)


def approx_tokens(text: str) -> int:
    """Estimate token count using simple heuristic"""
    return (len(text) + 3) // 4


class EpisodeSummaryGenerator:
    """GPT-5 powered episode summarizer with chunking, caching, and idempotency"""

    def __init__(self, cache_db_path: str = "episode_summaries.db"):
        """Initialize the episode summary generator with GPT-5"""
        self.cache_db_path = cache_db_path
        self.client = None
        self.api_available = False

        # Check for mock mode
        self.mock_mode = os.getenv("MOCK_OPENAI") == "1" or os.getenv("CI_SMOKE") == "1"

        if self.mock_mode:
            logger.info("🧪 MOCK MODE: Using mock OpenAI responses for summaries")
            self.client = None
            self.api_available = True
        else:
            # Initialize OpenAI client
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY environment variable not set")
                self.client = None
                self.api_available = False
            else:
                try:
                    from openai import OpenAI

                    self.client = OpenAI(api_key=api_key.strip())
                    self.api_available = True
                    logger.info(
                        f"✅ Episode Summary Generator initialized with {config.GPT5_MODELS['summary']}"
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI client: {e}")
                    self.client = None
                    self.api_available = False

        # Configuration from new Phase 2 settings
        self.model = config.GPT5_MODELS["summary"]
        self.max_output_tokens = config.OPENAI_TOKENS["summary"]
        self.reasoning_effort = config.REASONING_EFFORT["summary"]
        self.feature_enabled = config.FEATURE_FLAGS["use_gpt5_summaries"]

        # Chunking configuration
        self.chunk_size = 2200  # Characters per chunk
        self.chunk_overlap = 200  # Character overlap between chunks

        # Initialize cache database
        self._init_cache_db()

        # Log configuration on startup
        logger.info(
            f"component=summary model={self.model} max_output_tokens={self.max_output_tokens} "
            f"reasoning={self.reasoning_effort} feature_enabled={self.feature_enabled}"
        )

    def _init_cache_db(self):
        """Initialize SQLite database for caching summaries with idempotency"""
        try:
            with get_connection(self.cache_db_path) as conn:
                # Enhanced summaries table with idempotency support
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS episode_summaries (
                        content_hash TEXT PRIMARY KEY,
                        episode_id TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        char_start INTEGER NOT NULL,
                        char_end INTEGER NOT NULL,
                        topic TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        tokens_used INTEGER,
                        model TEXT NOT NULL,
                        prompt_version TEXT NOT NULL DEFAULT '1.0',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        word_count INTEGER
                    )
                """
                )

                # Idempotency constraint for summaries
                conn.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_summaries
                    ON episode_summaries(episode_id, chunk_index, prompt_version, model)
                """
                )

                # Run headers table for observability
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS run_headers (
                        run_id TEXT PRIMARY KEY,
                        component TEXT NOT NULL,
                        started_at DATETIME NOT NULL,
                        finished_at DATETIME,
                        model TEXT NOT NULL,
                        reasoning_effort TEXT,
                        tokens_in INTEGER,
                        tokens_out INTEGER,
                        chunk_count INTEGER,
                        failures INTEGER DEFAULT 0,
                        wall_ms INTEGER,
                        prompt_version TEXT DEFAULT '1.0'
                    )
                """
                )

                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_topic_timestamp ON episode_summaries(topic, timestamp)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_run_component ON run_headers(component, started_at)"
                )
                conn.commit()

            logger.info(
                f"📚 Summary cache database initialized with idempotency: {self.cache_db_path}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize cache database: {e}")

    def create_chunks(
        self, content: str, episode_id: str, title: str = ""
    ) -> List[Tuple[int, int, int, str]]:
        """
        Create overlapping chunks from content for processing

        Returns:
            List of (chunk_index, char_start, char_end, chunk_text) tuples
        """
        if not content or len(content.strip()) < self.chunk_size:
            return [(0, 0, len(content), content)]

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(content):
            end = min(start + self.chunk_size, len(content))

            # Try to break at sentence boundary if not the last chunk
            if end < len(content):
                # Look for sentence ending within overlap region
                search_start = max(start, end - self.chunk_overlap)
                sentence_break = content.rfind(". ", search_start, end)
                if sentence_break > search_start:
                    end = sentence_break + 1

            chunk_text = content[start:end].strip()
            if chunk_text:
                chunks.append((chunk_index, start, end, chunk_text))
                logger.info(
                    f'Chunk {chunk_index + 1}: {start}-{end} • "{title or episode_id}"'
                )
                chunk_index += 1

            # Move start forward, accounting for overlap
            start = end - self.chunk_overlap if end < len(content) else end

        logger.info(f"Created {len(chunks)} chunks for episode {episode_id}")
        return chunks

    def _get_cached_chunk_summary(
        self, episode_id: str, chunk_index: int
    ) -> Optional[Dict]:
        """Retrieve cached chunk summary if available"""
        try:
            with get_connection(self.cache_db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT summary, tokens_used, model, char_start, char_end
                    FROM episode_summaries
                    WHERE episode_id = ? AND chunk_index = ? AND model = ? AND prompt_version = '1.0'
                """,
                    (episode_id, chunk_index, self.model),
                )
                row = cursor.fetchone()

                if row:
                    return {
                        "episode_id": episode_id,
                        "chunk_index": chunk_index,
                        "char_start": row[3],
                        "char_end": row[4],
                        "summary": row[0],
                        "tokens_used": row[1],
                        "model": row[2],
                        "cached": True,
                    }
        except Exception as e:
            logger.warning(f"Failed to retrieve cached chunk summary: {e}")
        return None

    def _cache_chunk_summary(self, summary_data: Dict, topic: str):
        """Cache generated chunk summary with idempotency"""
        try:
            content_hash = generate_idempotency_key(
                summary_data["episode_id"],
                summary_data["chunk_index"],
                summary_data["summary"],
            )

            with get_connection(self.cache_db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO episode_summaries
                    (content_hash, episode_id, chunk_index, char_start, char_end, topic,
                     timestamp, summary, tokens_used, model, prompt_version, word_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        content_hash,
                        summary_data["episode_id"],
                        summary_data["chunk_index"],
                        summary_data["char_start"],
                        summary_data["char_end"],
                        topic,
                        summary_data["timestamp"],
                        summary_data["summary"],
                        summary_data["tokens_used"],
                        summary_data["model"],
                        "1.0",
                        len(summary_data["summary"].split()),
                    ),
                )
                conn.commit()

        except Exception as e:
            logger.warning(f"Failed to cache chunk summary: {e}")

    def _record_run_header(
        self,
        run_id: str,
        episode_id: str,
        chunk_count: int,
        failures: int,
        wall_ms: int,
    ):
        """Record run header for observability"""
        try:
            with get_connection(self.cache_db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO run_headers
                    (run_id, component, started_at, finished_at, model, reasoning_effort,
                     chunk_count, failures, wall_ms, prompt_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        run_id,
                        "summary",
                        now_utc().isoformat(),
                        now_utc().isoformat(),
                        self.model,
                        self.reasoning_effort,
                        chunk_count,
                        failures,
                        wall_ms,
                        "1.0",
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to record run header: {e}")

    def _clean_content_for_summary(self, content: str, max_words: int = 1500) -> str:
        """Clean and truncate content for summary generation"""
        # Remove excessive whitespace and normalize
        cleaned = " ".join(content.split())

        # Truncate if too long
        words = cleaned.split()
        if len(words) > max_words:
            cleaned = " ".join(words[:max_words]) + "..."
            logger.debug(f"Content truncated to {max_words} words")

        return cleaned

    def _generate_fallback_chunk_summary(
        self, episode_id: str, chunk_index: int, content: str, topic: str
    ) -> Dict:
        """Generate fallback summary when API unavailable"""
        # Extract first few sentences as summary
        sentences = content.replace("\n", " ").split(". ")
        summary = ". ".join(sentences[:2])
        if not summary.endswith("."):
            summary += "."

        return {
            "episode_id": episode_id,
            "chunk_index": chunk_index,
            "char_start": 0,
            "char_end": len(content),
            "summary": summary[:400],  # Limit length
            "tokens_used": 0,
            "model": "fallback",
            "fallback": True,
            "timestamp": now_utc().isoformat(),
        }

    def _generate_mock_chunk_summary(
        self, episode_id: str, chunk_index: int, content: str, topic: str
    ) -> Dict:
        """Generate mock summary for CI smoke tests"""
        # Create deterministic but realistic mock summary
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        mock_summary = f"Mock summary for {topic.replace('_', ' ').title()} chunk {chunk_index + 1}. Content hash: {content_hash}. Generated for testing purposes."

        return {
            "episode_id": episode_id,
            "chunk_index": chunk_index,
            "char_start": 0,
            "char_end": len(content),
            "summary": mock_summary,
            "tokens_used": 50,  # Mock token count
            "model": f"mock-{self.model}",
            "mock": True,
            "timestamp": now_utc().isoformat(),
        }

    def generate_chunk_summary(
        self,
        episode_id: str,
        chunk_index: int,
        char_start: int,
        char_end: int,
        content: str,
        topic: str,
        title: str = "",
        run_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """Generate summary for a single content chunk using GPT-5"""

        if not self.feature_enabled:
            logger.info("GPT-5 summaries disabled by feature flag, using fallback")
            return self._generate_fallback_chunk_summary(
                episode_id, chunk_index, content, topic
            )

        if not self.api_available:
            logger.warning("OpenAI API not available, using fallback")
            return self._generate_fallback_chunk_summary(
                episode_id, chunk_index, content, topic
            )

        # Mock mode
        if self.mock_mode:
            return self._generate_mock_chunk_summary(
                episode_id, chunk_index, content, topic
            )

        # Check cache (idempotency)
        cached_result = self._get_cached_chunk_summary(episode_id, chunk_index)
        if cached_result:
            logger.info(
                f"📖 Using cached chunk summary: {episode_id} chunk {chunk_index}"
            )
            return cached_result

        if len(content.strip()) < 50:
            logger.info(
                f"Chunk {chunk_index} too short ({len(content)} chars), skipping"
            )
            return None

        try:
            # Clean content
            clean_content = self._clean_content_for_summary(content)

            # Prepare system prompt
            system_prompt = """You are an expert podcast content summarizer. Create concise, informative summaries of podcast transcript chunks that capture the key points and insights discussed."""

            user_prompt = f"""Summarize this podcast transcript chunk for a {topic.replace('_', ' ').title()} digest.

Focus on:
- Key topics and main points discussed
- Important insights or conclusions
- Specific facts, announcements, or developments mentioned

Content to summarize:
{clean_content}

Provide a structured summary with the essential information from this segment."""

            # Call GPT-5 via Responses API
            logger.info(
                f"🤖 Generating chunk summary: {episode_id} chunk {chunk_index} ({len(clean_content)} chars)"
            )

            idempotency_key = generate_idempotency_key(
                episode_id, chunk_index, self.model, "1.0"
            )

            result = call_openai_with_backoff(
                client=self.client,
                component="summary",
                run_id=run_id,
                idempotency_key=idempotency_key,
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                reasoning={"effort": self.reasoning_effort},
                max_output_tokens=self.max_output_tokens,
                text={"format": get_json_schema("summary")},
            )

            # Parse JSON response
            summary_data = result.to_json()

            # Add metadata
            summary_data.update(
                {
                    "episode_id": episode_id,
                    "chunk_index": chunk_index,
                    "char_start": char_start,
                    "char_end": char_end,
                    "tokens_used": result.metadata.get("tokens_out", 0),
                    "model": self.model,
                    "timestamp": now_utc().isoformat(),
                }
            )

            # Cache the result
            self._cache_chunk_summary(summary_data, topic)

            logger.info(
                f"✅ Generated chunk summary: {episode_id} chunk {chunk_index} ({result.metadata.get('tokens_out', 0)} tokens)"
            )
            return summary_data

        except Exception as e:
            logger.error(
                f"❌ Failed to generate chunk summary for {episode_id} chunk {chunk_index}: {e}"
            )
            return self._generate_fallback_chunk_summary(
                episode_id, chunk_index, content, topic
            )

    def generate_episode_summary(
        self,
        episode_id: str,
        content: str,
        topic: str,
        title: str = "",
        run_id: Optional[str] = None,
    ) -> Dict:
        """
        Generate complete episode summary with chunking and map-reduce approach

        Returns:
            Dictionary with summary data and chunk information
        """
        if run_id is None:
            run_id = generate_idempotency_key(episode_id, topic, str(now_utc()))

        start_time = time.time()

        # Create chunks
        chunks = self.create_chunks(content, episode_id, title)

        # Process each chunk
        chunk_summaries = []
        failures = 0

        for chunk_index, char_start, char_end, chunk_text in chunks:
            chunk_summary = self.generate_chunk_summary(
                episode_id=episode_id,
                chunk_index=chunk_index,
                char_start=char_start,
                char_end=char_end,
                content=chunk_text,
                topic=topic,
                title=title,
                run_id=run_id,
            )

            if chunk_summary:
                chunk_summaries.append(chunk_summary)
            else:
                failures += 1

        # Check coverage quality
        coverage_pct = len(chunk_summaries) / len(chunks) if chunks else 0
        min_chunks = config.QUALITY_THRESHOLDS["min_chunks_ok"]
        min_coverage = config.QUALITY_THRESHOLDS["min_coverage_pct"]

        status = "OK"
        if len(chunk_summaries) < min_chunks or coverage_pct < min_coverage:
            status = "PARTIAL"
            logger.warning(
                f"⚠️ Low coverage for {episode_id}: {len(chunk_summaries)}/{len(chunks)} chunks "
                f"({coverage_pct:.1%} coverage, {failures} failures)"
            )

        # Record run header
        wall_ms = int((time.time() - start_time) * 1000)
        self._record_run_header(
            run_id=run_id,
            episode_id=episode_id,
            chunk_count=len(chunks),
            failures=failures,
            wall_ms=wall_ms,
        )

        result = {
            "episode_id": episode_id,
            "topic": topic,
            "status": status,
            "chunk_summaries": chunk_summaries,
            "chunk_count": len(chunks),
            "success_count": len(chunk_summaries),
            "failure_count": failures,
            "coverage_pct": coverage_pct,
            "wall_ms": wall_ms,
            "run_id": run_id,
            "timestamp": now_utc().isoformat(),
        }

        logger.info(
            f"📊 Episode summary complete: {episode_id} status={status} "
            f"chunks={len(chunk_summaries)}/{len(chunks)} coverage={coverage_pct:.1%} wall_ms={wall_ms}"
        )

        return result


def main():
    """CLI interface for testing"""
    parser = argparse.ArgumentParser(description="GPT-5 Episode Summary Generator")
    parser.add_argument("--episode-id", required=True, help="Episode ID")
    parser.add_argument("--content-file", required=True, help="Path to content file")
    parser.add_argument("--topic", default="AI News", help="Topic category")
    parser.add_argument("--title", default="", help="Episode title")
    parser.add_argument("--chunksize", type=int, default=2200, help="Chunk size")
    parser.add_argument("--overlap", type=int, default=200, help="Chunk overlap")
    parser.add_argument("--write-json", action="store_true", help="Write JSON output")
    parser.add_argument("--dry-run", action="store_true", help="Mock mode")
    parser.add_argument("--log-level", default="INFO", help="Logging level")

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))

    # Set mock mode if dry run
    if args.dry_run:
        os.environ["MOCK_OPENAI"] = "1"

    # Load content
    content_path = Path(args.content_file)
    if not content_path.exists():
        logger.error(f"Content file not found: {content_path}")
        return 1

    content = content_path.read_text(encoding="utf-8")

    # Initialize generator
    generator = EpisodeSummaryGenerator()
    generator.chunk_size = args.chunksize
    generator.chunk_overlap = args.overlap

    # Generate summary
    result = generator.generate_episode_summary(
        episode_id=args.episode_id, content=content, topic=args.topic, title=args.title
    )

    # Output results
    if args.write_json:
        output_file = f"summary_{args.episode_id}_{args.topic.replace(' ', '_')}.json"
        Path(output_file).write_text(json.dumps(result, indent=2))
        logger.info(f"Summary written to: {output_file}")

    # Print summary
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    exit(main())
