#!/usr/bin/env python3
"""
Episode Summary Generator - AI-powered RSS episode descriptions
Generates concise, informative summaries of digest episodes using OpenAI API
"""

import os
import json
import hashlib
import sqlite3
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
import logging

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EpisodeSummaryGenerator:
    def __init__(self, cache_db_path: str = "episode_summaries.db"):
        """Initialize the episode summary generator with caching"""
        self.cache_db_path = cache_db_path
        self.client = None
        self.api_available = False
        
        # Initialize OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY environment variable not set - summaries will use fallback descriptions")
        elif len(api_key.strip()) < 10:
            logger.warning(f"OPENAI_API_KEY appears invalid (length: {len(api_key.strip())}) - using fallback descriptions")
        else:
            try:
                # Initialize OpenAI client (v1.0+ format)
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key.strip())
                self.api_available = True
                logger.info("✅ OpenAI client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e} - using fallback descriptions")
                self.api_available = False
        
        # Initialize cache database
        self._init_cache_db()
    
    def _init_cache_db(self):
        """Initialize SQLite database for caching summaries"""
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS episode_summaries (
                        content_hash TEXT PRIMARY KEY,
                        topic TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        word_count INTEGER
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_timestamp ON episode_summaries(topic, timestamp)")
                conn.commit()
            logger.info(f"📚 Summary cache database initialized: {self.cache_db_path}")
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
        
        try:
            # Clean content for API consumption
            clean_content = self._clean_content_for_summary(content)
            
            # Generate summary using OpenAI
            logger.info(f"🤖 Generating AI summary for {topic} episode ({len(clean_content)} chars)")
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective model for summaries
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
                max_tokens=100,
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
            date_str = datetime.now().strftime('%B %d, %Y')
            return f"{topic_display} digest covering the latest developments and insights from {date_str}."
            
        except Exception as e:
            logger.warning(f"Fallback summary generation failed: {e}")
            return fallback_desc or f"Daily digest episode covering {topic.replace('_', ' ')}"
    
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