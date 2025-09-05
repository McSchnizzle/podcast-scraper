#!/usr/bin/env python3
"""
Episode Summary Generator - Map-Reduce Implementation with GPT-5
Generates per-episode summaries using GPT-5 Responses API with robust error handling
"""

import os
import json
import hashlib
import sqlite3
import time
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import logging
from utils.datetime_utils import now_utc

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import config
from utils.openai_helpers import call_openai_with_backoff, get_json_schema, generate_idempotency_key
from utils.logging_setup import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

def approx_tokens(text: str) -> int:
    """Estimate token count using simple heuristic"""
    return (len(text) + 3) // 4

class EpisodeSummaryGenerator:
    """GPT-5 powered episode summarizer with chunking and caching"""
    
    def __init__(self, cache_db_path: str = "episode_summaries.db"):
        """Initialize the episode summary generator with GPT-5"""
        self.cache_db_path = cache_db_path
        self.client = None
        self.api_available = False
        
        # Check for mock mode
        self.mock_mode = os.getenv('MOCK_OPENAI') == '1' or os.getenv('CI_SMOKE') == '1'
        
        if self.mock_mode:
            logger.info("🧪 MOCK MODE: Using mock OpenAI responses for summaries")
            self.client = None
            self.api_available = True
        else:
            # Initialize OpenAI client
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.error("OPENAI_API_KEY environment variable not set")
                self.client = None
                self.api_available = False
            else:
                try:
                    from openai import OpenAI
                    self.client = OpenAI(api_key=api_key.strip())
                    self.api_available = True
                    logger.info(f"✅ Episode Summary Generator initialized with {config.GPT5_MODELS['summary']}")
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI client: {e}")
                    self.client = None
                    self.api_available = False
        
        # Configuration from new Phase 2 settings
        self.model = config.GPT5_MODELS['summary']
        self.max_output_tokens = config.OPENAI_TOKENS['summary']  
        self.reasoning_effort = config.REASONING_EFFORT['summary']
        self.feature_enabled = config.FEATURE_FLAGS['use_gpt5_summaries']
        
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
            with sqlite3.connect(self.cache_db_path) as conn:
                # Enhanced summaries table with idempotency support
                conn.execute("""
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
                """)
                
                # Idempotency constraint for summaries
                conn.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_summaries 
                    ON episode_summaries(episode_id, chunk_index, prompt_version, model)
                """)
                
                # Run headers table for observability
                conn.execute("""
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
                """)
                
                conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_timestamp ON episode_summaries(topic, timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_run_component ON run_headers(component, started_at)")
                conn.commit()
                
            logger.info(f"📚 Summary cache database initialized with idempotency: {self.cache_db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize cache database: {e}")
    
    def _get_content_hash(self, content: str) -> str:
        """Generate hash of content for caching"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_cached_summary(self, content_hash: str) -> Optional[str]:
        """Retrieve cached summary if available"""
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                cursor = conn.execute(
                    "SELECT summary FROM episode_summaries WHERE content_hash = ?",
                    (content_hash,)
                )
                row = cursor.fetchone()
                if row:
                    logger.info("📖 Using cached episode summary")
                    return row[0]
        except Exception as e:
            logger.warning(f"Failed to retrieve cached summary: {e}")
        return None
    
    def _cache_summary(self, content_hash: str, topic: str, timestamp: str, summary: str, content: str):
        """Cache generated summary"""
        try:
            word_count = len(content.split())
            with sqlite3.connect(self.cache_db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO episode_summaries 
                    (content_hash, topic, timestamp, summary, word_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (content_hash, topic, timestamp, summary, word_count))
                conn.commit()
                logger.info(f"💾 Cached summary for {topic} episode")
        except Exception as e:
            logger.warning(f"Failed to cache summary: {e}")
    
    def _clean_content_for_summary(self, content: str, max_words: int = 1500) -> str:
        """Clean and truncate content for summary generation"""
        # Remove markdown formatting and excessive whitespace
        content = content.replace('\n', ' ').replace('\r', ' ')
        content = ' '.join(content.split())
        
        # Remove common markdown elements
        import re
        content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)  # Bold
        content = re.sub(r'\*(.*?)\*', r'\1', content)      # Italic
        content = re.sub(r'#{1,6}\s+', '', content)         # Headers
        content = re.sub(r'\[.*?\]\(.*?\)', '', content)    # Links
        
        # Truncate to reasonable length for API
        words = content.split()
        if len(words) > max_words:
            content = ' '.join(words[:max_words]) + "..."
            logger.info(f"📝 Truncated content to {max_words} words for summary generation")
        
        return content
    
    def generate_summary(self, content: str, topic: str, timestamp: str, fallback_desc: str = None) -> str:
        """Generate AI-powered summary of episode content"""
        if not content or len(content.strip()) < 50:
            logger.info("📄 Content too short for AI summary, using fallback")
            return fallback_desc or f"Daily digest episode covering {topic.replace('_', ' ')}"
        
        # Check cache first
        content_hash = self._get_content_hash(content)
        cached_summary = self._get_cached_summary(content_hash)
        if cached_summary:
            return cached_summary
        
        # If OpenAI API not available, return fallback
        if not self.api_available:
            logger.info("🔄 OpenAI API not available, using enhanced fallback description")
            return self._generate_fallback_summary(content, topic, fallback_desc)
        
        # Mock mode - return deterministic summary
        if self.mock_mode:
            logger.info(f"🧪 MOCK: Generating mock summary for {topic}")
            return self._generate_mock_summary(content, topic, fallback_desc)
        
        try:
            # Clean content for API consumption
            clean_content = self._clean_content_for_summary(content)
            
            # Generate summary using OpenAI
            logger.info(f"🤖 Generating AI summary for {topic} episode ({len(clean_content)} chars)")
            
            response = self.client.chat.completions.create(
                model="gpt-5-mini",  # Cost-effective model for summaries
                messages=[
                    {
                        "role": "system", 
                        "content": """You are a podcast episode summarizer. Create concise 2-3 sentence descriptions (maximum 250 characters) for RSS feeds that tell subscribers what key topics each episode covers. Focus on the most important content highlights. Be direct and informative."""
                    },
                    {
                        "role": "user",
                        "content": f"Write a 2-3 sentence RSS description (max 250 characters) for this {topic.replace('_', ' ').title()} digest:\n\n{clean_content}"
                    }
                ],
                max_completion_tokens=100,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Validate summary quality
            if len(summary) < 20 or len(summary) > 300:
                logger.warning(f"⚠️ Generated summary length unusual ({len(summary)} chars), using fallback")
                summary = self._generate_fallback_summary(content, topic, fallback_desc)
            else:
                logger.info(f"✅ Generated AI summary ({len(summary)} chars)")
                # Cache the successful summary
                self._cache_summary(content_hash, topic, timestamp, summary, content)
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Failed to generate AI summary: {e}")
            return self._generate_fallback_summary(content, topic, fallback_desc)
    
    def _generate_fallback_summary(self, content: str, topic: str, fallback_desc: str = None) -> str:
        """Generate enhanced fallback summary from content analysis"""
        if fallback_desc and len(content.strip()) < 100:
            return fallback_desc
        
        try:
            # Extract key information from content
            sentences = content.replace('\n', ' ').split('. ')
            
            # Find sentences with key indicator words
            key_indicators = [
                'announced', 'released', 'launched', 'reported', 'revealed', 'discussed',
                'analysis', 'breakthrough', 'development', 'update', 'news', 'trend',
                'important', 'significant', 'major', 'key', 'critical', 'interesting'
            ]
            
            relevant_sentences = []
            for sentence in sentences[:10]:  # Check first 10 sentences
                if any(indicator in sentence.lower() for indicator in key_indicators):
                    relevant_sentences.append(sentence.strip())
                if len(relevant_sentences) >= 2:
                    break
            
            if relevant_sentences:
                summary = '. '.join(relevant_sentences[:2])
                if not summary.endswith('.'):
                    summary += '.'
                
                # Add topic context if summary is short
                if len(summary) < 100:
                    topic_display = topic.replace('_', ' ').title()
                    summary = f"This {topic_display} episode covers {summary.lower()}"
                
                return summary[:300]  # Limit to reasonable length
            
            # Final fallback
            topic_display = topic.replace('_', ' ').title()
            date_str = now_utc().strftime('%B %d, %Y')
            return f"{topic_display} digest covering the latest developments and insights from {date_str}."
            
        except Exception as e:
            logger.warning(f"Fallback summary generation failed: {e}")
            return fallback_desc or f"Daily digest episode covering {topic.replace('_', ' ')}"
    
    def _generate_mock_summary(self, content: str, topic: str, fallback_desc: str = None) -> str:
        """Generate realistic mock summary for CI smoke tests"""
        topic_display = topic.replace('_', ' ').title()
        
        # Create topic-specific templates
        templates = {
            'ai_news': [
                f"Latest {topic_display} updates covering AI developments and breakthroughs.",
                f"This {topic_display} episode explores recent AI research and industry innovations.",
                f"AI technology advances and their implications are discussed in this {topic_display} digest."
            ],
            'tech_product_releases': [
                f"New technology products and launches are highlighted in this {topic_display} episode.",
                f"Latest product releases and tech hardware updates covered in {topic_display}.",
                f"This {topic_display} digest reviews recent gadget launches and software updates."
            ],
            'tech_news_and_tech_culture': [
                f"Technology industry developments and cultural trends in this {topic_display} episode.",
                f"Tech company news and digital culture insights from {topic_display}.",
                f"This {topic_display} digest covers tech industry analysis and cultural implications."
            ],
            'community_organizing': [
                f"Community activism and organizing strategies discussed in {topic_display}.",
                f"Grassroots organizing efforts and civic engagement covered in this {topic_display} episode.",
                f"Local organizing initiatives and community building insights from {topic_display}."
            ],
            'social_justice': [
                f"Social justice movements and advocacy work highlighted in {topic_display}.",
                f"Civil rights developments and social equality issues in this {topic_display} episode.",
                f"This {topic_display} digest covers social justice initiatives and policy changes."
            ],
            'societal_culture_change': [
                f"Cultural shifts and societal transformation explored in {topic_display}.",
                f"Social change movements and cultural evolution discussed in this {topic_display} episode.",
                f"This {topic_display} digest examines societal trends and cultural developments."
            ]
        }
        
        # Select template based on topic
        topic_key = topic.lower().replace(' ', '_')
        if topic_key in templates:
            # Use content hash to consistently select same template
            template_index = hash(content[:100]) % len(templates[topic_key])
            return templates[topic_key][template_index]
        
        # Generic fallback
        return f"This {topic_display} episode covers recent developments with insights and analysis."
    
    def get_summary_stats(self) -> Dict:
        """Get statistics about cached summaries"""
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_summaries,
                        COUNT(DISTINCT topic) as unique_topics,
                        AVG(word_count) as avg_content_words,
                        AVG(LENGTH(summary)) as avg_summary_chars
                    FROM episode_summaries
                """)
                row = cursor.fetchone()
                
                topic_cursor = conn.execute("""
                    SELECT topic, COUNT(*) as count 
                    FROM episode_summaries 
                    GROUP BY topic 
                    ORDER BY count DESC
                """)
                topic_counts = dict(topic_cursor.fetchall())
                
                return {
                    'total_summaries': row[0] if row else 0,
                    'unique_topics': row[1] if row else 0,
                    'avg_content_words': round(row[2]) if row and row[2] else 0,
                    'avg_summary_chars': round(row[3]) if row and row[3] else 0,
                    'topic_distribution': topic_counts
                }
        except Exception as e:
            logger.error(f"Failed to get summary stats: {e}")
            return {}

    def generate_episode_summary(self, episode_data: Dict, topic: str, max_tokens: int = None) -> Optional[str]:
        """Generate a concise summary of an episode for a specific topic (Map phase)"""
        if not self.api_available:
            logger.error("OpenAI API not available")
            return None
            
        if max_tokens is None:
            max_tokens = self.settings['max_episode_summary_tokens']
        
        topic_info = self.settings['topics'].get(topic, {})
        topic_description = topic_info.get('description', topic)
        
        # Create focused summary prompt
        system_prompt = f"""You are an expert content summarizer. Create a concise summary focused on {topic_description}.

Requirements:
- Maximum {max_tokens} tokens
- Focus only on content related to {topic}
- Include key insights, developments, or announcements
- Include one compelling quote if particularly relevant
- Write in flowing prose, no bullet points or lists
- If episode has minimal {topic} content, state "Limited {topic} content" and provide brief summary"""

        user_prompt = f"""Episode: {episode_data['title']}
Published: {episode_data['published_date']}
Source: {episode_data['source']}

Transcript excerpt (first 3000 chars):
{episode_data['content'][:3000]}

Create a focused summary for {topic} digest."""

        try:
            response = self.client.chat.completions.create(
                model=self.settings['scoring_model'],  # Use cost-effective model for efficiency
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.settings['scoring_temperature'],
                max_completion_tokens=max_tokens,
                timeout=self.settings['timeout_seconds']
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Log token usage
            actual_tokens = approx_tokens(summary)
            logger.info(f"Generated summary for {episode_data['episode_id']} ({topic}): {actual_tokens} tokens")
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate summary for {episode_data['episode_id']} ({topic}): {e}")
            return None

    def select_top_episodes_for_topic(self, transcripts: List[Dict], topic: str, 
                                    threshold: float = None, max_episodes: int = None) -> List[Dict]:
        """Select top episodes for a topic based on relevance scores"""
        if threshold is None:
            threshold = self.settings['relevance_threshold']
        if max_episodes is None:
            max_episodes = self.settings['max_episodes_per_topic']
        
        # Filter episodes by topic relevance
        relevant_episodes = []
        for episode in transcripts:
            topic_scores = episode.get('topic_scores', {})
            topic_score = topic_scores.get(topic, 0.0)
            
            if topic_score >= threshold:
                episode['topic_score'] = topic_score
                relevant_episodes.append(episode)
        
        # Sort by relevance score (highest first) and take top N
        relevant_episodes.sort(key=lambda x: x['topic_score'], reverse=True)
        selected_episodes = relevant_episodes[:max_episodes]
        
        logger.info(f"Topic '{topic}': {len(relevant_episodes)} candidates, "
                   f"{len(selected_episodes)} selected (threshold: {threshold})")
        
        return selected_episodes

    def generate_topic_summaries(self, transcripts: List[Dict], topic: str) -> List[Dict]:
        """Generate summaries for all selected episodes for a topic (Map phase)"""
        selected_episodes = self.select_top_episodes_for_topic(transcripts, topic)
        
        if not selected_episodes:
            logger.warning(f"No episodes selected for topic '{topic}'")
            return []
        
        summaries = []
        max_summary_tokens = self.settings['max_episode_summary_tokens']
        
        for episode in selected_episodes:
            logger.info(f"Generating summary for {episode['episode_id']} (score: {episode['topic_score']:.3f})")
            
            summary = self.generate_episode_summary(episode, topic, max_summary_tokens)
            if summary:
                summaries.append({
                    'episode_id': episode['episode_id'],
                    'title': episode['title'],
                    'published_date': episode['published_date'],
                    'source': episode['source'],
                    'topic_score': episode['topic_score'],
                    'summary': summary,
                    'tokens': approx_tokens(summary)
                })
                
                # Rate limiting
                time.sleep(self.settings['rate_limit_delay'])
        
        total_tokens = sum(s['tokens'] for s in summaries)
        logger.info(f"Generated {len(summaries)} summaries for '{topic}': {total_tokens} total tokens")
        
        return summaries

def main():
    """Test the episode summary generator"""
    generator = EpisodeSummaryGenerator()
    
    # Test with sample content
    test_content = """
    # AI News Digest - January 15, 2024
    
    Today's digest covers major developments in artificial intelligence, including OpenAI's latest GPT-4 updates, 
    Google's Bard improvements, and Microsoft's integration of AI tools into Office 365. We also discuss the 
    implications of new AI regulations in the EU and recent breakthroughs in computer vision research.
    
    The episode includes analysis of market trends, startup funding news, and interviews with leading AI researchers
    about the future of machine learning applications in healthcare and education.
    """
    
    summary = generator.generate_summary(
        content=test_content,
        topic="ai_news", 
        timestamp="20240115_120000",
        fallback_desc="AI news and developments digest"
    )
    
    print(f"Generated summary: {summary}")
    
    # Show stats
    stats = generator.get_summary_stats()
    print(f"Summary cache stats: {stats}")

if __name__ == "__main__":
    main()