#!/usr/bin/env python3
"""
OpenAI Digest Integration - Multi-Topic Digest Generator
Uses configurable models for digest generation with cost-effective models for scoring/validation
"""

import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import openai

from utils.datetime_utils import now_utc
from utils.db import get_connection

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
from config import config
from episode_summary_generator import EpisodeSummaryGenerator
from prose_validator import ProseValidator
from telemetry_manager import telemetry
from utils.logging_setup import configure_logging
from utils.openai_helpers import (
    call_openai_with_backoff,
    generate_idempotency_key,
    get_json_schema,
)
from utils.sanitization import safe_digest_filename, scrub_secrets_from_text

configure_logging()
logger = logging.getLogger(__name__)


def approx_tokens(text: str) -> int:
    """Estimate token count using simple heuristic"""
    return (len(text) + 3) // 4


class OpenAIDigestIntegration:
    def __init__(
        self, db_path: str = "podcast_monitor.db", transcripts_dir: str = "transcripts"
    ):
        self.db_path = db_path
        self.transcripts_dir = Path(transcripts_dir)

        # Initialize prose validator and episode summary generator
        self.prose_validator = ProseValidator()
        self.summary_generator = EpisodeSummaryGenerator()

        # GPT-5 configuration
        self.model = config.GPT5_MODELS["digest"]
        self.max_output_tokens = config.OPENAI_TOKENS["digest"]
        self.reasoning_effort = config.REASONING_EFFORT["digest"]
        self.feature_enabled = config.FEATURE_FLAGS["use_gpt5_digest"]

        # Check for mock mode
        self.mock_mode = os.getenv("MOCK_OPENAI") == "1" or os.getenv("CI_SMOKE") == "1"

        if self.mock_mode:
            logger.info("🧪 MOCK MODE: Using mock OpenAI responses for digest")
            self.client = None
            self.api_available = True
        else:
            # Initialize OpenAI client
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY environment variable not set")
                self.client = None
                self.api_available = False
            elif len(api_key.strip()) < 10:
                logger.error(
                    f"OPENAI_API_KEY appears invalid (length: {len(api_key.strip())})"
                )
                self.client = None
                self.api_available = False
            else:
                try:
                    from openai import OpenAI

                    self.client = OpenAI(api_key=api_key.strip())
                    self.api_available = True
                    logger.info(
                        f"✅ OpenAI Digest Integration initialized with {self.model}"
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI client: {e}")
                    self.client = None
                    self.api_available = False

        # Log configuration on startup
        logger.info(
            f"component=digest model={self.model} max_output_tokens={self.max_output_tokens} "
            f"reasoning={self.reasoning_effort} feature_enabled={self.feature_enabled}"
        )

    def get_transcripts_for_analysis(
        self, include_youtube: bool = True, topic: str = None, threshold: float = 0.6
    ) -> List[Dict]:
        """Get transcripts ready for API analysis from both databases, filtered by topic relevance scores"""
        transcripts = []

        # Get RSS transcripts from main database
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()

            # Updated query to use relevance scores instead of digest_topic
            if topic:
                query = """
                SELECT id, title, transcript_path, episode_id, published_date, status, topic_relevance_json
                FROM episodes
                WHERE transcript_path IS NOT NULL
                AND status = 'transcribed'
                AND topic_relevance_json IS NOT NULL
                AND topic_relevance_json != ''
                ORDER BY published_date DESC
                """
                cursor.execute(query)
            else:
                query = """
                SELECT id, title, transcript_path, episode_id, published_date, status, topic_relevance_json
                FROM episodes
                WHERE transcript_path IS NOT NULL
                AND status = 'transcribed'
                AND topic_relevance_json IS NOT NULL
                AND topic_relevance_json != ''
                ORDER BY published_date DESC
                """
                cursor.execute(query)

            rss_episodes = cursor.fetchall()
            conn.close()

            for (
                episode_id,
                title,
                transcript_path,
                ep_id,
                published_date,
                status,
                topic_relevance_json,
            ) in rss_episodes:
                transcript_file = Path(transcript_path)

                if transcript_file.exists():
                    try:
                        with open(transcript_file, "r", encoding="utf-8") as f:
                            content = f.read().strip()

                        # Parse topic relevance scores
                        try:
                            scores = (
                                json.loads(topic_relevance_json)
                                if topic_relevance_json
                                else {}
                            )
                        except (json.JSONDecodeError, TypeError):
                            logger.warning(f"Invalid topic scores for episode {ep_id}")
                            scores = {}

                        # Filter by topic relevance if specific topic requested
                        if topic:
                            topic_score = scores.get(topic, 0.0)
                            if topic_score < threshold:
                                continue  # Skip episodes below threshold
                        else:
                            # For general query, check if any topic exceeds threshold
                            max_score = max(
                                (
                                    score
                                    for score in scores.values()
                                    if isinstance(score, (int, float))
                                ),
                                default=0.0,
                            )
                            if max_score < threshold:
                                continue

                        if content:
                            transcripts.append(
                                {
                                    "id": episode_id,
                                    "title": title,
                                    "episode_id": ep_id,
                                    "published_date": published_date,
                                    "transcript_path": str(transcript_path),
                                    "content": content[:50000],  # Limit content for API
                                    "source": "rss",
                                    "topic_scores": scores,
                                }
                            )
                    except Exception as e:
                        logger.error(
                            f"Error reading RSS transcript {transcript_path}: {e}"
                        )

            logger.info(f"Found {len(transcripts)} RSS transcripts")

        except Exception as e:
            logger.error(f"Error getting RSS transcripts: {e}")

        # Get YouTube transcripts from YouTube database
        if include_youtube:
            try:
                youtube_db_path = "youtube_transcripts.db"
                if Path(youtube_db_path).exists():
                    conn = get_connection(youtube_db_path)
                    cursor = conn.cursor()

                    # Use the same query logic for YouTube database
                    cursor.execute(query)
                    youtube_episodes = cursor.fetchall()
                    conn.close()

                    youtube_count = 0
                    for (
                        episode_id,
                        title,
                        transcript_path,
                        ep_id,
                        published_date,
                        status,
                        topic_relevance_json,
                    ) in youtube_episodes:
                        transcript_file = Path(transcript_path)

                        if transcript_file.exists():
                            try:
                                with open(transcript_file, "r", encoding="utf-8") as f:
                                    content = f.read().strip()

                                # Parse topic relevance scores
                                try:
                                    scores = (
                                        json.loads(topic_relevance_json)
                                        if topic_relevance_json
                                        else {}
                                    )
                                except (json.JSONDecodeError, TypeError):
                                    logger.warning(
                                        f"Invalid topic scores for YouTube episode {ep_id}"
                                    )
                                    scores = {}

                                # Filter by topic relevance if specific topic requested
                                if topic:
                                    topic_score = scores.get(topic, 0.0)
                                    if topic_score < threshold:
                                        continue  # Skip episodes below threshold
                                else:
                                    # For general query, check if any topic exceeds threshold
                                    max_score = max(
                                        (
                                            score
                                            for score in scores.values()
                                            if isinstance(score, (int, float))
                                        ),
                                        default=0.0,
                                    )
                                    if max_score < threshold:
                                        continue

                                if content:
                                    transcripts.append(
                                        {
                                            "id": f"yt_{episode_id}",  # Prefix to avoid ID conflicts
                                            "title": title,
                                            "episode_id": ep_id,
                                            "published_date": published_date,
                                            "transcript_path": str(transcript_path),
                                            "content": content[:50000],
                                            "source": "youtube",
                                            "topic_scores": scores,
                                        }
                                    )
                                    youtube_count += 1
                            except Exception as e:
                                logger.error(
                                    f"Error reading YouTube transcript {transcript_path}: {e}"
                                )

                    logger.info(f"Found {youtube_count} YouTube transcripts")
                else:
                    logger.info("No YouTube database found - RSS only")

            except Exception as e:
                logger.error(f"Error getting YouTube transcripts: {e}")

        # Sort combined transcripts by date
        transcripts.sort(key=lambda x: x["published_date"], reverse=True)
        logger.info(f"Total transcripts for analysis: {len(transcripts)}")

        return transcripts

    def prepare_digest_prompt(self, transcripts: List[Dict], topic: str = None) -> str:
        """Prepare topic-specific digest prompt for OpenAI GPT-4"""

        transcript_summaries = []
        for transcript in transcripts:
            summary = f"""
## {transcript['title']} ({transcript['published_date']})
{transcript['content']}
"""
            transcript_summaries.append(summary)

        combined_content = "\n".join(transcript_summaries)

        # Load topic-specific instructions from files
        instructions_path = Path("digest_instructions") / f"{topic}.md"
        if topic and instructions_path.exists():
            try:
                with open(instructions_path, "r", encoding="utf-8") as f:
                    instructions_content = f.read()

                # Extract the key sections from instructions for prompt
                focus_match = re.search(
                    r"## Topic Focus\n(.+?)(?=\n##|$)", instructions_content, re.DOTALL
                )
                focus_area = (
                    focus_match.group(1).strip() if focus_match else f"{topic} topics"
                )

                structure_match = re.search(
                    r"## Content Structure\n(.+?)(?=\n## Style Guidelines|$)",
                    instructions_content,
                    re.DOTALL,
                )
                structure_content = (
                    structure_match.group(1).strip() if structure_match else ""
                )

                # Load topic config for display info
                topics_config_path = Path("topics.json")
                if topics_config_path.exists():
                    try:
                        with open(topics_config_path, "r", encoding="utf-8") as f:
                            topics_config = json.load(f)
                        topic_info = topics_config.get(topic, {})
                        title = f"{topic_info.get('display_name', topic)} - {now_utc().strftime('%B %d, %Y')}"
                    except (json.JSONDecodeError, Exception) as e:
                        logger.warning(f"Could not load topics config: {e}")
                        title = f"{topic} - {now_utc().strftime('%B %d, %Y')}"
                else:
                    title = f"{topic} - {now_utc().strftime('%B %d, %Y')}"

            except Exception as e:
                logger.warning(f"Could not load instructions for {topic}: {e}")
                # Fallback to embedded instructions
                return self._prepare_fallback_prompt(
                    transcripts, topic, combined_content
                )
        else:
            # Fallback to embedded instructions
            return self._prepare_fallback_prompt(transcripts, topic, combined_content)

        prompt = f"""You are an expert analyst creating a focused digest from podcast transcripts.

Please analyze the following {len(transcripts)} podcast transcripts and create a structured digest following these specific instructions:

TOPIC FOCUS:
{focus_area}

TRANSCRIPT CONTENT:
{combined_content}

CONTENT STRUCTURE TO FOLLOW:
{structure_content}

Create a comprehensive digest with the title: {title}

Follow the content structure provided above exactly, maintaining the same section headers and focus areas. Ensure the content is formatted as clean Markdown suitable for publication and TTS generation (avoid bullet points, use prose format).

Focus on accuracy, insight, and connecting information specifically related to the topic focus area."""

        return prompt

    def _prepare_fallback_prompt(
        self, transcripts: List[Dict], topic: str, combined_content: str
    ) -> str:
        """Fallback to embedded prompts when files are not available"""
        # Topic-specific prompts with focused analysis - same structure as before
        topic_descriptions = {
            "AI News": {
                "title": "AI News Digest",
                "focus": "artificial intelligence developments, machine learning breakthroughs, AI product launches, research updates, industry announcements",
                "sections": [
                    "### 🤖 AI Model Releases & Updates",
                    "### 🔬 Research Breakthroughs",
                    "### 🏢 Industry Developments",
                    "### 🛠️ Developer Tools & Platforms",
                    "### 📈 Market Impact & Analysis",
                ],
            },
            "Tech Product Releases": {
                "title": "Tech Product Releases Digest",
                "focus": "new technology product launches, hardware releases, software updates, gadget reviews, product announcements",
                "sections": [
                    "### 📱 Consumer Electronics",
                    "### 💻 Computing & Hardware",
                    "### 🎮 Gaming & Entertainment",
                    "### 🏠 Smart Home & IoT",
                    "### 🚗 Automotive Tech",
                ],
            },
            "Tech News and Tech Culture": {
                "title": "Tech News & Culture Digest",
                "focus": "technology industry news, tech company developments, tech culture discussions, digital trends, tech policy",
                "sections": [
                    "### 📰 Industry News",
                    "### 🏛️ Policy & Regulation",
                    "### 🌐 Digital Culture & Trends",
                    "### 💼 Business & Leadership",
                    "### 🔮 Future Outlook",
                ],
            },
            "Community Organizing": {
                "title": "Community Organizing Digest",
                "focus": "grassroots organizing, community activism, local organizing efforts, civic engagement, community building strategies",
                "sections": [
                    "### 🤝 Grassroots Campaigns",
                    "### 🗳️ Civic Engagement",
                    "### 🏘️ Community Building",
                    "### 📢 Advocacy Strategies",
                    "### 🌱 Local Impact Stories",
                ],
            },
            "Social Justice": {
                "title": "Social Justice Digest",
                "focus": "social justice movements, civil rights, equity and inclusion, systemic justice issues, advocacy and activism",
                "sections": [
                    "### ⚖️ Civil Rights Updates",
                    "### 🌈 Equity & Inclusion",
                    "### 📊 Systemic Change",
                    "### 🔊 Advocacy Highlights",
                    "### 💪 Movement Building",
                ],
            },
            "Societal Culture Change": {
                "title": "Societal Culture Change Digest",
                "focus": "cultural shifts, social movements, changing social norms, generational changes, cultural transformation",
                "sections": [
                    "### 🌊 Cultural Shifts",
                    "### 👥 Generational Changes",
                    "### 🔄 Social Transformation",
                    "### 📱 Digital Culture Impact",
                    "### 🌍 Global Perspectives",
                ],
            },
        }

        # Get topic info or use generic if not specified
        if topic and topic in topic_descriptions:
            topic_info = topic_descriptions[topic]
            title = topic_info["title"]
            focus_area = topic_info["focus"]
            sections = "\n".join(topic_info["sections"])
        else:
            title = "Daily Tech Digest"
            focus_area = "technology and innovation developments"
            sections = """### 🤖 AI & Machine Learning
### 📱 Consumer Tech
### 💼 Business & Industry
### 🔒 Security & Privacy
### 🛠️ Open Source & Development"""

        prompt = f"""You are an expert analyst creating a focused digest from podcast transcripts.

Please analyze the following {len(transcripts)} podcast transcripts focused on {focus_area} and create a structured digest:

{combined_content}

Create a comprehensive digest with the following structure:

# {title} - {now_utc().strftime('%B %d, %Y')}

## 🌟 Key Highlights
- List the 3-5 most important developments from these episodes
- Focus specifically on {focus_area}
- Include brief explanations of significance

## 📊 Detailed Analysis

{sections}

## 💡 Insights & Connections
- Provide 2-3 deeper insights connecting themes across episodes
- Identify emerging trends or patterns within {focus_area}
- Highlight unique perspectives or expert opinions

## 🔗 Cross-References & Context
- Note when multiple episodes discuss the same topic
- Connect developments to broader industry/social trends
- Highlight different viewpoints or approaches

## 🎯 Actionable Takeaways
- What should listeners know or do based on these insights?
- Key questions or areas to watch
- Implications for the future

Format the output as clean Markdown suitable for publication. Focus on accuracy, insight, and connecting information specifically related to {focus_area}."""

        return prompt

    def get_available_topics(self, threshold: float = 0.6) -> List[str]:
        """Get list of topics that have episodes ready for digest based on relevance scores"""
        topics_with_episodes = set()

        # Define available topics (from OpenAI scorer)
        all_topics = [
            "AI News",
            "Tech Product Releases",
            "Tech News and Tech Culture",
            "Community Organizing",
            "Social Justice",
            "Societal Culture Change",
        ]

        # Check RSS database
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT topic_relevance_json
                FROM episodes
                WHERE topic_relevance_json IS NOT NULL
                AND topic_relevance_json != ''
                AND status = 'transcribed'
                AND transcript_path IS NOT NULL
            """
            )

            for (scores_json,) in cursor.fetchall():
                try:
                    scores = json.loads(scores_json)
                    for topic in all_topics:
                        if scores.get(topic, 0.0) >= threshold:
                            topics_with_episodes.add(topic)
                except (json.JSONDecodeError, TypeError):
                    continue
            conn.close()
        except Exception as e:
            logger.error(f"Error getting RSS topics: {e}")

        # Check YouTube database
        try:
            youtube_db_path = "youtube_transcripts.db"
            if Path(youtube_db_path).exists():
                conn = get_connection(youtube_db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT topic_relevance_json
                    FROM episodes
                    WHERE topic_relevance_json IS NOT NULL
                    AND topic_relevance_json != ''
                    AND status = 'transcribed'
                    AND transcript_path IS NOT NULL
                """
                )

                for (scores_json,) in cursor.fetchall():
                    try:
                        scores = json.loads(scores_json)
                        for topic in all_topics:
                            if scores.get(topic, 0.0) >= threshold:
                                topics_with_episodes.add(topic)
                    except (json.JSONDecodeError, TypeError):
                        continue
                conn.close()
        except Exception as e:
            logger.error(f"Error getting YouTube topics: {e}")

        return sorted(list(topics_with_episodes))

    def generate_topic_digest(
        self, topic: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Generate digest for a specific topic using map-reduce approach with OpenAI models"""

        logger.info(f"🧠 Starting {topic} digest generation with OpenAI (map-reduce)")
        start_time = time.time()
        retry_count = 0

        if not self.api_available:
            logger.error("OpenAI API not available - cannot generate digest")
            telemetry.record_error(f"OpenAI API not available for {topic}")
            return False, None, None

        # Get all transcripts and use map-reduce approach
        all_transcripts = self.get_transcripts_for_analysis(include_youtube=True)
        if not all_transcripts:
            logger.warning(f"No transcripts available for any topics")
            telemetry.record_warning(f"No transcripts available for {topic}")
            return False, None, None

        logger.info(
            f"📊 Starting map-reduce for {topic} with {len(all_transcripts)} total transcripts"
        )

        # Filter by topic relevance for telemetry
        threshold = config.OPENAI_SETTINGS["relevance_threshold"]
        topic_relevant = [
            t
            for t in all_transcripts
            if t.get("topic_scores", {}).get(topic, 0.0) >= threshold
        ]

        try:
            # MAP PHASE: Generate episode summaries using cost-effective model
            episode_summaries = self.summary_generator.generate_topic_summaries(
                all_transcripts, topic
            )

            if not episode_summaries:
                logger.warning(f"No relevant episodes found for topic: {topic}")
                return False, None, f"No episodes meet relevance threshold for {topic}"

            # Check token budget for REDUCE phase
            total_summary_tokens = sum(s["tokens"] for s in episode_summaries)
            max_reduce_tokens = config.OPENAI_SETTINGS["max_reduce_tokens"]

            logger.info(
                f"Map phase complete: {len(episode_summaries)} summaries, {total_summary_tokens} tokens"
            )

            # Progressive token reduction if needed
            if (
                total_summary_tokens > max_reduce_tokens * 0.8
            ):  # Leave room for system prompt
                logger.warning(
                    f"Token budget tight ({total_summary_tokens} > {int(max_reduce_tokens * 0.8)}), reducing episodes"
                )
                # Drop lowest-scored episodes until we fit
                episode_summaries.sort(key=lambda x: x["topic_score"], reverse=True)
                while (
                    total_summary_tokens > max_reduce_tokens * 0.8
                    and len(episode_summaries) > 2
                ):
                    removed = episode_summaries.pop()
                    total_summary_tokens -= removed["tokens"]
                    logger.info(
                        f"Dropped episode {removed['episode_id']} (score: {removed['topic_score']:.3f})"
                    )

            # REDUCE PHASE: Generate final digest using primary model
            digest_content = self._generate_final_digest(episode_summaries, topic)

            if not digest_content:
                logger.error(f"Failed to generate final digest for {topic}")
                return False, None, "Digest generation failed in reduce phase"

            # Validate and ensure prose quality
            logger.info(f"🔍 Validating prose quality for {topic} digest")
            success, final_content, issues = self.prose_validator.ensure_prose_quality(
                digest_content
            )

            if not success:
                logger.error(
                    f"❌ Failed to create valid prose for {topic} digest: {', '.join(issues)}"
                )
                return False, None, f"Prose validation failed: {', '.join(issues)}"

            if final_content != digest_content:
                logger.info(f"✅ {topic} digest was rewritten to improve prose quality")
            else:
                logger.info(f"✅ {topic} digest already had good prose quality")

            # Save topic-specific digest
            timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
            digest_filename = safe_digest_filename(topic, timestamp)
            digest_path = Path("daily_digests") / digest_filename
            digest_path.parent.mkdir(exist_ok=True)

            with open(digest_path, "w", encoding="utf-8") as f:
                f.write(final_content)

            logger.info(f"✅ {topic} digest saved to {digest_path}")

            # Update databases - mark episodes as digested and stamp with topic/date
            episode_ids = [s["episode_id"] for s in episode_summaries]
            self._mark_episodes_as_digested_by_ids(episode_ids, topic, timestamp)

            # Move transcripts to digested folder
            transcript_paths = [
                Path(s.get("transcript_path", ""))
                for s in episode_summaries
                if s.get("transcript_path")
            ]
            self._move_transcripts_to_digested_by_paths(transcript_paths)

            # Save map summaries for telemetry retention
            for summary in episode_summaries:
                telemetry.save_map_summary(
                    episode_id=summary["episode_id"],
                    topic=topic,
                    summary_content=summary["summary"],
                    token_count=summary["tokens"],
                )

            # Record telemetry for successful processing
            processing_time = time.time() - start_time

            # Track dropped episode IDs (if any were removed during budget trimming)
            all_selected_ids = {s["episode_id"] for s in episode_summaries}
            all_relevant_ids = {t["episode_id"] for t in topic_relevant}
            dropped_ids = list(all_relevant_ids - all_selected_ids)

            telemetry.record_topic_processing(
                topic=topic,
                total_candidates=len(all_transcripts),
                above_threshold_count=len(topic_relevant),
                selected_count=len(episode_summaries),
                threshold_used=threshold,
                map_phase_tokens=sum(s["tokens"] for s in episode_summaries),
                reduce_phase_tokens=len(final_content.split())
                * 4,  # Estimate output tokens
                retry_count=retry_count,
                processing_time=processing_time,
                episode_ids_included=episode_ids,
                episode_ids_dropped=dropped_ids,
                success=True,
            )

            return True, str(digest_path), None

        except Exception as e:
            logger.error(f"Error generating {topic} digest with OpenAI: {e}")

            # Record telemetry for failed processing
            processing_time = time.time() - start_time
            telemetry.record_topic_processing(
                topic=topic,
                total_candidates=len(all_transcripts),
                above_threshold_count=len(topic_relevant),
                selected_count=0,
                threshold_used=threshold,
                map_phase_tokens=0,
                reduce_phase_tokens=0,
                retry_count=retry_count,
                processing_time=processing_time,
                episode_ids_included=[],
                episode_ids_dropped=[],
                success=False,
                error_message=str(e),
            )

            return False, None, str(e)

    def _generate_final_digest(
        self, episode_summaries: List[Dict], topic: str
    ) -> Optional[str]:
        """Generate final digest using primary model (Reduce phase)"""
        if not episode_summaries:
            return None

        topic_info = config.OPENAI_SETTINGS["topics"].get(topic, {})
        topic_description = topic_info.get("description", topic)

        # Build system prompt with prose-only requirement
        system_prompt = f"""You are an expert podcast writer. Produce a single, flowing spoken script.

Absolutely no bullet points, no numbered lists, no markdown, no headings.
Keep it conversational and coherent. Include short, attributed quotes only if instructed.
Honor the topic's structure and voice.

Topic Focus: {topic_description}

Create a comprehensive digest that synthesizes insights across episodes.
Connect themes, highlight key developments, and provide actionable insights.
Write for an intelligent audience interested in {topic}.
Aim for 2000-3000 words in flowing, conversational prose."""

        # Build user prompt with episode summaries
        summaries_text = []
        for i, summary in enumerate(episode_summaries, 1):
            summaries_text.append(
                f"Episode {i}: {summary['title']} ({summary['source']}, score: {summary['topic_score']:.3f})\n"
                f"{summary['summary']}\n"
            )

        user_prompt = f"""Generate a comprehensive {topic} digest from these episode summaries:

{chr(10).join(summaries_text)}

Create a flowing, conversational digest that synthesizes these insights."""

        # Estimate tokens for logging
        total_tokens = approx_tokens(system_prompt + user_prompt)
        logger.info(f"Reduce phase prompt: {total_tokens} tokens")

        try:
            # Check if feature is enabled
            if not self.feature_enabled:
                logger.warning("GPT-5 digest generation disabled by feature flag")
                return False, None, "Feature disabled"

            # Mock mode handling
            if self.mock_mode:
                logger.info("🧪 MOCK: Generating mock digest")
                mock_digest = self._generate_mock_digest(topic, episode_summaries)
                return True, mock_digest, None

            # Generate run ID for idempotency and observability
            run_id = generate_idempotency_key(topic, str(now_utc()), self.model)

            # Call GPT-5 via Responses API with structured output
            logger.info(
                f"🤖 Generating digest: {topic} ({len(episode_summaries)} summaries, ~{approx_tokens(user_prompt)} tokens)"
            )

            result = call_openai_with_backoff(
                client=self.client,
                component="digest",
                run_id=run_id,
                idempotency_key=run_id,
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                reasoning={"effort": self.reasoning_effort},
                max_output_tokens=self.max_output_tokens,
                text={"format": get_json_schema("digest")},
            )

            # Parse structured response
            digest_data = result.to_json()

            # Check if digest meets quality standards
            status = digest_data.get("status", "OK")
            if status == "PARTIAL":
                logger.warning(f"⚠️ Digest marked as PARTIAL quality for {topic}")

            # Extract digest content (assuming it's in the items field)
            items = digest_data.get("items", [])
            if not items:
                logger.error(f"❌ No digest items generated for {topic}")
                return False, None, "No digest items generated"

            # Format the digest content from structured data
            digest_content = self._format_digest_from_structured_data(
                topic, digest_data
            )

            logger.info(
                f"✅ Generated final digest for {topic}: {len(items)} items, {approx_tokens(digest_content)} tokens"
            )
            return digest_content

        except Exception as e:
            logger.error(f"Failed to generate final digest for {topic}: {e}")

            # Write error artifact
            error_filename = f"{topic.lower().replace(' ', '_')}_digest_ERROR.md"
            error_path = Path("daily_digests") / error_filename
            with open(error_path, "w") as f:
                f.write(f"# ERROR generating {topic} digest\n\n")
                f.write(f"Error: {e}\n\n")
                f.write(f"Token estimate: {total_tokens}\n")
                f.write(f"Episodes included: {len(episode_summaries)}\n\n")
                for summary in episode_summaries:
                    f.write(
                        f"- {summary.get('episode_id', 'unknown')}: {summary.get('title', 'No title')}\n"
                    )

            logger.error(f"Error artifact saved to {error_path}")
            return None

    def _mark_episodes_as_digested_by_ids(
        self, episode_ids: List[str], topic: str, timestamp: str
    ):
        """Mark episodes as digested in both databases"""
        # Mark in RSS database
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            for episode_id in episode_ids:
                if not episode_id.startswith("yt_"):  # RSS episode
                    cursor.execute(
                        """
                        UPDATE episodes
                        SET status = 'digested', digest_topic = ?, digest_date = ?
                        WHERE episode_id = ?
                    """,
                        (topic, timestamp, episode_id),
                    )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error marking RSS episodes as digested: {e}")

        # Mark in YouTube database
        try:
            youtube_db_path = "youtube_transcripts.db"
            if Path(youtube_db_path).exists():
                conn = get_connection(youtube_db_path)
                cursor = conn.cursor()
                for episode_id in episode_ids:
                    if episode_id.startswith("yt_"):  # YouTube episode
                        actual_id = episode_id[3:]  # Remove 'yt_' prefix
                        cursor.execute(
                            """
                            UPDATE episodes
                            SET status = 'digested', digest_topic = ?, digest_date = ?
                            WHERE episode_id = ?
                        """,
                            (topic, timestamp, actual_id),
                        )
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"Error marking YouTube episodes as digested: {e}")

    def _move_transcripts_to_digested_by_paths(self, transcript_paths: List[Path]):
        """Move transcript files to digested directory"""
        digested_dir = Path("transcripts/digested")
        digested_dir.mkdir(parents=True, exist_ok=True)

        for transcript_path in transcript_paths:
            if transcript_path.exists():
                try:
                    target_path = digested_dir / transcript_path.name
                    transcript_path.rename(target_path)
                    logger.debug(f"Moved {transcript_path} to {target_path}")
                except Exception as e:
                    logger.error(f"Error moving transcript {transcript_path}: {e}")

    def generate_all_topic_digests(
        self,
    ) -> Dict[str, Tuple[bool, Optional[str], Optional[str]]]:
        """Generate digests for all available topics"""

        available_topics = self.get_available_topics()
        if not available_topics:
            logger.warning("No topics with episodes ready for digest")
            return {}

        logger.info(
            f"🚀 Starting multi-topic digest generation for {len(available_topics)} topics"
        )
        logger.info(f"Topics: {', '.join(available_topics)}")

        results = {}
        for topic in available_topics:
            logger.info(f"\n📝 Processing topic: {topic}")
            result = self.generate_topic_digest(topic)
            results[topic] = result

            success, path, error = result
            if success:
                logger.info(f"✅ {topic} digest completed: {path}")
            else:
                logger.error(f"❌ {topic} digest failed: {error}")

        # Summary
        successful = sum(1 for _, (success, _, _) in results.items() if success)
        logger.info(
            f"\n🏁 Multi-topic digest generation complete: {successful}/{len(available_topics)} topics successful"
        )

        return results

    def generate_digest(
        self, topic: str = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Generate digest using OpenAI GPT-4 - supports single topic or all topics"""

        if topic:
            # Generate single topic digest
            logger.info(f"🧠 Starting single topic digest generation: {topic}")
            return self.generate_topic_digest(topic)
        else:
            # Generate all topic digests (new default behavior)
            logger.info("🧠 Starting multi-topic digest generation")
            results = self.generate_all_topic_digests()

            if not results:
                logger.error("No topics available for digest generation")
                return False, None, "No topics with episodes ready for digest"

            # Check if any digests were successful
            successful_digests = []
            failed_digests = []

            for topic, (success, path, error) in results.items():
                if success:
                    successful_digests.append((topic, path))
                else:
                    failed_digests.append((topic, error))

            if successful_digests:
                # Return success with summary of all generated digests
                digest_list = [f"{topic}: {path}" for topic, path in successful_digests]
                summary = (
                    f"Generated {len(successful_digests)} topic digests:\n"
                    + "\n".join(digest_list)
                )

                if failed_digests:
                    failed_list = [
                        f"{topic}: {error or 'Unknown error'}"
                        for topic, error in failed_digests
                    ]
                    summary += (
                        f"\n\nFailed {len(failed_digests)} digests:\n"
                        + "\n".join(failed_list)
                    )

                # Return the path of the first successful digest for compatibility
                return True, successful_digests[0][1], None
            else:
                # All failed
                error_summary = f"All {len(failed_digests)} topic digests failed"
                return False, None, error_summary

    def _mark_episodes_as_digested(
        self, transcripts: List[Dict], topic: str, timestamp: str
    ):
        """Mark episodes as digested in both databases and stamp with topic/date"""
        rss_episodes = []
        youtube_episodes = []

        # Separate by source
        for transcript in transcripts:
            if transcript["source"] == "rss":
                rss_episodes.append(transcript["id"])
            elif transcript["source"] == "youtube":
                # Remove 'yt_' prefix to get original ID
                original_id = int(transcript["id"].replace("yt_", ""))
                youtube_episodes.append(original_id)

        # Format date for database storage
        digest_date = now_utc().strftime("%Y-%m-%d")

        # Update RSS episodes in main database
        if rss_episodes:
            try:
                conn = get_connection(self.db_path)
                cursor = conn.cursor()

                for episode_id in rss_episodes:
                    cursor.execute(
                        """
                        UPDATE episodes
                        SET status = 'digested', digest_topic = ?, digest_date = ?
                        WHERE id = ?
                    """,
                        (topic, digest_date, episode_id),
                    )

                conn.commit()
                conn.close()
                logger.info(
                    f"✅ Marked {len(rss_episodes)} RSS episodes as digested for {topic}"
                )

            except Exception as e:
                logger.error(f"Error updating RSS database: {e}")

        # Update YouTube episodes in YouTube database
        if youtube_episodes:
            try:
                youtube_db_path = "youtube_transcripts.db"
                if Path(youtube_db_path).exists():
                    conn = get_connection(youtube_db_path)
                    cursor = conn.cursor()

                    for episode_id in youtube_episodes:
                        cursor.execute(
                            """
                            UPDATE episodes
                            SET status = 'digested', digest_topic = ?, digest_date = ?
                            WHERE id = ?
                        """,
                            (topic, digest_date, episode_id),
                        )

                    conn.commit()
                    conn.close()
                    logger.info(
                        f"✅ Marked {len(youtube_episodes)} YouTube episodes as digested for {topic}"
                    )

            except Exception as e:
                logger.error(f"Error updating YouTube database: {e}")

    def _move_transcripts_to_digested(self, transcripts: List[Dict]):
        """Move transcript files to digested folder"""
        digested_dir = self.transcripts_dir / "digested"
        digested_dir.mkdir(exist_ok=True)

        for transcript in transcripts:
            try:
                source_path = Path(transcript["transcript_path"])
                if source_path.exists():
                    dest_path = digested_dir / source_path.name
                    source_path.rename(dest_path)
                    logger.info(f"📁 Moved {source_path.name} to digested folder")
            except Exception as e:
                logger.error(
                    f"Error moving transcript {transcript['transcript_path']}: {e}"
                )

    def test_api_connection(self) -> bool:
        """Test OpenAI API connection using GPT-5"""
        if not self.api_available:
            return False

        if self.mock_mode:
            logger.info("🧪 MOCK: OpenAI connection test successful")
            return True

        try:
            result = call_openai_with_backoff(
                client=self.client,
                component="connection_test",
                model=self.model,
                input=[
                    {
                        "role": "user",
                        "content": "Hello, please respond with 'API connection successful'",
                    }
                ],
                reasoning={"effort": "minimal"},
                max_output_tokens=50,
            )

            response_text = result.text
            success = "successful" in response_text.lower()
            if success:
                logger.info(f"✅ API connection test successful with {self.model}")
            return success

        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False

    def _generate_mock_digest(self, topic: str, summaries: List[Dict]) -> str:
        """Generate mock digest for CI smoke tests"""
        timestamp = now_utc().strftime("%B %d, %Y")
        mock_content = f"""# {topic} Digest - {timestamp}

## Mock Digest Content

This is a mock digest generated for testing purposes.

### Summary
- Topic: {topic}
- Summaries processed: {len(summaries)}
- Generated at: {timestamp}

### Mock Content Items
"""

        for i, summary in enumerate(summaries[:3], 1):  # Show first 3 summaries
            mock_content += f"""
#### Mock Item {i}
**Episode:** {summary.get('episode_id', 'Unknown')}
**Title:** {summary.get('title', 'Mock Title')}
**Summary:** Mock summary content for testing purposes.
"""

        return mock_content

    def _format_digest_from_structured_data(self, topic: str, digest_data: Dict) -> str:
        """Format structured digest data into readable markdown"""
        timestamp = now_utc().strftime("%B %d, %Y")
        items = digest_data.get("items", [])

        # Start with header
        content = f"# {topic} Digest - {timestamp}\n\n"

        # Add status if partial
        status = digest_data.get("status", "OK")
        if status == "PARTIAL":
            content += "⚠️ **Note: This digest contains partial results due to processing limitations.**\n\n"

        # Add summary
        content += f"## Summary\n\n"
        content += f"Today's {topic.lower()} digest contains {len(items)} key developments and insights.\n\n"

        # Add items
        for i, item in enumerate(items, 1):
            title = item.get("title", f"Development #{i}")
            blurb = item.get("blurb", "No description available.")

            content += f"### {title}\n\n{blurb}\n\n"

        return content


def main():
    """CLI interface for OpenAI digest generation"""
    import argparse

    parser = argparse.ArgumentParser(
        description="OpenAI Digest Integration - Multi-Topic Digest Generator"
    )
    parser.add_argument(
        "--topic", type=str, help="Generate digest for specific topic only"
    )
    parser.add_argument(
        "--list-topics", action="store_true", help="List available topics with episodes"
    )
    parser.add_argument(
        "--test-api", action="store_true", help="Test OpenAI API connection"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="podcast_monitor.db",
        help="Database path (default: podcast_monitor.db)",
    )

    args = parser.parse_args()

    # Initialize OpenAI integration
    integration = OpenAIDigestIntegration(db_path=args.db)

    if args.test_api:
        logger.info("🧪 Testing OpenAI API connection...")
        if integration.test_api_connection():
            logger.info("✅ API connection successful")
        else:
            logger.error("❌ API connection failed")
        return

    if args.list_topics:
        logger.info("📂 Available topics with episodes ready for digest:")
        topics = integration.get_available_topics()
        if topics:
            for topic in topics:
                transcripts = integration.get_transcripts_for_analysis(topic=topic)
                logger.info(f"  📄 {topic}: {len(transcripts)} episodes")
        else:
            logger.info("  No topics with episodes ready for digest")
        return

    # Generate digest(s)
    if args.topic:
        logger.info(f"🎯 Generating digest for topic: {args.topic}")
        success, path, error = integration.generate_digest(topic=args.topic)

        if success:
            logger.info(f"✅ Topic digest generated successfully: {path}")
        else:
            logger.error(f"❌ Topic digest generation failed: {error}")
    else:
        logger.info("🚀 Generating digests for all available topics...")
        success, path, error = integration.generate_digest()

        if success:
            logger.info(f"✅ Multi-topic digest generation completed")
        else:
            logger.error(f"❌ Multi-topic digest generation failed: {error}")


if __name__ == "__main__":
    main()
