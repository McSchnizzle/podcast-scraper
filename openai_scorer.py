#!/usr/bin/env python3
"""
OpenAI Topic Relevance Scorer
Scores podcast episode transcripts against multiple topics using OpenAI's API
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openai

from utils.datetime_utils import now_utc
from utils.db import get_connection

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
from openai import OpenAI

from utils.logging_setup import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


class OpenAITopicScorer:
    """
    Scores episode transcripts against multiple topics using OpenAI's API
    """

    # Core topic definitions with scoring prompts
    TOPICS = {
        "AI News": {
            "description": "Artificial intelligence developments, AI research, machine learning breakthroughs, AI industry news, AI policy and ethics",
            "prompt": "artificial intelligence, AI news, machine learning, deep learning, AI research, AI breakthroughs, AI industry, AI policy, AI ethics, AI regulation, generative AI, LLMs, AI startups, AI funding",
        },
        "Tech Product Releases": {
            "description": "New technology product launches, hardware releases, software updates, gadget reviews, product announcements",
            "prompt": "product launch, product release, new products, hardware launch, software release, gadget announcement, tech products, product reviews, device launch, tech hardware, consumer electronics",
        },
        "Tech News and Tech Culture": {
            "description": "Technology industry news, tech company developments, tech culture discussions, digital trends, tech policy",
            "prompt": "tech news, technology industry, tech companies, tech culture, digital trends, tech policy, tech regulation, tech industry analysis, tech leadership, tech innovation, startup news",
        },
        "Community Organizing": {
            "description": "Grassroots organizing, community activism, local organizing efforts, civic engagement, community building strategies",
            "prompt": "community organizing, grassroots activism, local organizing, civic engagement, community building, activist organizing, community mobilization, grassroots campaigns, community advocacy, local activism",
        },
        "Social Justice": {
            "description": "Social justice movements, civil rights, equity and inclusion, systemic justice issues, advocacy and activism",
            "prompt": "social justice, civil rights, equity, inclusion, systemic justice, social equity, human rights, justice advocacy, social activism, civil rights movement, racial justice, economic justice",
        },
        "Societal Culture Change": {
            "description": "Cultural shifts, social movements, changing social norms, generational changes, cultural transformation",
            "prompt": "cultural change, social movements, cultural shifts, social transformation, generational change, cultural evolution, social change, cultural trends, societal transformation, cultural movements",
        },
    }

    SCORING_SYSTEM_PROMPT = """You are an expert content analyzer. You will score how relevant a podcast episode transcript is to specific topics.

Your task:
1. Read the episode transcript carefully
2. Score relevance from 0.0 to 1.0 for each topic (0.0 = not relevant at all, 1.0 = highly relevant)
3. Also check for content moderation issues

Scoring Guidelines:
- 0.9-1.0: Extremely relevant, core focus of the episode
- 0.7-0.8: Highly relevant, significant portion discusses this topic
- 0.5-0.6: Moderately relevant, some discussion of this topic
- 0.3-0.4: Minimally relevant, brief mentions
- 0.0-0.2: Not relevant or only tangentially mentioned

Content Moderation:
- Flag content that is: harmful, hateful, violent, sexual, illegal, or promotes dangerous activities
- Use the "moderation_flag" field to indicate issues

