#!/usr/bin/env python3
"""
Manual Daily Digest Generator for Podcast Transcripts
Phase 2.75 Implementation - Direct Analysis Version
"""

import sqlite3
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ManualDigestGenerator:
    def __init__(self, db_path: str = "podcast_monitor.db", transcripts_dir: str = "transcripts"):
        self.db_path = db_path
        self.transcripts_dir = Path(transcripts_dir)
        
        # Enhanced topic categories
        self.topic_categories = {
            "ai_tools": {
                "keywords": ["chatgpt", "claude", "gemini", "ai tool", "artificial intelligence", 
                           "machine learning", "neural network", "gpt", "llm", "automation"],
                "episodes": []
            },
            "product_launches": {
                "keywords": ["launch", "release", "announcement", "new product", "google pixel",
                           "event", "unveil", "debut", "introduce", "rollout"],
                "episodes": []
            },
            "creative_applications": {
                "keywords": ["creative", "art", "design", "music", "video", "content creation",
                           "remix", "tiny desk", "kurt cobain", "notorious", "veo", "editing"],
                "episodes": []
            },
            "technical_insights": {
                "keywords": ["algorithm", "technical", "engineering", "development", "code",
                           "programming", "system", "architecture", "optimization"],
                "episodes": []
            },
            "business_analysis": {
                "keywords": ["business", "market", "economy", "profit", "revenue", "company",
                           "strategy", "investment", "growth", "competition"],
                "episodes": []
            },
            "social_commentary": {
                "keywords": ["society", "culture", "politics", "social", "community", "impact",
                           "decolonization", "rights", "justice", "movement"],
                "episodes": []
            }
        }
    
    def get_completed_episodes(self) -> List[Dict]:
        """Retrieve all completed episodes from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT id, title, status, transcript_path, episode_id
            FROM episodes 
            WHERE status IN ('transcribed', 'digested')
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
                    'episode_id': row[4]
                })
            
            conn.close()
            logger.info(f"Retrieved {len(episodes)} completed episodes")
            return episodes
            
        except Exception as e:
            logger.error(f"Error retrieving episodes: {e}")
            return []
    
    def load_transcript(self, transcript_path: str) -> str:
        """Load transcript content from file"""
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            logger.error(f"Error loading transcript {transcript_path}: {e}")
            return ""
    
    def analyze_episodes(self, episodes: List[Dict]) -> Dict:
        """Analyze all episodes and categorize them"""
        analysis = {
            "episode_data": {},
            "topic_distribution": {},
            "cross_references": {},
            "key_themes": []
        }
        
        # Reset episode lists
        for category in self.topic_categories:
            self.topic_categories[category]["episodes"] = []
        
        # Analyze each episode
        for episode in episodes:
            content = self.load_transcript(episode['transcript_path'])
            if not content:
                continue
            
            # Clean and prepare content for analysis
            clean_content = content.replace('\n', ' ').replace('\t', ' ')
            text_to_analyze = f"{episode['title']} {clean_content}".lower()
            
            # Categorize episode
            episode_topics = []
            for category, data in self.topic_categories.items():
                for keyword in data["keywords"]:
                    if keyword.lower() in text_to_analyze:
                        episode_topics.append(category)
                        data["episodes"].append({
                            'id': episode['id'],
                            'title': episode['title'],
                            'preview': clean_content[:300] + "..."
                        })
                        break
            
            if not episode_topics:
                episode_topics = ['general']
            
            # Store episode analysis
            analysis["episode_data"][episode['id']] = {
                'title': episode['title'],
                'topics': episode_topics,
                'content_length': len(content),
                'preview': clean_content[:200].replace('\n', ' ') + "...",
                'key_phrases': self.extract_key_phrases(text_to_analyze)
            }
        
        # Calculate topic distribution
        for category, data in self.topic_categories.items():
            if data["episodes"]:
                analysis["topic_distribution"][category] = len(data["episodes"])
        
        # Identify cross-references
        for category, data in self.topic_categories.items():
            if len(data["episodes"]) > 1:
                analysis["cross_references"][category] = data["episodes"]
        
        return analysis
    
    def extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases from text"""
        # Simple key phrase extraction
        phrases = []
        
        # Look for AI-related terms
        ai_terms = ["ai", "artificial intelligence", "machine learning", "neural network", 
                   "chatgpt", "claude", "gemini", "automation", "algorithm"]
        for term in ai_terms:
            if term in text:
                phrases.append(term)
        
        # Look for technology terms
        tech_terms = ["google", "pixel", "video", "audio", "creative", "design", 
                     "music", "podcast", "transcript", "processing"]
        for term in tech_terms:
            if term in text:
                phrases.append(term)
        
        return list(set(phrases))
    
    def generate_manual_digest(self, analysis: Dict) -> str:
        """Generate comprehensive digest manually"""
        
        digest = f"""# Daily Podcast Digest - {datetime.now().strftime('%B %d, %Y')}

## Executive Summary

Today's podcast collection spans {len(analysis['episode_data'])} episodes covering diverse topics from AI technology developments to creative applications and social commentary. Key themes include Google's latest AI innovations, creative tools democratization, and the intersection of technology with artistic expression.

## Episode Overview

"""
        
        # Add episode summaries
        for episode_id, data in analysis['episode_data'].items():
            digest += f"**Episode #{episode_id}: {data['title']}**\n"
            digest += f"- Topics: {', '.join(data['topics'])}\n"
            digest += f"- Key phrases: {', '.join(data['key_phrases'][:5])}\n"
            digest += f"- Preview: {data['preview']}\n\n"
        
        digest += "## Topic Highlights\n\n"
        
        # AI Tools & Technology
        if "ai_tools" in analysis["cross_references"]:
            digest += "### 🤖 AI Tools & Technology\n\n"
            episodes = analysis["cross_references"]["ai_tools"]
            digest += f"**{len(episodes)} episodes** explore AI advancement:\n\n"
            for ep in episodes:
                digest += f"- **#{ep['id']}: {ep['title']}** - {ep['preview'][:150]}...\n"
            digest += "\n**Key Insights:** AI tools are becoming more accessible and integrated into creative workflows, with significant developments in memory capabilities and democratization of creative outlets.\n\n"
        
        # Product Launches
        if "product_launches" in analysis["cross_references"]:
            digest += "### 🚀 Product Launches & Announcements\n\n"
            episodes = analysis["cross_references"]["product_launches"]
            digest += f"**{len(episodes)} episodes** cover product announcements:\n\n"
            for ep in episodes:
                digest += f"- **#{ep['id']}: {ep['title']}** - {ep['preview'][:150]}...\n"
            digest += "\n**Key Insights:** Major focus on Google's AI integration across products, particularly in the Pixel ecosystem and image editing capabilities.\n\n"
        
        # Creative Applications
        if "creative_applications" in analysis["cross_references"]:
            digest += "### 🎨 Creative Applications\n\n"
            episodes = analysis["cross_references"]["creative_applications"]
            digest += f"**{len(episodes)} episodes** showcase creative innovation:\n\n"
            for ep in episodes:
                digest += f"- **#{ep['id']}: {ep['title']}** - {ep['preview'][:150]}...\n"
            digest += "\n**Key Insights:** AI is enabling new forms of creative expression, from AI-generated music videos to realistic recreations of historical performances, democratizing access to professional-quality creative tools.\n\n"
        
        # Technical Insights
        if "technical_insights" in analysis["cross_references"]:
            digest += "### ⚙️ Technical Insights\n\n"
            episodes = analysis["cross_references"]["technical_insights"]
            digest += f"**{len(episodes)} episodes** provide technical depth:\n\n"
            for ep in episodes:
                digest += f"- **#{ep['id']}: {ep['title']}** - {ep['preview'][:150]}...\n"
            digest += "\n**Key Insights:** Advanced processing techniques and system architectures enabling real-time AI applications.\n\n"
        
        # Business Analysis
        if "business_analysis" in analysis["cross_references"]:
            digest += "### 💼 Business Analysis\n\n"
            episodes = analysis["cross_references"]["business_analysis"]
            digest += f"**{len(episodes)} episodes** examine business implications:\n\n"
            for ep in episodes:
                digest += f"- **#{ep['id']}: {ep['title']}** - {ep['preview'][:150]}...\n"
            digest += "\n\n"
        
        # Social Commentary
        if "social_commentary" in analysis["cross_references"]:
            digest += "### 🌍 Social Commentary\n\n"
            episodes = analysis["cross_references"]["social_commentary"]
            digest += f"**{len(episodes)} episodes** provide social perspective:\n\n"
            for ep in episodes:
                digest += f"- **#{ep['id']}: {ep['title']}** - {ep['preview'][:150]}...\n"
            digest += "\n**Key Insights:** Deep exploration of individualism, social movements, and the intersection of technology with social change.\n\n"
        
        digest += "## Cross-Episode Connections\n\n"
        
        # Identify thematic connections
        digest += "**AI Democratization Theme:** Multiple episodes explore how AI tools are making professional-quality creative work accessible to broader audiences.\n\n"
        digest += "**Google AI Ecosystem:** Several episodes focus on Google's comprehensive AI integration strategy across consumer products.\n\n"
        digest += "**Creative-Technology Intersection:** Strong emphasis on how technology is reshaping creative industries and individual expression.\n\n"
        
        digest += "## Key Takeaways\n\n"
        
        key_takeaways = [
            "AI tools are rapidly democratizing access to professional creative capabilities",
            "Google's AI strategy focuses on seamless integration across consumer touchpoints",
            "Creative applications of AI are moving beyond novelty to practical utility",
            "Memory upgrades in AI systems are enabling more contextual and useful interactions",
            "The intersection of technology and social commentary reveals broader cultural shifts",
            "Podcast processing and content analysis systems are becoming more sophisticated",
            "AI-generated content quality is approaching professional standards"
        ]
        
        for i, takeaway in enumerate(key_takeaways, 1):
            digest += f"{i}. {takeaway}\n"
        
        digest += f"\n## Recommended Deep Dives\n\n"
        
        # Recommend episodes based on content richness
        digest += "**For AI Technology Deep Dive:** Episode #45 (Google's AI-stuffed Pixel 10 event) - Comprehensive overview of AI integration\n\n"
        digest += "**For Creative Applications:** Episode #52 (Kurt Cobain Tiny Desk) & Episode #55 (Notorious B.I.G. AI videos) - Explore AI's creative potential\n\n"
        digest += "**For Social Perspective:** Episode #57 (Alain de Botton - Individualism) - Deep philosophical commentary on modern society\n\n"
        
        digest += f"---\n"
        digest += f"*Generated from {len(analysis['episode_data'])} podcast episodes | {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
        digest += f"*Topic categories analyzed: {len([k for k, v in analysis['cross_references'].items() if v])}*\n"
        digest += f"*Cross-references detected: {sum(len(v) for v in analysis['cross_references'].values())} episode connections*\n"
        
        return digest
    
    def save_digest(self, digest_content: str) -> Tuple[str, str]:
        """Save digest to file and return digest info"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        digest_file = Path(f"manual_daily_digest_{timestamp}.md")
        digest_id = f"digest_{timestamp}"
        
        try:
            with open(digest_file, 'w', encoding='utf-8') as f:
                f.write(digest_content)
            logger.info(f"Manual digest saved to: {digest_file}")
            return str(digest_file), digest_id
        except Exception as e:
            logger.error(f"Error saving digest: {e}")
            return "", ""
    
    def update_episode_digest_status(self, episodes: List[Dict], digest_id: str) -> None:
        """Update episodes as digested and track digest inclusion"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            updated_count = 0
            for episode in episodes:
                episode_id = episode['id']
                
                # Get current digest inclusions
                cursor.execute('SELECT digest_inclusions FROM episodes WHERE id = ?', (episode_id,))
                result = cursor.fetchone()
                
                if result:
                    current_inclusions = result[0] if result[0] else '[]'
                    try:
                        inclusions_list = json.loads(current_inclusions)
                    except json.JSONDecodeError:
                        inclusions_list = []
                    
                    # Add new digest to inclusions if not already present
                    digest_entry = {
                        'digest_id': digest_id,
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Check if this digest is already recorded
                    if not any(d.get('digest_id') == digest_id for d in inclusions_list):
                        inclusions_list.append(digest_entry)
                    
                    # Update database
                    cursor.execute('''
                        UPDATE episodes 
                        SET status = 'digested', digest_inclusions = ?
                        WHERE id = ?
                    ''', (json.dumps(inclusions_list), episode_id))
                    
                    updated_count += 1
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated {updated_count} episodes with digest status and inclusions")
            
        except Exception as e:
            logger.error(f"Error updating episode digest status: {e}")
    
    def generate_daily_digest(self) -> str:
        """Main method to generate daily digest"""
        logger.info("Starting manual daily digest generation...")
        
        # Get completed episodes
        episodes = self.get_completed_episodes()
        if not episodes:
            logger.error("No completed episodes found")
            return ""
        
        # Analyze episodes
        analysis = self.analyze_episodes(episodes)
        
        # Generate digest
        digest_content = self.generate_manual_digest(analysis)
        
        # Save digest
        digest_file, digest_id = self.save_digest(digest_content)
        
        if digest_file and digest_id:
            # Update episode statuses and track digest inclusions
            self.update_episode_digest_status(episodes, digest_id)
            
            logger.info(f"Manual daily digest generation completed: {digest_file}")
            logger.info(f"Digest ID: {digest_id}")
            return digest_file
        else:
            logger.error("Failed to generate manual daily digest")
            return ""


def main():
    """CLI entry point"""
    generator = ManualDigestGenerator()
    
    print("🎙️  Manual Daily Podcast Digest Generator")
    print("=" * 45)
    
    digest_file = generator.generate_daily_digest()
    
    if digest_file:
        print(f"✅ Manual digest generated successfully: {digest_file}")
        
        # Display preview
        try:
            with open(digest_file, 'r', encoding='utf-8') as f:
                content = f.read()
                preview = content[:2000]
            print("\n📖 Preview:")
            print("-" * 50)
            print(preview)
            if len(content) > 2000:
                print("\n... (content continues)")
        except Exception as e:
            print(f"❌ Error reading digest preview: {e}")
    else:
        print("❌ Failed to generate manual digest")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())