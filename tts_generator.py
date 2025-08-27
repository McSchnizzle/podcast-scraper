#!/usr/bin/env python3
"""
TTS Generation System for Daily Podcast Digest
Phase 3: ElevenLabs Integration with Topic-Based Compilation
"""

import os
import json
import sqlite3
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import time
import re

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not available - using system environment only")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TTSGenerator:
    def __init__(self, 
                 db_path: str = "podcast_monitor.db",
                 transcripts_dir: str = "transcripts",
                 audio_output_dir: str = "daily_digests"):
        
        self.db_path = db_path
        self.transcripts_dir = Path(transcripts_dir)
        self.audio_output_dir = Path(audio_output_dir)
        self.audio_output_dir.mkdir(exist_ok=True)
        
        # ElevenLabs configuration
        self.elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY')
        if not self.elevenlabs_api_key:
            logger.warning("ELEVENLABS_API_KEY not found in environment")
        
        self.base_url = "https://api.elevenlabs.io/v1"
        
        # Voice configurations for different topics
        self.voice_config = {
            "ai_tools": {
                "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel - clear, professional
                "stability": 0.75,
                "similarity_boost": 0.75,
                "style": 0.15
            },
            "product_launches": {
                "voice_id": "AZnzlk1XvdvUeBnXmlld",  # Domi - energetic, engaging
                "stability": 0.70,
                "similarity_boost": 0.80,
                "style": 0.25
            },
            "creative_applications": {
                "voice_id": "EXAVITQu4vr4xnSDxMaL",  # Bella - warm, creative
                "stability": 0.65,
                "similarity_boost": 0.75,
                "style": 0.35
            },
            "technical_insights": {
                "voice_id": "ErXwobaYiN019PkySvjV",  # Antoni - authoritative
                "stability": 0.80,
                "similarity_boost": 0.70,
                "style": 0.10
            },
            "business_analysis": {
                "voice_id": "VR6AewLTigWG4xSOukaG",  # Arnold - confident
                "stability": 0.85,
                "similarity_boost": 0.75,
                "style": 0.20
            },
            "social_commentary": {
                "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam - thoughtful
                "stability": 0.75,
                "similarity_boost": 0.80,
                "style": 0.30
            },
            "intro_outro": {
                "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel - consistent host voice
                "stability": 0.85,
                "similarity_boost": 0.75,
                "style": 0.20
            }
        }
        
        # Topic categories aligned with manual_digest_generator.py
        self.topic_categories = {
            "ai_tools": {
                "keywords": ["chatgpt", "claude", "gemini", "ai tool", "artificial intelligence", 
                           "machine learning", "neural network", "gpt", "llm", "automation"],
                "episodes": [],
                "display_name": "AI Tools & Technology"
            },
            "product_launches": {
                "keywords": ["launch", "release", "announcement", "new product", "google pixel",
                           "event", "unveil", "debut", "introduce", "rollout"],
                "episodes": [],
                "display_name": "Product Launches & Announcements"
            },
            "creative_applications": {
                "keywords": ["creative", "art", "design", "music", "video", "content creation",
                           "remix", "tiny desk", "kurt cobain", "notorious", "veo", "editing"],
                "episodes": [],
                "display_name": "Creative Applications"
            },
            "technical_insights": {
                "keywords": ["algorithm", "technical", "engineering", "development", "code",
                           "programming", "system", "architecture", "optimization"],
                "episodes": [],
                "display_name": "Technical Insights"
            },
            "business_analysis": {
                "keywords": ["business", "market", "economy", "profit", "revenue", "company",
                           "strategy", "investment", "growth", "competition"],
                "episodes": [],
                "display_name": "Business Analysis"
            },
            "social_commentary": {
                "keywords": ["society", "culture", "politics", "social", "community", "impact",
                           "decolonization", "rights", "justice", "movement"],
                "episodes": [],
                "display_name": "Social Commentary"
            }
        }

    def get_digested_episodes(self, days_back: int = 1) -> List[Dict]:
        """Get episodes ready for TTS generation"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT id, title, transcript_path, episode_id, published_date
            FROM episodes 
            WHERE status = 'digested'
            ORDER BY published_date DESC
            """
            
            cursor.execute(query)
            episodes = []
            
            for row in cursor.fetchall():
                episodes.append({
                    'id': row[0],
                    'title': row[1],
                    'transcript_path': row[2],
                    'episode_id': row[3],
                    'published_date': row[4]
                })
            
            conn.close()
            logger.info(f"Retrieved {len(episodes)} digested episodes")
            return episodes
            
        except Exception as e:
            logger.error(f"Error retrieving episodes: {e}")
            return []

    def load_transcript(self, transcript_path: str) -> str:
        """Load and clean transcript content"""
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            logger.error(f"Error loading transcript {transcript_path}: {e}")
            return ""

    def categorize_episodes(self, episodes: List[Dict]) -> Dict:
        """Categorize episodes by topics for TTS compilation"""
        
        # Reset episode lists
        for category in self.topic_categories:
            self.topic_categories[category]["episodes"] = []
        
        categorized = {
            "topics": {},
            "uncategorized": []
        }
        
        for episode in episodes:
            content = self.load_transcript(episode['transcript_path'])
            if not content:
                continue
            
            # Analyze content for topic classification
            text_to_analyze = f"{episode['title']} {content}".lower()
            
            episode_topics = []
            for category, data in self.topic_categories.items():
                for keyword in data["keywords"]:
                    if keyword.lower() in text_to_analyze:
                        episode_topics.append(category)
                        data["episodes"].append({
                            'id': episode['id'],
                            'title': episode['title'],
                            'content': content,
                            'preview': content[:500].replace('\n', ' ') + "..."
                        })
                        break
            
            if episode_topics:
                for topic in episode_topics:
                    if topic not in categorized["topics"]:
                        categorized["topics"][topic] = []
                    categorized["topics"][topic].append(episode)
            else:
                categorized["uncategorized"].append(episode)
        
        # Filter topics with episodes
        categorized["topics"] = {k: v for k, v in categorized["topics"].items() if v}
        
        logger.info(f"Categorized {len(episodes)} episodes into {len(categorized['topics'])} topics")
        return categorized

    def generate_tts_script(self, categorized_episodes: Dict) -> str:
        """Generate TTS-optimized script with emphasis markers"""
        
        script_parts = []
        
        # Introduction
        total_episodes = sum(len(eps) for eps in categorized_episodes["topics"].values())
        total_episodes += len(categorized_episodes["uncategorized"])
        
        intro = f"""
[INTRO_MUSIC_FADE_IN]

Welcome to your Daily Podcast Digest for {datetime.now().strftime('%B %d, %Y')}.

[INTRO_MUSIC_FADE_OUT]

Today's digest synthesizes insights from {total_episodes} podcast episodes, 
organized by key themes rather than individual shows. Let's dive into the most 
important developments across technology, creativity, and society.

[PAUSE:2000]
"""
        script_parts.append(intro.strip())
        
        # Process each topic
        for topic_key, episodes in categorized_episodes["topics"].items():
            if not episodes:
                continue
                
            topic_data = self.topic_categories[topic_key]
            topic_name = topic_data["display_name"]
            
            # Topic introduction
            topic_intro = f"""
[TOPIC_TRANSITION_MUSIC]

## {topic_name}

[MUSIC_FADE_OUT]

In {topic_name.lower()}, we're seeing significant developments 
across {len(episodes)} episodes. Here are the key insights:

[PAUSE:1500]
"""
            script_parts.append(topic_intro.strip())
            
            # Cross-episode synthesis for this topic
            if len(episodes) == 1:
                # Single episode - focus on key points
                episode = episodes[0]
                content = self.load_transcript(episode['transcript_path'])
                synthesis = self._synthesize_single_episode(episode, content, topic_name)
            else:
                # Multiple episodes - cross-episode synthesis
                synthesis = self._synthesize_cross_episodes(episodes, topic_name)
            
            script_parts.append(synthesis)
            
            # Topic conclusion
            topic_outro = f"""
[PAUSE:1000]

That's our synthesis of {topic_name.lower()} developments. 

[TOPIC_TRANSITION_PAUSE:500]
"""
            script_parts.append(topic_outro.strip())
        
        # Conclusion
        conclusion = f"""
[CONCLUSION_MUSIC_FADE_IN]

That wraps up today's digest. We've covered {len(categorized_episodes['topics'])} 
key themes from the podcast landscape, synthesizing insights to help you stay 
informed on what matters most.

[PAUSE:1500]

Thanks for listening to your Daily Podcast Digest. 
We'll be back tomorrow with fresh insights.

[OUTRO_MUSIC_FADE_OUT]
"""
        script_parts.append(conclusion.strip())
        
        return "\n\n".join(script_parts)

    def _synthesize_single_episode(self, episode: Dict, content: str, topic_name: str) -> str:
        """Synthesize key points from a single episode"""
        
        # Extract key segments (simplified approach for now)
        sentences = re.split(r'[.!?]+', content)
        key_sentences = [s.strip() for s in sentences if len(s.strip()) > 50][:5]
        
        synthesis = f"""
**From {episode['title']}:**

[EMPHASIS] The main insight here is about {topic_name.lower()} development. [/EMPHASIS]

{' '.join(key_sentences[:3])}

[PAUSE:1000]

This represents a significant shift in how we approach {topic_name.lower()}.
"""
        
        return synthesis

    def _synthesize_cross_episodes(self, episodes: List[Dict], topic_name: str) -> str:
        """Synthesize insights across multiple episodes"""
        
        synthesis = f"""
**Cross-Episode Analysis for {topic_name}:**

[EMPHASIS] We're seeing a clear pattern emerge across {len(episodes)} different sources. [/EMPHASIS]

"""
        
        # Key themes (simplified - in production this would use LLM analysis)
        for i, episode in enumerate(episodes[:3], 1):  # Limit to top 3 for brevity
            title = episode['title']
            synthesis += f"""
{i}. **{title}**: """
            
            content = self.load_transcript(episode['transcript_path'])
            if content:
                # Extract first substantial sentence
                sentences = re.split(r'[.!?]+', content)
                key_sentence = next((s.strip() for s in sentences if len(s.strip()) > 40), "Key insights available.")
                synthesis += f"{key_sentence[:200]}...\n\n"
        
        synthesis += f"""
[PAUSE:1500]

[EMPHASIS] The connecting thread across these discussions is the rapid evolution 
of {topic_name.lower()} and its implications for both creators and consumers. [/EMPHASIS]

[PAUSE:1000]
"""
        
        return synthesis

    def get_available_voices(self) -> Dict:
        """Get available ElevenLabs voices"""
        if not self.elevenlabs_api_key:
            return {}
        
        try:
            headers = {"xi-api-key": self.elevenlabs_api_key}
            response = requests.get(f"{self.base_url}/voices", headers=headers)
            
            if response.status_code == 200:
                voices_data = response.json()
                return {voice["voice_id"]: voice["name"] for voice in voices_data.get("voices", [])}
            else:
                logger.error(f"Failed to get voices: {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting voices: {e}")
            return {}

    def generate_audio_segment(self, text: str, voice_config: Dict, output_path: str) -> bool:
        """Generate audio using ElevenLabs TTS"""
        
        if not self.elevenlabs_api_key:
            logger.error("ElevenLabs API key not configured")
            return False
        
        try:
            # Clean TTS markers from text
            clean_text = self._clean_tts_markers(text)
            
            url = f"{self.base_url}/text-to-speech/{voice_config['voice_id']}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }
            
            data = {
                "text": clean_text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": voice_config.get("stability", 0.75),
                    "similarity_boost": voice_config.get("similarity_boost", 0.75),
                    "style": voice_config.get("style", 0.20),
                    "use_speaker_boost": True
                }
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=180)
            
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Generated audio segment: {output_path}")
                return True
            else:
                logger.error(f"TTS generation failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            return False

    def _clean_tts_markers(self, text: str) -> str:
        """Remove TTS markers and optimize for speech synthesis"""
        
        # Remove audio cues
        text = re.sub(r'\[.*?\]', '', text)
        
        # Handle emphasis markers
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove markdown bold
        
        # Clean up formatting
        text = re.sub(r'\n+', '. ', text)  # Replace newlines with periods
        text = re.sub(r'\s+', ' ', text)   # Normalize whitespace
        text = re.sub(r'\.+', '.', text)   # Remove multiple periods
        
        # Add natural pauses
        text = re.sub(r'(\. )([A-Z])', r'\1 \2', text)  # Add space after periods
        
        return text.strip()

    def compile_daily_audio(self, tts_script: str) -> Tuple[bool, str]:
        """Compile daily audio digest from TTS script"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        audio_segments_dir = self.audio_output_dir / f"segments_{timestamp}"
        audio_segments_dir.mkdir(exist_ok=True)
        
        final_audio_path = self.audio_output_dir / f"daily_digest_{timestamp}.mp3"
        
        try:
            # Parse script into segments
            segments = self._parse_script_segments(tts_script)
            
            # Generate audio for each segment
            segment_files = []
            
            for i, segment in enumerate(segments):
                segment_path = audio_segments_dir / f"segment_{i:02d}.mp3"
                
                # Determine voice based on segment type
                voice_config = self._get_voice_for_segment(segment)
                
                if self.generate_audio_segment(segment["text"], voice_config, str(segment_path)):
                    segment_files.append(str(segment_path))
                    
                    # Rate limiting - ElevenLabs free tier has limits
                    time.sleep(1)
                else:
                    logger.warning(f"Failed to generate segment {i}")
            
            if segment_files:
                # Combine audio segments using ffmpeg
                success = self._combine_audio_segments(segment_files, str(final_audio_path))
                
                if success:
                    logger.info(f"Daily audio digest compiled: {final_audio_path}")
                    return True, str(final_audio_path)
                else:
                    return False, ""
            else:
                logger.error("No audio segments generated successfully")
                return False, ""
                
        except Exception as e:
            logger.error(f"Error compiling daily audio: {e}")
            return False, ""

    def _parse_script_segments(self, script: str) -> List[Dict]:
        """Parse TTS script into manageable segments"""
        
        # Split on topic boundaries and music cues
        segments = []
        
        # Simple segmentation for now - split on major sections
        sections = script.split('##')
        
        for i, section in enumerate(sections):
            if not section.strip():
                continue
                
            # Determine segment type
            segment_type = "content"
            if i == 0 or "Welcome to" in section:
                segment_type = "intro"
            elif "wraps up" in section.lower() or "thanks for listening" in section.lower():
                segment_type = "outro"
            
            segments.append({
                "text": section.strip(),
                "type": segment_type,
                "index": i
            })
        
        return segments

    def _get_voice_for_segment(self, segment: Dict) -> Dict:
        """Select appropriate voice configuration for segment"""
        
        segment_text = segment["text"].lower()
        segment_type = segment["type"]
        
        # Intro/outro uses consistent host voice
        if segment_type in ["intro", "outro"]:
            return self.voice_config["intro_outro"]
        
        # Topic-based voice selection
        for topic_key, topic_data in self.topic_categories.items():
            for keyword in topic_data["keywords"]:
                if keyword.lower() in segment_text:
                    return self.voice_config.get(topic_key, self.voice_config["intro_outro"])
        
        # Default voice
        return self.voice_config["intro_outro"]

    def _combine_audio_segments(self, segment_files: List[str], output_path: str) -> bool:
        """Combine audio segments using ffmpeg"""
        
        try:
            # Create file list for ffmpeg
            file_list_path = Path(output_path).parent / "segment_list.txt"
            
            with open(file_list_path, 'w') as f:
                for segment_file in segment_files:
                    f.write(f"file '{segment_file}'\n")
            
            # Use ffmpeg to concatenate
            import subprocess
            
            cmd = [
                'ffmpeg', '-y',  # Overwrite output
                '-f', 'concat',
                '-safe', '0',
                '-i', str(file_list_path),
                '-c', 'copy',
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info(f"Audio segments combined successfully: {output_path}")
                
                # Cleanup temporary files
                file_list_path.unlink()
                for segment_file in segment_files:
                    Path(segment_file).unlink()
                    
                return True
            else:
                logger.error(f"ffmpeg error: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error combining audio segments: {e}")
            return False

    def generate_daily_digest_audio(self) -> Optional[str]:
        """Main method to generate daily TTS audio digest"""
        
        logger.info("Starting TTS daily digest generation...")
        
        # Get episodes ready for TTS
        episodes = self.get_digested_episodes()
        if not episodes:
            logger.error("No digested episodes found for TTS generation")
            return None
        
        # Categorize episodes by topics
        categorized = self.categorize_episodes(episodes)
        
        # Generate TTS script
        tts_script = self.generate_tts_script(categorized)
        
        # Save script for review
        script_path = self.audio_output_dir / f"tts_script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(tts_script)
        
        logger.info(f"TTS script generated: {script_path}")
        
        # Generate audio if API key available
        if self.elevenlabs_api_key:
            success, audio_path = self.compile_daily_audio(tts_script)
            if success:
                return audio_path
            else:
                logger.error("Audio compilation failed")
                return None
        else:
            logger.info("ElevenLabs API key not configured - script generated only")
            return str(script_path)

    def test_tts_generation(self, test_text: str = None) -> bool:
        """Test TTS generation with sample text"""
        
        if not test_text:
            test_text = "This is a test of the TTS generation system for the Daily Podcast Digest."
        
        test_output = self.audio_output_dir / "tts_test.mp3"
        
        # Use default voice for testing
        voice_config = self.voice_config["intro_outro"]
        
        success = self.generate_audio_segment(test_text, voice_config, str(test_output))
        
        if success:
            logger.info(f"TTS test successful: {test_output}")
            return True
        else:
            logger.error("TTS test failed")
            return False


def main():
    """CLI entry point for TTS generation"""
    
    generator = TTSGenerator()
    
    print("🎙️  TTS Daily Digest Generator")
    print("=" * 40)
    
    # Test TTS if API key available
    if generator.elevenlabs_api_key:
        print("Testing ElevenLabs connection...")
        if generator.test_tts_generation():
            print("✅ TTS test successful")
        else:
            print("❌ TTS test failed - check API key and connection")
            return 1
    else:
        print("⚠️  ElevenLabs API key not configured - will generate script only")
    
    # Generate daily digest
    result = generator.generate_daily_digest_audio()
    
    if result:
        print(f"✅ Daily digest generated: {result}")
        return 0
    else:
        print("❌ Failed to generate daily digest")
        return 1


if __name__ == "__main__":
    exit(main())