Return your analysis as a JSON object with this exact structure:
{
    "AI News": 0.X,
    "Tech Product Releases": 0.X,
    "Tech News and Tech Culture": 0.X,
    "Community Organizing": 0.X,
    "Social Justice": 0.X,
    "Societal Culture Change": 0.X,
    "moderation_flag": false,
    "moderation_reason": null,
    "confidence": 0.X,
    "reasoning": "Brief explanation of scoring rationale"
}"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path

        # Check for mock mode
        self.mock_mode = os.getenv("MOCK_OPENAI") == "1" or os.getenv("CI_SMOKE") == "1"

        if self.mock_mode:
            logger.info("🧪 MOCK MODE: Using mock OpenAI responses")
            self.client = None
            self.api_available = True  # Mock mode is always "available"
        else:
            # Initialize OpenAI client
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY environment variable not set")
                self.client = None
                self.api_available = False
            else:
                try:
                    self.client = OpenAI(api_key=api_key)
                    self.api_available = True
                    logger.info("✅ OpenAI client initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI client: {e}")
                    self.client = None
                    self.api_available = False

    def score_transcript(
        self, transcript_text: str, episode_id: str = None
    ) -> Dict[str, Any]:
        """
        Score a single transcript against all topics
        """
        if not self.api_available:
            logger.error("OpenAI API not available")
            return self._create_fallback_scores()

        # Mock mode - return fixed scores
        if self.mock_mode:
            logger.info(f"🧪 MOCK: Returning mock scores for episode {episode_id}")
            return self._create_mock_scores(transcript_text, episode_id)

        try:
            # Process full transcript - no truncation
            logger.info(
                f"Processing full transcript for episode {episode_id} (length: {len(transcript_text)} chars)"
            )

            user_prompt = f"""Please analyze this podcast episode transcript and score its relevance to each topic:

TRANSCRIPT:
{transcript_text}

TOPICS TO SCORE:
{json.dumps(self.TOPICS, indent=2)}

Provide scores as requested in the system prompt."""

            logger.info(
                f"Sending transcript to OpenAI for scoring (episode: {episode_id})"
            )

            # Use Responses API for GPT-5-mini (recommended for reasoning models)
            response = self.client.responses.create(
                model="gpt-5-mini",  # Cost-effective model for analysis
                input=[
                    {"role": "system", "content": self.SCORING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                reasoning={"effort": "minimal"},  # Low effort for simple scoring task
                max_output_tokens=500,  # Use max_output_tokens for Responses API
                # Responses API uses text format with JSON schema specification
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "EpisodeScores",  # Required name field for Responses API
                        "schema": {
                            "type": "object",
                            "properties": {
                                "AI News": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                },
                                "Tech Product Releases": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                },
                                "Tech News and Tech Culture": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                },
                                "Community Organizing": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                },
                                "Social Justice": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                },
                                "Societal Culture Change": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                },
                                "confidence": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                },
                                "reasoning": {"type": "string"},
                            },
                            "required": [
                                "AI News",
                                "Tech Product Releases",
                                "Tech News and Tech Culture",
                                "Community Organizing",
                                "Social Justice",
                                "Societal Culture Change",
                                "confidence",
                                "reasoning",
                            ],
                            "additionalProperties": False,
                        },
                        "strict": True,
                    }
                },
            )

            # Parse the response using Responses API format
            scores_json = response.output_text.strip()
            logger.info(f"DEBUG: Raw response content: '{scores_json}'")
            logger.info(f"DEBUG: Response length: {len(scores_json)}")

            if not scores_json:
                logger.error(f"Empty response content for episode {episode_id}")
                return None

            scores = json.loads(scores_json)

            # Add metadata
            scores["timestamp"] = now_utc().isoformat()
            scores["model"] = "gpt-5-mini"
            scores["version"] = "1.0"
            scores["episode_id"] = episode_id

            logger.info(f"✅ Successfully scored episode {episode_id}")
            return scores

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse OpenAI response as JSON for episode {episode_id}: {e}"
            )
            return self._create_fallback_scores(episode_id)

        except Exception as e:
            logger.error(f"Error scoring transcript for episode {episode_id}: {e}")
            return self._create_fallback_scores(episode_id)

    def _create_fallback_scores(self, episode_id: str = None) -> Dict[str, Any]:
        """Create neutral fallback scores when API fails"""
        return {
            "AI News": 0.0,
            "Tech Product Releases": 0.0,
            "Tech News and Tech Culture": 0.0,
            "Community Organizing": 0.0,
            "Social Justice": 0.0,
            "Societal Culture Change": 0.0,
            "moderation_flag": False,
            "moderation_reason": None,
            "confidence": 0.0,
            "reasoning": "API unavailable - fallback scores assigned",
            "timestamp": now_utc().isoformat(),
            "model": "fallback",
            "version": "1.0",
            "episode_id": episode_id,
            "error": True,
        }

    def _create_mock_scores(
        self, transcript_text: str, episode_id: str = None
    ) -> Dict[str, Any]:
        """Create realistic mock scores for CI smoke tests"""
        # Create deterministic but realistic scores based on text content
        text_lower = transcript_text.lower()

        # Simple keyword-based scoring for mock mode
        scores = {}
        for topic, config in self.TOPICS.items():
            # Count keyword matches
            keywords = config["prompt"].lower().split(", ")
            matches = sum(1 for keyword in keywords if keyword in text_lower)

            # Convert to score (0.0-1.0) with some randomness for realism
            base_score = min(matches / 5.0, 0.9)  # Cap at 0.9
            # Add small deterministic variation based on episode_id hash
            if episode_id:
                variation = (hash(episode_id + topic) % 20) / 100  # 0-0.19
            else:
                variation = 0.1

            scores[topic] = min(base_score + variation, 1.0)

        return {
            **scores,
            "confidence": 0.8,  # High confidence for mock
            "reasoning": f"Mock scoring based on {len(text_lower)} chars of transcript text",
            "timestamp": now_utc().isoformat(),
            "model": "mock-gpt-5-mini",
            "version": "1.0",
            "episode_id": episode_id,
            "error": False,
        }

    def score_episodes_in_database(
        self, db_path: str, status_filter: str = "transcribed"
    ) -> int:
        """
        Score all episodes with the specified status in a database
        Returns number of episodes scored
        """
        if not os.path.exists(db_path):
            logger.error(f"Database not found: {db_path}")
            return 0

        scored_count = 0

        try:
            conn = get_connection(db_path)
            cursor = conn.cursor()

            # Get episodes that need scoring
            cursor.execute(
                """
                SELECT id, episode_id, title, transcript_path
                FROM episodes
                WHERE status = ? AND transcript_path IS NOT NULL
                AND (topic_relevance_json IS NULL OR topic_relevance_json = '')
                ORDER BY id DESC
            """,
                (status_filter,),
            )

            episodes = cursor.fetchall()
            logger.info(f"Found {len(episodes)} episodes to score in {db_path}")

            for episode_data in episodes:
                db_id, episode_id, title, transcript_path = episode_data

                # Read transcript file
                transcript_file = Path(transcript_path)
                if not transcript_file.exists():
                    logger.warning(f"Transcript file not found: {transcript_path}")
                    continue

                try:
                    with open(transcript_file, "r", encoding="utf-8") as f:
                        transcript_text = f.read()

                    if len(transcript_text.strip()) < 100:
                        logger.warning(
                            f"Transcript too short for episode {episode_id}, skipping"
                        )
                        continue

                    # Score the transcript
                    logger.info(f"Scoring episode: {title[:50]}...")
                    scores = self.score_transcript(transcript_text, episode_id)

                    # Store scores in database
                    cursor.execute(
                        """
                        UPDATE episodes
                        SET topic_relevance_json = ?, scores_version = ?
                        WHERE id = ?
                    """,
                        (json.dumps(scores), scores.get("version", "1.0"), db_id),
                    )

                    conn.commit()
                    scored_count += 1

                    # Rate limiting - pause between requests
                    if scored_count % 5 == 0:
                        logger.info(
                            f"Processed {scored_count} episodes, pausing briefly..."
                        )
                        time.sleep(1)

                except Exception as e:
                    logger.error(f"Error processing episode {episode_id}: {e}")
                    continue

            conn.close()
            logger.info(f"✅ Successfully scored {scored_count} episodes in {db_path}")
            return scored_count

        except Exception as e:
            logger.error(f"Database error in {db_path}: {e}")
            return 0

    def score_pending_in_db(
        self, db_path: str, source: str = "rss", max_to_score: int = None
    ) -> int:
        """
        Score transcribed episodes idempotently with rate limiting and cost guards

        Args:
            db_path: Path to database
            source: Source identifier for logging (rss/youtube)
            max_to_score: Maximum number of episodes to score (cost control)

        Returns:
            Number of episodes successfully scored
        """
        if not os.path.exists(db_path):
            logger.warning(f"Database not found: {db_path}")
            return 0

        if not self.api_available:
            logger.error("OpenAI API not available - cannot score episodes")
            return 0

        # Apply cost control limits
        max_per_run = int(os.getenv("SCORING_MAX_PER_RUN", "50"))
        if max_to_score is None:
            max_to_score = max_per_run
        else:
            max_to_score = min(max_to_score, max_per_run)

        scored_count = 0

        try:
            conn = get_connection(db_path)
            cursor = conn.cursor()

            # Idempotent query - only score episodes that are transcribed and unscored
            cursor.execute(
                """
                SELECT id, episode_id, title, transcript_path
                FROM episodes
                WHERE status = 'transcribed'
                  AND transcript_path IS NOT NULL
                  AND (topic_relevance_json IS NULL OR topic_relevance_json = '' OR topic_relevance_json = '{}')
                ORDER BY id DESC
                LIMIT ?
            """,
                (max_to_score,),
            )

            episodes = cursor.fetchall()

            if not episodes:
                logger.debug(
                    f"No unscored 'transcribed' episodes found in {source} database"
                )
                conn.close()
                return 0

            logger.info(
                f"Found {len(episodes)} unscored episodes in {source} database (limit: {max_to_score})"
            )

            for episode_data in episodes:
                db_id, episode_id, title, transcript_path = episode_data

                # Verify transcript exists and is readable
                transcript_file = Path(transcript_path)
                if not transcript_file.exists():
                    logger.warning(
                        f"Transcript missing: {transcript_path} (episode: {episode_id})"
                    )
                    continue

                try:
                    # Normalize and validate transcript
                    with open(transcript_file, "r", encoding="utf-8") as f:
                        transcript_text = f.read().strip()

                    if len(transcript_text) < 100:
                        logger.debug(f"Transcript too short for scoring: {episode_id}")
                        continue

                    # Score the transcript with OpenAI
                    logger.info(f"Scoring {source} episode: {title[:60]}...")
                    scores = self.score_transcript(transcript_text, episode_id)

                    # Idempotent DB update - only updates if still unscored
                    cursor.execute(
                        """
                        UPDATE episodes
                        SET topic_relevance_json = ?,
                            scores_version = ?,
                            scored_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                          AND status = 'transcribed'
                          AND (topic_relevance_json IS NULL OR topic_relevance_json = '' OR topic_relevance_json = '{}')
                    """,
                        (json.dumps(scores), scores.get("version", "1.0"), db_id),
                    )

                    if cursor.rowcount > 0:
                        scored_count += 1
                        logger.debug(
                            f"✅ Scored episode {episode_id} (total: {scored_count})"
                        )
                    else:
                        logger.debug(
                            f"Episode {episode_id} was already scored by another process"
                        )

                    conn.commit()

                    # Rate limiting to respect API limits
                    if scored_count % 5 == 0 and scored_count > 0:
                        base_delay = float(os.getenv("API_RATE_LIMIT_DELAY", "1.0"))
                        time.sleep(base_delay)

                except Exception as e:
                    logger.error(f"Error scoring episode {episode_id}: {e}")
                    # Continue with next episode on individual failures
                    continue

            conn.close()

            if scored_count > 0:
                logger.info(f"✅ Successfully scored {scored_count} {source} episodes")
            else:
                logger.info(f"No new {source} episodes needed scoring")

            return scored_count

        except Exception as e:
            logger.error(f"Critical error in score_pending_in_db for {db_path}: {e}")
            return 0

    def get_episode_scores(
        self, db_path: str, episode_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get topic scores for episodes from database
        """
        if not os.path.exists(db_path):
            logger.error(f"Database not found: {db_path}")
            return []

        try:
            conn = get_connection(db_path)
            cursor = conn.cursor()

            if episode_id:
                cursor.execute(
                    """
                    SELECT episode_id, title, topic_relevance_json, status
                    FROM episodes
                    WHERE episode_id = ?
                """,
                    (episode_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT episode_id, title, topic_relevance_json, status
                    FROM episodes
                    WHERE topic_relevance_json IS NOT NULL AND topic_relevance_json != ''
                    ORDER BY id DESC
                """
                )

            results = []
            for row in cursor.fetchall():
                ep_id, title, scores_json, status = row
                try:
                    scores = json.loads(scores_json) if scores_json else {}
                    results.append(
                        {
                            "episode_id": ep_id,
                            "title": title,
                            "status": status,
                            "scores": scores,
                        }
                    )
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in scores for episode {ep_id}")
                    continue

            conn.close()
            return results

        except Exception as e:
            logger.error(f"Error retrieving scores from {db_path}: {e}")
            return []


