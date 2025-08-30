#!/usr/bin/env python3
"""
Claude API Integration - GitHub Actions Compatible
Direct API integration replacing CLI dependency
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sqlite3
import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClaudeAPIIntegration:
    def __init__(self, db_path: str = "podcast_monitor.db", transcripts_dir: str = "transcripts"):
        self.db_path = db_path
        self.transcripts_dir = Path(transcripts_dir)
        
        # Initialize Anthropic client
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.error("ANTHROPIC_API_KEY environment variable not set")
            self.client = None
            self.api_available = False
        else:
            try:
                self.client = anthropic.Anthropic(api_key=api_key)
                self.api_available = True
                logger.info("✅ Anthropic API client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {e}")
                self.client = None
                self.api_available = False

    def get_transcripts_for_analysis(self) -> List[Dict]:
        """Get transcripts ready for API analysis"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Only get episodes with status='transcribed'
            query = """
            SELECT id, title, transcript_path, episode_id, published_date, status
            FROM episodes 
            WHERE transcript_path IS NOT NULL 
            AND status = 'transcribed'
            ORDER BY published_date DESC
            """
            
            cursor.execute(query)
            episodes = cursor.fetchall()
            conn.close()
            
            transcripts = []
            for episode_id, title, transcript_path, ep_id, published_date, status in episodes:
                transcript_file = Path(transcript_path)
                
                if transcript_file.exists():
                    try:
                        with open(transcript_file, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                        
                        if content:
                            transcripts.append({
                                'id': episode_id,
                                'title': title,
                                'episode_id': ep_id,
                                'published_date': published_date,
                                'transcript_path': str(transcript_path),
                                'content': content[:50000]  # Limit content for API
                            })
                    except Exception as e:
                        logger.error(f"Error reading transcript {transcript_path}: {e}")
            
            return transcripts
            
        except Exception as e:
            logger.error(f"Error getting transcripts: {e}")
            return []

    def prepare_digest_prompt(self, transcripts: List[Dict]) -> str:
        """Prepare comprehensive digest prompt for Claude API"""
        
        transcript_summaries = []
        for transcript in transcripts:
            summary = f"""
## {transcript['title']} ({transcript['published_date']})
{transcript['content'][:8000]}...
"""
            transcript_summaries.append(summary)
        
        combined_content = "\n".join(transcript_summaries)
        
        prompt = f"""You are an expert tech analyst creating a comprehensive daily digest from podcast transcripts. 

Please analyze the following {len(transcripts)} podcast transcripts and create a structured daily digest:

{combined_content}

Create a comprehensive daily digest with the following structure:

# Daily Tech Digest - {datetime.now().strftime('%B %d, %Y')}

## 🌟 Top Stories
- List the 3-5 most important developments mentioned across episodes
- Include brief explanations of why they matter

## 📊 Key Developments by Category

### AI & Machine Learning
- Summarize AI-related news, breakthroughs, and industry developments

### Consumer Tech
- Cover new product launches, reviews, and consumer-focused news

### Business & Industry
- Include mergers, acquisitions, funding news, and business developments

### Security & Privacy
- Highlight cybersecurity news, privacy concerns, and regulatory updates

### Open Source & Development
- Cover new tools, frameworks, and developer-focused news

## 💡 Analysis & Insights
- Provide 2-3 deeper insights connecting themes across episodes
- Identify emerging trends or patterns

## 🔗 Cross-References
- Note when multiple episodes cover the same topic
- Highlight conflicting viewpoints or different perspectives

## 📅 Looking Ahead
- Mention upcoming events, releases, or developments discussed

Format the output as clean Markdown suitable for publication. Focus on accuracy, insight, and connecting information across sources."""

        return prompt

    def generate_api_digest(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """Generate daily digest using Anthropic API"""
        
        logger.info("🧠 Starting Anthropic API digest generation")
        
        if not self.api_available:
            logger.error("Anthropic API not available - cannot generate digest")
            return False, None, None
        
        # Get transcripts
        transcripts = self.get_transcripts_for_analysis()
        if not transcripts:
            logger.error("No transcripts available for analysis")
            return False, None, None
        
        logger.info(f"📊 Analyzing {len(transcripts)} transcripts with Anthropic API")
        
        try:
            # Prepare prompt
            prompt = self.prepare_digest_prompt(transcripts)
            
            # Call Anthropic API
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0.7,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            digest_content = message.content[0].text
            
            # Save digest
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            digest_filename = f"daily_digest_{timestamp}.md"
            digest_path = Path('daily_digests') / digest_filename
            digest_path.parent.mkdir(exist_ok=True)
            
            with open(digest_path, 'w', encoding='utf-8') as f:
                f.write(digest_content)
            
            logger.info(f"✅ Digest saved to {digest_path}")
            
            # Update database - mark episodes as digested
            self._mark_episodes_as_digested([t['id'] for t in transcripts])
            
            # Move transcripts to digested folder
            self._move_transcripts_to_digested(transcripts)
            
            return True, str(digest_path), None
            
        except Exception as e:
            logger.error(f"Error generating digest with Anthropic API: {e}")
            return False, None, None

    def _mark_episodes_as_digested(self, episode_ids: List[int]):
        """Mark episodes as digested in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for episode_id in episode_ids:
                cursor.execute("""
                    UPDATE episodes 
                    SET status = 'digested'
                    WHERE id = ?
                """, (episode_id,))
            
            conn.commit()
            conn.close()
            logger.info(f"✅ Marked {len(episode_ids)} episodes as digested")
            
        except Exception as e:
            logger.error(f"Error updating database: {e}")

    def _move_transcripts_to_digested(self, transcripts: List[Dict]):
        """Move transcript files to digested folder"""
        digested_dir = self.transcripts_dir / 'digested'
        digested_dir.mkdir(exist_ok=True)
        
        for transcript in transcripts:
            try:
                source_path = Path(transcript['transcript_path'])
                if source_path.exists():
                    dest_path = digested_dir / source_path.name
                    source_path.rename(dest_path)
                    logger.info(f"📁 Moved {source_path.name} to digested folder")
            except Exception as e:
                logger.error(f"Error moving transcript {transcript['transcript_path']}: {e}")

    def test_api_connection(self) -> bool:
        """Test Anthropic API connection"""
        if not self.api_available:
            return False
        
        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=50,
                messages=[{
                    "role": "user",
                    "content": "Hello, please respond with 'API connection successful'"
                }]
            )
            
            response = message.content[0].text
            return "successful" in response.lower()
            
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False