#!/usr/bin/env python3
"""
OpenAI Digest Integration - Multi-Topic Digest Generator
Complete replacement for Claude integration using OpenAI GPT-4 for consistency
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sqlite3
import openai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIDigestIntegration:
    def __init__(self, db_path: str = "podcast_monitor.db", transcripts_dir: str = "transcripts"):
        self.db_path = db_path
        self.transcripts_dir = Path(transcripts_dir)
        
        # Initialize OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("OPENAI_API_KEY environment variable not set")
            self.client = None
            self.api_available = False
        elif len(api_key.strip()) < 10:
            logger.error(f"OPENAI_API_KEY appears invalid (length: {len(api_key.strip())})")
            self.client = None
            self.api_available = False
        else:
            try:
                # Initialize OpenAI client
                openai.api_key = api_key.strip()
                self.client = openai
                self.api_available = True
                logger.info(f"✅ OpenAI API client initialized (key length: {len(api_key.strip())})")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
                self.api_available = False

    def get_transcripts_for_analysis(self, include_youtube: bool = True, topic: str = None) -> List[Dict]:
        """Get transcripts ready for API analysis from both databases, optionally filtered by topic"""
        transcripts = []
        
        # Get RSS transcripts from main database
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Updated query to only include episodes approved for digest with specific topic assignment
            if topic:
                query = """
                SELECT id, title, transcript_path, episode_id, published_date, status, digest_topic
                FROM episodes 
                WHERE transcript_path IS NOT NULL 
                AND status = 'transcribed'
                AND digest_topic = ?
                ORDER BY published_date DESC
                """
                cursor.execute(query, (topic,))
            else:
                query = """
                SELECT id, title, transcript_path, episode_id, published_date, status, digest_topic
                FROM episodes 
                WHERE transcript_path IS NOT NULL 
                AND status = 'transcribed'
                AND digest_topic IS NOT NULL
                ORDER BY published_date DESC
                """
                cursor.execute(query)
            
            rss_episodes = cursor.fetchall()
            conn.close()
            
            for episode_id, title, transcript_path, ep_id, published_date, status, digest_topic in rss_episodes:
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
                                'content': content[:50000],  # Limit content for API
                                'source': 'rss',
                                'digest_topic': digest_topic
                            })
                    except Exception as e:
                        logger.error(f"Error reading RSS transcript {transcript_path}: {e}")
            
            logger.info(f"Found {len(transcripts)} RSS transcripts")
            
        except Exception as e:
            logger.error(f"Error getting RSS transcripts: {e}")
        
        # Get YouTube transcripts from YouTube database
        if include_youtube:
            try:
                youtube_db_path = "youtube_transcripts.db"
                if Path(youtube_db_path).exists():
                    conn = sqlite3.connect(youtube_db_path)
                    cursor = conn.cursor()
                    
                    # Use the same query logic for YouTube database
                    if topic:
                        cursor.execute(query, (topic,))
                    else:
                        cursor.execute(query)
                    youtube_episodes = cursor.fetchall()
                    conn.close()
                    
                    youtube_count = 0
                    for episode_id, title, transcript_path, ep_id, published_date, status, digest_topic in youtube_episodes:
                        transcript_file = Path(transcript_path)
                        
                        if transcript_file.exists():
                            try:
                                with open(transcript_file, 'r', encoding='utf-8') as f:
                                    content = f.read().strip()
                                
                                if content:
                                    transcripts.append({
                                        'id': f"yt_{episode_id}",  # Prefix to avoid ID conflicts
                                        'title': title,
                                        'episode_id': ep_id,
                                        'published_date': published_date,
                                        'transcript_path': str(transcript_path),
                                        'content': content[:50000],
                                        'source': 'youtube',
                                        'digest_topic': digest_topic
                                    })
                                    youtube_count += 1
                            except Exception as e:
                                logger.error(f"Error reading YouTube transcript {transcript_path}: {e}")
                    
                    logger.info(f"Found {youtube_count} YouTube transcripts")
                else:
                    logger.info("No YouTube database found - RSS only")
            
            except Exception as e:
                logger.error(f"Error getting YouTube transcripts: {e}")
        
        # Sort combined transcripts by date
        transcripts.sort(key=lambda x: x['published_date'], reverse=True)
        logger.info(f"Total transcripts for analysis: {len(transcripts)}")
        
        return transcripts

    def prepare_digest_prompt(self, transcripts: List[Dict], topic: str = None) -> str:
        """Prepare topic-specific digest prompt for OpenAI GPT-4"""
        
        transcript_summaries = []
        for transcript in transcripts:
            summary = f"""