# Standalone functions for pipeline integration
def score_pending_in_db(
    db_path: str, source: str = "rss", max_to_score: int = None
) -> int:
    """
    Standalone function to score pending transcribed episodes
    Used by daily_podcast_pipeline.py for post-transcription scoring
    """
    scorer = OpenAITopicScorer()
    return scorer.score_pending_in_db(db_path, source, max_to_score)


def run_backfill_scoring(
    rss_db: str = "podcast_monitor.db", youtube_db: str = "youtube_transcripts.db"
) -> Tuple[int, int]:
    """
    Backfill scoring for any missed episodes across both databases
    Returns (rss_scored, youtube_scored)
    """
    scorer = OpenAITopicScorer()

    rss_scored = 0
    youtube_scored = 0

    if Path(rss_db).exists():
        rss_scored = scorer.score_pending_in_db(rss_db, source="rss", max_to_score=200)

    if Path(youtube_db).exists():
        youtube_scored = scorer.score_pending_in_db(
            youtube_db, source="youtube", max_to_score=200
        )

    logger.info(
        f"Backfill scoring complete: RSS={rss_scored}, YouTube={youtube_scored}"
    )
    return rss_scored, youtube_scored


def main():
    """CLI interface for the OpenAI scorer"""
    import argparse

    parser = argparse.ArgumentParser(description="Score podcast episodes using OpenAI")
    parser.add_argument("--db", type=str, help="Database path")
    parser.add_argument(
        "--score-all", action="store_true", help="Score all unscored episodes"
    )
    parser.add_argument(
        "--view-scores", action="store_true", help="View existing scores"
    )
    parser.add_argument("--episode-id", type=str, help="Score specific episode")

    args = parser.parse_args()

    scorer = OpenAITopicScorer()

    if not scorer.api_available:
        print("❌ OpenAI API not available. Set OPENAI_API_KEY environment variable.")
        return

    if args.score_all:
        databases = ["podcast_monitor.db", "youtube_transcripts.db"]
        total_scored = 0
        for db_path in databases:
            if os.path.exists(db_path):
                scored = scorer.score_episodes_in_database(db_path)
                total_scored += scored
                print(f"Scored {scored} episodes in {db_path}")
        print(f"\n✅ Total episodes scored: {total_scored}")

    elif args.view_scores:
        databases = ["podcast_monitor.db", "youtube_transcripts.db"]
        for db_path in databases:
            if os.path.exists(db_path):
                scores = scorer.get_episode_scores(db_path)
                print(f"\n{db_path} - {len(scores)} episodes with scores:")
                for episode in scores[:5]:  # Show first 5
                    print(f"  {episode['episode_id']}: {episode['title'][:50]}")
                    top_topics = sorted(
                        episode["scores"].items(),
                        key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0,
                        reverse=True,
                    )[:2]
                    for topic, score in top_topics:
                        if isinstance(score, (int, float)) and score > 0.3:
                            print(f"    {topic}: {score:.2f}")

    elif args.episode_id and args.db:
        scores = scorer.get_episode_scores(args.db, args.episode_id)
        if scores:
            episode = scores[0]
            print(f"Episode: {episode['title']}")
            print(f"Status: {episode['status']}")
            print("Topic Scores:")
            for topic, score in episode["scores"].items():
                if isinstance(score, (int, float)):
                    print(f"  {topic}: {score:.2f}")
        else:
            print(f"Episode {args.episode_id} not found or not scored")

    else:
        print("Use --score-all to score episodes or --view-scores to see results")
        print("Example: python openai_scorer.py --score-all")


# Conditional backward compatibility
import os

if os.getenv("ALLOW_LEGACY_OPENAI_SCORER_ALIAS", "").lower() == "true":
    OpenAIScorer = OpenAITopicScorer
    OpenAIRelevanceScorer = OpenAITopicScorer
    __all__ = [
        "OpenAITopicScorer",
        "OpenAIScorer",
        "OpenAIRelevanceScorer",
        "score_pending_in_db",
        "run_backfill_scoring",
    ]
else:
    __all__ = ["OpenAITopicScorer", "score_pending_in_db", "run_backfill_scoring"]


if __name__ == "__main__":
    main()
