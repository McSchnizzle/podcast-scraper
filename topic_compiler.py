#!/usr/bin/env python3
"""
Topic-Based Compilation System for TTS Generation
Phase 3: Enhanced cross-episode synthesis and TTS script optimization
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
import re
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TopicCompiler:
    def __init__(self, db_path: str = "podcast_monitor.db", transcripts_dir: str = "transcripts"):
        self.db_path = db_path
        self.transcripts_dir = Path(transcripts_dir)
        
        # Enhanced topic detection with weighted keywords
        self.topic_definitions = {
            "ai_tools": {
                "display_name": "AI Tools & Technology",
                "keywords": {
                    # High weight - definitive indicators
                    "chatgpt": 3, "claude": 3, "gemini": 3, "openai": 3,
                    "artificial intelligence": 2, "machine learning": 2, "llm": 2,
                    "neural network": 2, "gpt": 2, "ai tool": 2,
                    # Medium weight - context dependent  
                    "automation": 1, "algorithm": 1, "ai": 1
                },
                "intro_template": "In AI and technology, we're seeing rapid evolution across {episode_count} episodes.",
                "synthesis_focus": "technological advancement and practical applications"
            },
            "product_launches": {
                "display_name": "Product Launches & Announcements", 
                "keywords": {
                    "google pixel": 3, "product launch": 3, "announcement": 2,
                    "new product": 2, "release": 2, "unveil": 2, "debut": 2,
                    "event": 1, "introduce": 1, "rollout": 1
                },
                "intro_template": "Major product announcements dominated {episode_count} episodes this period.",
                "synthesis_focus": "market impact and consumer implications"
            },
            "creative_applications": {
                "display_name": "Creative Applications",
                "keywords": {
                    "tiny desk": 3, "kurt cobain": 3, "notorious": 3, "creative": 2,
                    "music video": 2, "content creation": 2, "art": 2, "design": 2,
                    "video editing": 2, "remix": 2, "veo": 1, "music": 1
                },
                "intro_template": "Creative innovation takes center stage across {episode_count} episodes.",
                "synthesis_focus": "artistic expression and democratization of creative tools"
            },
            "technical_insights": {
                "display_name": "Technical Deep Dives",
                "keywords": {
                    "engineering": 2, "architecture": 2, "system": 2, "technical": 2,
                    "optimization": 2, "processing": 2, "development": 1,
                    "code": 1, "programming": 1
                },
                "intro_template": "Technical discussions across {episode_count} episodes reveal key implementation insights.",
                "synthesis_focus": "technical innovation and system design"
            },
            "business_analysis": {
                "display_name": "Business & Market Analysis",
                "keywords": {
                    "business model": 3, "market strategy": 3, "revenue": 2, "profit": 2,
                    "investment": 2, "growth": 2, "competition": 2, "economy": 2,
                    "company": 1, "business": 1, "strategy": 1
                },
                "intro_template": "Business implications emerge from {episode_count} episodes of market analysis.",
                "synthesis_focus": "economic impact and strategic positioning"
            },
            "social_commentary": {
                "display_name": "Social & Cultural Commentary",
                "keywords": {
                    "individualism": 3, "social change": 3, "decolonization": 3, "society": 2,
                    "culture": 2, "community": 2, "social": 2, "politics": 2,
                    "rights": 2, "justice": 2, "movement": 1, "impact": 1
                },
                "intro_template": "Social and cultural themes span {episode_count} thoughtful episodes.",
                "synthesis_focus": "societal implications and cultural shifts"
            }
        }
        
    def get_processed_episodes(self, status_filter: str = 'digested') -> List[Dict]:
        """Get episodes ready for topic compilation"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT id, title, transcript_path, episode_id, published_date, priority_score
            FROM episodes 
            WHERE status = ? AND transcript_path IS NOT NULL
            ORDER BY priority_score DESC, published_date DESC
            """
            
            cursor.execute(query, (status_filter,))
            episodes = []
            
            for row in cursor.fetchall():
                episodes.append({
                    'id': row[0],
                    'title': row[1],
                    'transcript_path': row[2],
                    'episode_id': row[3],
                    'published_date': row[4],
                    'priority_score': row[5] or 0.0
                })
            
            conn.close()
            logger.info(f"Retrieved {len(episodes)} episodes for topic compilation")
            return episodes
            
        except Exception as e:
            logger.error(f"Error retrieving episodes: {e}")
            return []

    def analyze_topic_weight(self, text: str, topic_key: str) -> float:
        """Calculate weighted topic relevance score"""
        
        topic_def = self.topic_definitions[topic_key]
        keywords = topic_def["keywords"]
        
        text_lower = text.lower()
        total_weight = 0
        
        for keyword, weight in keywords.items():
            # Count keyword occurrences
            count = text_lower.count(keyword.lower())
            if count > 0:
                # Apply diminishing returns for multiple occurrences
                score = weight * (1 + (count - 1) * 0.3)
                total_weight += score
        
        # Normalize by text length (per 1000 chars)
        text_length = len(text)
        if text_length > 0:
            normalized_weight = (total_weight * 1000) / text_length
        else:
            normalized_weight = 0
        
        return normalized_weight

    def compile_topics(self, episodes: List[Dict]) -> Dict:
        """Compile episodes into topic-based groups with synthesis data"""
        
        compilation = {
            "topics": {},
            "episode_topic_map": {},
            "cross_references": defaultdict(set),
            "synthesis_data": {}
        }
        
        # Analyze each episode for topic relevance
        for episode in episodes:
            content = self._load_transcript_content(episode['transcript_path'])
            if not content:
                continue
            
            # Full text for analysis
            full_text = f"{episode['title']} {content}"
            
            # Calculate topic weights
            episode_topics = {}
            for topic_key in self.topic_definitions:
                weight = self.analyze_topic_weight(full_text, topic_key)
                if weight > 0.5:  # Minimum threshold for topic relevance
                    episode_topics[topic_key] = weight
            
            # Assign episode to strongest topic(s)
            if episode_topics:
                # Sort by weight, take top topics above threshold
                sorted_topics = sorted(episode_topics.items(), key=lambda x: x[1], reverse=True)
                primary_topic = sorted_topics[0][0]
                
                # Initialize topic group if needed
                if primary_topic not in compilation["topics"]:
                    compilation["topics"][primary_topic] = {
                        "episodes": [],
                        "total_weight": 0,
                        "key_themes": set(),
                        "cross_episode_connections": []
                    }
                
                # Add episode to primary topic
                episode_data = {
                    **episode,
                    "content": content,
                    "topic_weight": episode_topics[primary_topic],
                    "secondary_topics": [t for t, w in sorted_topics[1:] if w > 1.0]
                }
                
                compilation["topics"][primary_topic]["episodes"].append(episode_data)
                compilation["topics"][primary_topic]["total_weight"] += episode_topics[primary_topic]
                
                # Track episode mapping
                compilation["episode_topic_map"][episode['id']] = {
                    "primary_topic": primary_topic,
                    "all_topics": list(episode_topics.keys()),
                    "weights": episode_topics
                }
                
                # Identify cross-references
                for topic in episode_topics:
                    compilation["cross_references"][topic].add(episode['id'])
        
        # Generate synthesis data for each topic
        for topic_key, topic_data in compilation["topics"].items():
            compilation["synthesis_data"][topic_key] = self._generate_topic_synthesis(
                topic_key, topic_data
            )
        
        # Convert sets to lists for JSON serialization
        compilation["cross_references"] = {
            k: list(v) for k, v in compilation["cross_references"].items()
        }
        
        logger.info(f"Compiled {len(episodes)} episodes into {len(compilation['topics'])} topics")
        return compilation

    def _load_transcript_content(self, transcript_path: str) -> str:
        """Load and clean transcript content"""
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            logger.error(f"Error loading transcript {transcript_path}: {e}")
            return ""

    def _generate_topic_synthesis(self, topic_key: str, topic_data: Dict) -> Dict:
        """Generate synthesis data for a topic group"""
        
        episodes = topic_data["episodes"]
        topic_def = self.topic_definitions[topic_key]
        
        synthesis = {
            "episode_count": len(episodes),
            "total_content_length": sum(len(ep["content"]) for ep in episodes),
            "avg_priority": sum(ep["priority_score"] for ep in episodes) / len(episodes) if episodes else 0,
            "key_insights": [],
            "connecting_themes": [],
            "recommended_focus": "",
            "tts_emphasis_points": []
        }
        
        if len(episodes) == 1:
            # Single episode synthesis
            episode = episodes[0]
            synthesis["key_insights"] = self._extract_single_episode_insights(episode, topic_def)
            synthesis["recommended_focus"] = f"Deep dive into {episode['title']}"
            
        else:
            # Multi-episode synthesis
            synthesis["key_insights"] = self._extract_cross_episode_insights(episodes, topic_def)
            synthesis["connecting_themes"] = self._identify_connecting_themes(episodes)
            synthesis["recommended_focus"] = f"Cross-episode analysis of {topic_def['synthesis_focus']}"
        
        # Generate TTS emphasis points
        synthesis["tts_emphasis_points"] = self._generate_tts_emphasis(synthesis, topic_def)
        
        return synthesis

    def _extract_single_episode_insights(self, episode: Dict, topic_def: Dict) -> List[str]:
        """Extract key insights from a single episode"""
        
        content = episode["content"]
        title = episode["title"]
        
        insights = []
        
        # Extract sentences with high keyword density
        sentences = re.split(r'[.!?]+', content)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 50:  # Skip very short sentences
                continue
                
            # Calculate keyword density for this sentence
            weight = 0
            for keyword, keyword_weight in topic_def["keywords"].items():
                if keyword.lower() in sentence.lower():
                    weight += keyword_weight
            
            if weight > 2:  # High relevance threshold
                insights.append(sentence[:200] + "..." if len(sentence) > 200 else sentence)
        
        return insights[:5]  # Top 5 insights

    def _extract_cross_episode_insights(self, episodes: List[Dict], topic_def: Dict) -> List[str]:
        """Extract insights across multiple episodes"""
        
        insights = []
        
        # Analyze common themes across episodes
        all_content = " ".join([ep["content"] for ep in episodes])
        
        # Find frequently mentioned concepts
        word_freq = defaultdict(int)
        words = re.findall(r'\b[a-zA-Z]{4,}\b', all_content.lower())
        
        for word in words:
            if word in [kw.lower().replace(" ", "") for kw in topic_def["keywords"]]:
                word_freq[word] += 1
        
        # Generate cross-episode insights
        if len(episodes) >= 2:
            insights.append(f"Consistent themes emerge across {len(episodes)} different sources")
            
            # Find titles with common elements
            titles = [ep["title"] for ep in episodes]
            common_words = self._find_common_title_words(titles)
            if common_words:
                insights.append(f"Common focus areas include: {', '.join(common_words[:3])}")
        
        return insights

    def _find_common_title_words(self, titles: List[str]) -> List[str]:
        """Find words that appear in multiple episode titles"""
        
        word_counts = defaultdict(int)
        
        for title in titles:
            words = re.findall(r'\b[a-zA-Z]{4,}\b', title.lower())
            unique_words = set(words)  # Avoid double-counting within same title
            
            for word in unique_words:
                word_counts[word] += 1
        
        # Return words that appear in multiple titles
        common_words = [word for word, count in word_counts.items() if count >= 2]
        return sorted(common_words, key=lambda w: word_counts[w], reverse=True)

    def _identify_connecting_themes(self, episodes: List[Dict]) -> List[str]:
        """Identify themes that connect multiple episodes"""
        
        themes = []
        
        # Simple theme detection based on title and content analysis
        all_titles = " ".join([ep["title"] for ep in episodes]).lower()
        
        # Technology democratization theme
        if any(word in all_titles for word in ["democratiz", "access", "available", "easy"]):
            themes.append("Technology democratization and accessibility")
        
        # Innovation theme
        if any(word in all_titles for word in ["innovat", "breakthrough", "advance", "new"]):
            themes.append("Innovation and technological advancement")
        
        # Market impact theme
        if any(word in all_titles for word in ["market", "impact", "change", "transform"]):
            themes.append("Market transformation and industry impact")
        
        return themes

    def _generate_tts_emphasis(self, synthesis: Dict, topic_def: Dict) -> List[str]:
        """Generate emphasis points for TTS script"""
        
        emphasis_points = []
        
        episode_count = synthesis["episode_count"]
        
        if episode_count == 1:
            emphasis_points.append("This episode provides deep insights into the topic")
        else:
            emphasis_points.append(f"The consensus across {episode_count} sources is significant")
        
        if synthesis["avg_priority"] > 0.7:
            emphasis_points.append("This represents a high-priority development")
        
        if synthesis["connecting_themes"]:
            emphasis_points.append("Multiple connecting themes emerge from this analysis")
        
        return emphasis_points

    def generate_tts_optimized_compilation(self, episodes: List[Dict]) -> Dict:
        """Generate TTS-optimized topic compilation"""
        
        compilation = self.compile_topics(episodes)
        
        # Enhance for TTS optimization
        tts_compilation = {
            "metadata": {
                "generation_time": datetime.now().isoformat(),
                "total_episodes": len(episodes),
                "topics_covered": len(compilation["topics"]),
                "estimated_audio_duration": self._estimate_audio_duration(compilation)
            },
            "script_structure": self._generate_script_structure(compilation),
            "topics": {}
        }
        
        # Process each topic for TTS
        for topic_key, topic_data in compilation["topics"].items():
            if not topic_data["episodes"]:
                continue
                
            tts_compilation["topics"][topic_key] = {
                "display_name": self.topic_definitions[topic_key]["display_name"],
                "episode_count": len(topic_data["episodes"]),
                "synthesis": compilation["synthesis_data"][topic_key],
                "tts_script": self._generate_topic_tts_script(topic_key, topic_data, compilation["synthesis_data"][topic_key]),
                "voice_instructions": self._generate_voice_instructions(topic_key),
                "estimated_duration": self._estimate_topic_duration(topic_data)
            }
        
        return tts_compilation

    def _estimate_audio_duration(self, compilation: Dict) -> str:
        """Estimate total audio duration in minutes"""
        
        # Rough estimation: 150 words per minute average speech
        total_chars = 0
        
        for topic_data in compilation["topics"].values():
            for episode in topic_data["episodes"]:
                total_chars += len(episode["content"])
        
        # Convert to estimated words (avg 5 chars per word)
        estimated_words = total_chars / 5
        estimated_minutes = estimated_words / 150
        
        return f"{estimated_minutes:.1f} minutes"

    def _estimate_topic_duration(self, topic_data: Dict) -> str:
        """Estimate duration for a single topic"""
        
        total_chars = sum(len(ep["content"]) for ep in topic_data["episodes"])
        estimated_words = total_chars / 5
        estimated_minutes = estimated_words / 150
        
        # Add time for transitions and emphasis
        adjusted_minutes = estimated_minutes * 0.3 + 1  # 30% of content + 1 min for structure
        
        return f"{adjusted_minutes:.1f} minutes"

    def _generate_script_structure(self, compilation: Dict) -> List[Dict]:
        """Generate overall script structure for TTS"""
        
        structure = [
            {"type": "intro", "duration": "30 seconds", "voice": "host"},
            {"type": "topic_preview", "duration": "45 seconds", "voice": "host"}
        ]
        
        for topic_key in compilation["topics"]:
            if compilation["topics"][topic_key]["episodes"]:
                structure.append({
                    "type": "topic_section",
                    "topic": topic_key,
                    "duration": self._estimate_topic_duration(compilation["topics"][topic_key]),
                    "voice": topic_key
                })
                structure.append({
                    "type": "topic_transition", 
                    "duration": "10 seconds",
                    "voice": "host"
                })
        
        structure.append({"type": "conclusion", "duration": "30 seconds", "voice": "host"})
        
        return structure

    def _generate_topic_tts_script(self, topic_key: str, topic_data: Dict, synthesis: Dict) -> str:
        """Generate TTS script for a specific topic"""
        
        topic_def = self.topic_definitions[topic_key]
        episodes = topic_data["episodes"]
        
        script_parts = []
        
        # Topic introduction
        intro_template = topic_def["intro_template"]
        intro = intro_template.format(episode_count=len(episodes))
        script_parts.append(f"[EMPHASIS]{intro}[/EMPHASIS]")
        
        # Content synthesis
        if len(episodes) == 1:
            # Single episode deep dive
            episode = episodes[0]
            script_parts.append(f"\n**Deep dive from {episode['title']}:**")
            
            # Extract key quotes or insights
            key_content = self._extract_tts_content(episode["content"], max_sentences=4)
            script_parts.append(key_content)
            
        else:
            # Cross-episode synthesis
            script_parts.append(f"\n**Cross-episode synthesis from {len(episodes)} sources:**")
            
            for i, episode in enumerate(episodes[:3], 1):  # Limit for audio length
                key_insight = self._extract_tts_content(episode["content"], max_sentences=2)
                script_parts.append(f"\n{i}. From **{episode['title']}**: {key_insight}")
        
        # Connecting insights
        if synthesis["connecting_themes"]:
            script_parts.append(f"\n[PAUSE:1000]")
            script_parts.append(f"[EMPHASIS]The connecting thread here is {topic_def['synthesis_focus']}.[/EMPHASIS]")
        
        return "\n".join(script_parts)

    def _extract_tts_content(self, content: str, max_sentences: int = 3) -> str:
        """Extract most relevant sentences for TTS"""
        
        sentences = re.split(r'[.!?]+', content)
        
        # Filter sentences by length and quality
        quality_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if 30 <= len(sentence) <= 200:  # Good length for TTS
                # Avoid technical jargon or timestamp artifacts
                if not re.search(r'^\d+:\d+', sentence) and not sentence.startswith('http'):
                    quality_sentences.append(sentence)
        
        # Return top sentences
        return ". ".join(quality_sentences[:max_sentences]) + "."

    def _generate_voice_instructions(self, topic_key: str) -> Dict:
        """Generate voice and delivery instructions for topic"""
        
        instructions = {
            "ai_tools": {
                "tone": "professional and clear",
                "pace": "moderate",
                "emphasis": "technical terms and capabilities"
            },
            "product_launches": {
                "tone": "energetic and engaging", 
                "pace": "slightly faster",
                "emphasis": "product names and key features"
            },
            "creative_applications": {
                "tone": "warm and inspiring",
                "pace": "relaxed",
                "emphasis": "creative achievements and artistic elements"
            },
            "technical_insights": {
                "tone": "authoritative and precise",
                "pace": "measured",
                "emphasis": "technical concepts and implications"
            },
            "business_analysis": {
                "tone": "confident and analytical",
                "pace": "business-appropriate",
                "emphasis": "market implications and strategic points"
            },
            "social_commentary": {
                "tone": "thoughtful and reflective",
                "pace": "deliberate",
                "emphasis": "key social insights and implications"
            }
        }
        
        return instructions.get(topic_key, instructions["ai_tools"])

    def save_compilation(self, compilation: Dict, filename_suffix: str = None) -> str:
        """Save topic compilation to JSON file"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if filename_suffix:
            filename = f"topic_compilation_{timestamp}_{filename_suffix}.json"
        else:
            filename = f"topic_compilation_{timestamp}.json"
        
        output_path = Path(filename)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(compilation, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Topic compilation saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error saving compilation: {e}")
            return ""


def main():
    """CLI entry point for topic compilation"""
    
    compiler = TopicCompiler()
    
    print("🎯 Topic-Based Compilation System")
    print("=" * 40)
    
    # Get processed episodes
    episodes = compiler.get_processed_episodes()
    
    if not episodes:
        print("❌ No digested episodes found")
        return 1
    
    print(f"📊 Processing {len(episodes)} episodes for topic compilation...")
    
    # Generate compilation
    compilation = compiler.generate_tts_optimized_compilation(episodes)
    
    # Save compilation
    output_file = compiler.save_compilation(compilation)
    
    if output_file:
        print(f"✅ Topic compilation generated: {output_file}")
        
        # Display summary
        print(f"\n📈 Summary:")
        print(f"Topics identified: {len(compilation['topics'])}")
        print(f"Estimated audio duration: {compilation['metadata']['estimated_audio_duration']}")
        
        for topic_key, topic_data in compilation["topics"].items():
            print(f"  - {topic_data['display_name']}: {topic_data['episode_count']} episodes")
        
        return 0
    else:
        print("❌ Failed to generate topic compilation")
        return 1


if __name__ == "__main__":
    exit(main())