#!/usr/bin/env python3
"""
Daily Digest Generation System for Podcast Transcripts
Phase 2.75 Implementation using Claude Code headless mode
"""

import sqlite3
import os
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('digest_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DigestGenerator:
    def __init__(self, db_path: str = "podcast_monitor.db", transcripts_dir: str = "transcripts"):
        self.db_path = db_path
        self.transcripts_dir = Path(transcripts_dir)
        self.claude_binary = "claude"  # Claude Code headless binary
        
        # Topic categories for classification
        self.topic_categories = {
            "ai_tools": [
                "chatgpt", "claude", "gemini", "ai tool", "artificial intelligence",
                "machine learning", "neural network", "gpt", "llm", "automation",
                "ai-generated", "ai create", "ai democratize"
            ],
            "product_launches": [
                "launch", "release", "announcement", "new product", "google pixel",
                "event", "unveil", "debut", "introduce", "rollout"
            ],
            "creative_applications": [
                "creative", "art", "design", "music", "video", "content creation",
                "remix", "tiny desk", "kurt cobain", "notorious", "veo", "editing"
            ],
            "technical_insights": [
                "algorithm", "technical", "engineering", "development", "code",
                "programming", "system", "architecture", "optimization", "performance"
            ],
            "business_analysis": [
                "business", "market", "economy", "profit", "revenue", "company",
                "strategy", "investment", "growth", "competition"
            ],
            "social_commentary": [
                "society", "culture", "politics", "social", "community", "impact",
                "change", "movement", "rights", "justice", "decolonization"
            ]
        }
    
    def get_completed_episodes(self) -> List[Dict]:
        """Retrieve all completed episodes from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT id, title, status, transcript_path, episode_id
            FROM episodes 
            WHERE status = 'completed'
            ORDER BY id
            """
            
            cursor.execute(query)
            episodes = []
            
            for row in cursor.fetchall():
                episodes.append({
                    'id': row[0],
                    'title': row[1],
                    'status': row[2],
                    'transcript_path': row[3],
                    'audio_file_id': row[4]  # Keep the same key name for consistency
                })
            
            conn.close()
            logger.info(f"Retrieved {len(episodes)} completed episodes from database")
            return episodes
            
        except Exception as e:
            logger.error(f"Error retrieving episodes: {e}")
            return []
    
    def load_transcript(self, transcript_path: str) -> str:
        """Load transcript content from file"""
        transcript_file = Path(transcript_path)
        
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"Loaded transcript: {transcript_file}")
            return content
        except Exception as e:
            logger.error(f"Error loading transcript {transcript_file}: {e}")
            return ""
    
    def classify_topic(self, title: str, content: str) -> Set[str]:
        """Classify content into topic categories"""
        topics = set()
        text_to_analyze = f"{title} {content}".lower()
        
        for category, keywords in self.topic_categories.items():
            for keyword in keywords:
                if keyword.lower() in text_to_analyze:
                    topics.add(category)
                    break
        
        # If no topics found, classify as 'general'
        if not topics:
            topics.add('general')
            
        return topics
    
    def detect_cross_references(self, episodes: List[Dict]) -> Dict[str, List[str]]:
        """Detect topic overlaps between episodes"""
        cross_refs = {}
        episode_topics = {}
        
        # First pass: classify all episodes
        for episode in episodes:
            content = self.load_transcript(episode['transcript_path'])
            if content:
                topics = self.classify_topic(episode['title'], content)
                episode_topics[episode['id']] = {
                    'title': episode['title'],
                    'topics': topics,
                    'content_preview': content[:500].replace('\n', ' ')
                }
        
        # Second pass: find cross-references
        for topic_category in self.topic_categories.keys():
            related_episodes = []
            for episode_id, data in episode_topics.items():
                if topic_category in data['topics']:
                    related_episodes.append({
                        'id': episode_id,
                        'title': data['title'],
                        'preview': data['content_preview']
                    })
            
            if len(related_episodes) > 1:
                cross_refs[topic_category] = related_episodes
        
        logger.info(f"Detected cross-references for {len(cross_refs)} topic categories")
        return cross_refs, episode_topics
    
    def generate_digest_prompt(self, cross_refs: Dict, episode_topics: Dict) -> str:
        """Generate Claude Code prompt for daily digest creation"""
        
        # Create episode summaries
        episode_summaries = []
        for episode_id, data in episode_topics.items():
            episode_summaries.append(f"""
**Episode {episode_id}: {data['title']}**
- Topics: {', '.join(data['topics'])}
- Preview: {data['content_preview']}
""")
        
        # Create cross-reference summary
        cross_ref_summary = []
        for topic, episodes in cross_refs.items():
            if len(episodes) > 1:
                episode_list = [f"#{ep['id']}: {ep['title']}" for ep in episodes]
                cross_ref_summary.append(f"""
**{topic.replace('_', ' ').title()}** ({len(episodes)} episodes):
{chr(10).join(f'  - {ep}' for ep in episode_list)}
""")
        
        prompt = f"""TASK: Create a comprehensive daily podcast digest from the following {len(episode_topics)} transcribed episodes.

EPISODE SUMMARIES:
{''.join(episode_summaries)}

TOPIC CROSS-REFERENCES:
{''.join(cross_ref_summary)}

INSTRUCTIONS: Generate a structured daily digest using the following format exactly. Do not ask questions - create the digest directly.

# Daily Podcast Digest - {datetime.now().strftime('%B %d, %Y')}

## Executive Summary
[2-3 sentence overview of the day's key themes and insights]

## Topic Highlights

### AI Tools & Technology
[Summarize AI-related content, noting cross-episode connections]

### Product Launches & Announcements  
[Summarize product/launch content, noting cross-episode connections]

### Creative Applications
[Summarize creative/artistic content, noting cross-episode connections]

### Technical Insights
[Summarize technical/engineering content, noting cross-episode connections]

### Business Analysis
[Summarize business/market content, noting cross-episode connections]

### Social Commentary
[Summarize social/cultural content, noting cross-episode connections]

## Cross-Episode Connections
[Identify and explain thematic connections between episodes]

## Key Takeaways
[5-7 bullet points of the most important insights across all episodes]

## Recommended Deep Dives
[Suggest 2-3 episodes for detailed listening based on current trends]

---
Generated from {len(episode_topics)} podcast episodes | {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        
        return prompt
    
    def call_claude_headless(self, prompt: str) -> str:
        """Call Claude Code in headless mode to generate digest"""
        try:
            logger.info("Calling Claude Code headless mode for digest generation...")
            
            # Write prompt to temporary file
            prompt_file = Path("digest_prompt.txt")
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(prompt)
            
            # Call Claude Code headless
            cmd = [self.claude_binary, "-p", str(prompt_file)]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            # Clean up temp file
            prompt_file.unlink()
            
            if result.returncode == 0:
                logger.info("Successfully generated digest using Claude Code")
                return result.stdout
            else:
                logger.error(f"Claude Code error: {result.stderr}")
                return self.generate_fallback_digest(prompt)
                
        except subprocess.TimeoutExpired:
            logger.error("Claude Code timeout - generating fallback digest")
            return self.generate_fallback_digest(prompt)
        except FileNotFoundError:
            logger.error("Claude Code binary not found - generating fallback digest")
            return self.generate_fallback_digest(prompt)
        except Exception as e:
            logger.error(f"Error calling Claude Code: {e}")
            return self.generate_fallback_digest(prompt)
    
    def generate_fallback_digest(self, original_prompt: str) -> str:
        """Generate a basic digest without Claude Code"""
        logger.info("Generating fallback digest...")
        
        digest = f"""