## {transcript['title']} ({transcript['published_date']})
{transcript['content'][:12000]}...
"""
            transcript_summaries.append(summary)
        
        combined_content = "\n".join(transcript_summaries)
        
        # Topic-specific prompts with focused analysis - same structure as Claude version
        topic_descriptions = {
            'AI News': {
                'title': 'AI News Digest',
                'focus': 'artificial intelligence developments, machine learning breakthroughs, AI product launches, research updates, industry announcements',
                'sections': [
                    '### 🤖 AI Model Releases & Updates',
                    '### 🔬 Research Breakthroughs',
                    '### 🏢 Industry Developments',
                    '### 🛠️ Developer Tools & Platforms',
                    '### 📈 Market Impact & Analysis'
                ]
            },
            'Tech Product Releases': {
                'title': 'Tech Product Releases Digest',
                'focus': 'new technology product launches, hardware releases, software updates, gadget reviews, product announcements',
                'sections': [
                    '### 📱 Consumer Electronics',
                    '### 💻 Computing & Hardware',
                    '### 🎮 Gaming & Entertainment',
                    '### 🏠 Smart Home & IoT',
                    '### 🚗 Automotive Tech'
                ]
            },
            'Tech News and Tech Culture': {
                'title': 'Tech News & Culture Digest',
                'focus': 'technology industry news, tech company developments, tech culture discussions, digital trends, tech policy',
                'sections': [
                    '### 📰 Industry News',
                    '### 🏛️ Policy & Regulation',
                    '### 🌐 Digital Culture & Trends',
                    '### 💼 Business & Leadership',
                    '### 🔮 Future Outlook'
                ]
            },
            'Community Organizing': {
                'title': 'Community Organizing Digest',
                'focus': 'grassroots organizing, community activism, local organizing efforts, civic engagement, community building strategies',
                'sections': [
                    '### 🤝 Grassroots Campaigns',
                    '### 🗳️ Civic Engagement',
                    '### 🏘️ Community Building',
                    '### 📢 Advocacy Strategies',
                    '### 🌱 Local Impact Stories'
                ]
            },
            'Social Justice': {
                'title': 'Social Justice Digest',
                'focus': 'social justice movements, civil rights, equity and inclusion, systemic justice issues, advocacy and activism',
                'sections': [
                    '### ⚖️ Civil Rights Updates',
                    '### 🌈 Equity & Inclusion',
                    '### 📊 Systemic Change',
                    '### 🔊 Advocacy Highlights',
                    '### 💪 Movement Building'
                ]
            },
            'Societal Culture Change': {
                'title': 'Societal Culture Change Digest',
                'focus': 'cultural shifts, social movements, changing social norms, generational changes, cultural transformation',
                'sections': [
                    '### 🌊 Cultural Shifts',
                    '### 👥 Generational Changes',
                    '### 🔄 Social Transformation',
                    '### 📱 Digital Culture Impact',
                    '### 🌍 Global Perspectives'
                ]
            }
        }
        
        # Get topic info or use generic if not specified
        if topic and topic in topic_descriptions:
            topic_info = topic_descriptions[topic]
            title = topic_info['title']
            focus_area = topic_info['focus']
            sections = '\n'.join(topic_info['sections'])
        else:
            title = 'Daily Tech Digest'
            focus_area = 'technology and innovation developments'
            sections = """### 🤖 AI & Machine Learning
### 📱 Consumer Tech
### 💼 Business & Industry
### 🔒 Security & Privacy
### 🛠️ Open Source & Development"""
        
        prompt = f"""You are an expert analyst creating a focused digest from podcast transcripts.

Please analyze the following {len(transcripts)} podcast transcripts focused on {focus_area} and create a structured digest:

{combined_content}

Create a comprehensive digest with the following structure:

# {title} - {datetime.now().strftime('%B %d, %Y')}

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

    def get_available_topics(self) -> List[str]:
        """Get list of topics that have episodes ready for digest"""
        topics_with_episodes = set()
        
        # Check RSS database
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT digest_topic 
                FROM episodes 
                WHERE digest_topic IS NOT NULL 
                AND status = 'transcribed'
                AND transcript_path IS NOT NULL
            """)
            rss_topics = [row[0] for row in cursor.fetchall()]
            topics_with_episodes.update(rss_topics)
            conn.close()
        except Exception as e:
            logger.error(f"Error getting RSS topics: {e}")
        
        # Check YouTube database
        try:
            youtube_db_path = "youtube_transcripts.db"
            if Path(youtube_db_path).exists():
                conn = sqlite3.connect(youtube_db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT digest_topic 
                    FROM episodes 
                    WHERE digest_topic IS NOT NULL 
                    AND status = 'transcribed'
                    AND transcript_path IS NOT NULL
                """)
                youtube_topics = [row[0] for row in cursor.fetchall()]
                topics_with_episodes.update(youtube_topics)
                conn.close()
        except Exception as e:
            logger.error(f"Error getting YouTube topics: {e}")
        
        return sorted(list(topics_with_episodes))

    def generate_topic_digest(self, topic: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Generate digest for a specific topic using OpenAI GPT-5"""
        
        logger.info(f"🧠 Starting {topic} digest generation with OpenAI GPT-5")
        
        if not self.api_available:
            logger.error("OpenAI API not available - cannot generate digest")
            return False, None, None
        
        # Get transcripts for this topic
        transcripts = self.get_transcripts_for_analysis(topic=topic)
        if not transcripts:
            logger.warning(f"No transcripts available for topic: {topic}")
            return False, None, None
        
        logger.info(f"📊 Analyzing {len(transcripts)} transcripts for {topic}")
        
        try:
            # Prepare topic-specific prompt
            prompt = self.prepare_digest_prompt(transcripts, topic=topic)
            
            # Call OpenAI GPT-5 API
            response = self.client.ChatCompletion.create(
                model="gpt-5",  # Use latest GPT-5 model
                messages=[{
                    "role": "system",
                    "content": "You are an expert analyst creating focused, insightful digests from podcast transcripts. You excel at identifying key themes, connecting information across sources, and providing actionable insights."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                max_tokens=4000,
                temperature=0.7
            )
            
            digest_content = response.choices[0].message.content
            
            # Save topic-specific digest
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            topic_safe = topic.lower().replace(' ', '_').replace('&', 'and')
            digest_filename = f"{topic_safe}_digest_{timestamp}.md"
            digest_path = Path('daily_digests') / digest_filename
            digest_path.parent.mkdir(exist_ok=True)
            
            with open(digest_path, 'w', encoding='utf-8') as f:
                f.write(digest_content)
            
            logger.info(f"✅ {topic} digest saved to {digest_path}")
            
            # Update databases - mark episodes as digested  
            self._mark_episodes_as_digested(transcripts)
            
            # Move transcripts to digested folder
            self._move_transcripts_to_digested(transcripts)
            
            return True, str(digest_path), None
            
        except Exception as e:
            logger.error(f"Error generating {topic} digest with OpenAI GPT-5: {e}")
            return False, None, str(e)

    def generate_all_topic_digests(self) -> Dict[str, Tuple[bool, Optional[str], Optional[str]]]:
        """Generate digests for all available topics"""
        
        available_topics = self.get_available_topics()
        if not available_topics:
            logger.warning("No topics with episodes ready for digest")
            return {}
        
        logger.info(f"🚀 Starting multi-topic digest generation for {len(available_topics)} topics")
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
        logger.info(f"\n🏁 Multi-topic digest generation complete: {successful}/{len(available_topics)} topics successful")
        
        return results

    def generate_digest(self, topic: str = None) -> Tuple[bool, Optional[str], Optional[str]]:
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
                summary = f"Generated {len(successful_digests)} topic digests:\n" + "\n".join(digest_list)
                
                if failed_digests:
                    failed_list = [f"{topic}: {error or 'Unknown error'}" for topic, error in failed_digests]
                    summary += f"\n\nFailed {len(failed_digests)} digests:\n" + "\n".join(failed_list)
                
                # Return the path of the first successful digest for compatibility
                return True, successful_digests[0][1], None
            else:
                # All failed
                error_summary = f"All {len(failed_digests)} topic digests failed"
                return False, None, error_summary

    def _mark_episodes_as_digested(self, transcripts: List[Dict]):
        """Mark episodes as digested in both databases"""
        rss_episodes = []
        youtube_episodes = []
        
        # Separate by source
        for transcript in transcripts:
            if transcript['source'] == 'rss':
                rss_episodes.append(transcript['id'])
            elif transcript['source'] == 'youtube':
                # Remove 'yt_' prefix to get original ID
                original_id = int(transcript['id'].replace('yt_', ''))
                youtube_episodes.append(original_id)
        
        # Update RSS episodes in main database
        if rss_episodes:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for episode_id in rss_episodes:
                    cursor.execute("""
                        UPDATE episodes 
                        SET status = 'digested'
                        WHERE id = ?
                    """, (episode_id,))
                
                conn.commit()
                conn.close()
                logger.info(f"✅ Marked {len(rss_episodes)} RSS episodes as digested")
                
            except Exception as e:
                logger.error(f"Error updating RSS database: {e}")
        
        # Update YouTube episodes in YouTube database
        if youtube_episodes:
            try:
                youtube_db_path = "youtube_transcripts.db"
                if Path(youtube_db_path).exists():
                    conn = sqlite3.connect(youtube_db_path)
                    cursor = conn.cursor()
                    
                    for episode_id in youtube_episodes:
                        cursor.execute("""
                            UPDATE episodes 
                            SET status = 'digested'
                            WHERE id = ?
                        """, (episode_id,))
                    
                    conn.commit()
                    conn.close()
                    logger.info(f"✅ Marked {len(youtube_episodes)} YouTube episodes as digested")
                
            except Exception as e:
                logger.error(f"Error updating YouTube database: {e}")

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
        """Test OpenAI API connection"""
        if not self.api_available:
            return False
        
        try:
            response = self.client.ChatCompletion.create(
                model="gpt-5",
                messages=[{
                    "role": "user",
                    "content": "Hello, please respond with 'API connection successful'"
                }],
                max_tokens=50
            )
            
            response_text = response.choices[0].message.content
            return "successful" in response_text.lower()
            
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False


def main():
    """CLI interface for OpenAI digest generation"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OpenAI Digest Integration - Multi-Topic Digest Generator')
    parser.add_argument('--topic', type=str, help='Generate digest for specific topic only')
    parser.add_argument('--list-topics', action='store_true', help='List available topics with episodes')
    parser.add_argument('--test-api', action='store_true', help='Test OpenAI API connection')
    parser.add_argument('--db', type=str, default='podcast_monitor.db', help='Database path (default: podcast_monitor.db)')
    
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


if __name__ == '__main__':
    main()