# Daily Podcast Digest - {datetime.now().strftime('%B %d, %Y')}

## Executive Summary
This digest was generated from podcast transcripts using automated analysis. 
Claude Code headless mode was not available, so this is a basic structural digest.

## Episode Analysis
The following episodes were processed:

{original_prompt.split('EPISODE SUMMARIES:')[1].split('TOPIC CROSS-REFERENCES:')[0]}

## Cross-References
{original_prompt.split('TOPIC CROSS-REFERENCES:')[1].split('Please generate')[0]}

## Note
This is a fallback digest. For full analysis, ensure Claude Code is properly installed and available.

---
Generated as fallback digest | {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        return digest
    
    def save_digest(self, digest_content: str) -> str:
        """Save digest to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        digest_file = Path(f"daily_digest_{timestamp}.md")
        
        try:
            with open(digest_file, 'w', encoding='utf-8') as f:
                f.write(digest_content)
            
            logger.info(f"Digest saved to: {digest_file}")
            return str(digest_file)
            
        except Exception as e:
            logger.error(f"Error saving digest: {e}")
            return ""
    
    def generate_daily_digest(self) -> str:
        """Main method to generate daily digest"""
        logger.info("Starting daily digest generation...")
        
        # Step 1: Get completed episodes
        episodes = self.get_completed_episodes()
        if not episodes:
            logger.error("No completed episodes found")
            return ""
        
        # Step 2: Detect cross-references and organize topics
        cross_refs, episode_topics = self.detect_cross_references(episodes)
        
        # Step 3: Generate Claude Code prompt
        prompt = self.generate_digest_prompt(cross_refs, episode_topics)
        
        # Step 4: Call Claude Code headless mode
        digest_content = self.call_claude_headless(prompt)
        
        # Step 5: Save digest
        digest_file = self.save_digest(digest_content)
        
        if digest_file:
            logger.info(f"Daily digest generation completed: {digest_file}")
            return digest_file
        else:
            logger.error("Failed to generate daily digest")
            return ""


def main():
    """CLI entry point"""
    generator = DigestGenerator()
    
    print("🎙️  Daily Podcast Digest Generator")
    print("=" * 40)
    
    digest_file = generator.generate_daily_digest()
    
    if digest_file:
        print(f"✅ Digest generated successfully: {digest_file}")
        
        # Display preview
        try:
            with open(digest_file, 'r', encoding='utf-8') as f:
                preview = f.read()[:1000]
            print("\n📖 Preview:")
            print("-" * 40)
            print(preview)
            if len(preview) >= 1000:
                print("\n... (truncated)")
        except Exception as e:
            print(f"❌ Error reading digest preview: {e}")
    else:
        print("❌ Failed to generate digest")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())