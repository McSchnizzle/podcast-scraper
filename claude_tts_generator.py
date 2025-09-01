#!/usr/bin/env python3
"""
Claude-Powered TTS Generator
Consolidated: Claude Code headless analysis + ElevenLabs TTS + Topic Compilation
"""

import os
import json
import sqlite3
import subprocess
import logging
import requests
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
import tempfile

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClaudeTTSGenerator:
    def __init__(self, db_path: str = "podcast_monitor.db", output_dir: str = "daily_digests"):
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.transcripts_dir = Path("transcripts")
        
        # Claude Code settings
        self.claude_cmd = "claude"
        
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
        
        # Enhanced topic detection with weighted keywords
        self.topic_definitions = {
            "ai_tools": {
                "display_name": "AI Tools & Technology",
                "keywords": {
                    "chatgpt": 3, "claude": 3, "gemini": 3, "openai": 3,
                    "artificial intelligence": 2, "machine learning": 2, "llm": 2,
                    "neural network": 2, "gpt": 2, "ai tool": 2,
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

    def find_most_recent_digest(self) -> Optional[Tuple[str, str]]:
        """Find the most recent digest file and extract its content and timestamp
        
        Returns:
            Tuple of (digest_content, timestamp) or None if no digest found
        """
        try:
            digest_files = list(self.output_dir.glob("daily_digest_*.md"))
            if not digest_files:
                logger.warning("No digest files found in daily_digests directory")
                return None
            
            # Sort by filename (which includes timestamp) to get most recent
            most_recent_file = sorted(digest_files, key=lambda x: x.name)[-1]
            
            # Extract timestamp from filename: daily_digest_20250901_013235.md
            timestamp_match = re.search(r'daily_digest_(\d{8}_\d{6})\.md', most_recent_file.name)
            if not timestamp_match:
                logger.error(f"Could not extract timestamp from filename: {most_recent_file.name}")
                return None
            
            timestamp = timestamp_match.group(1)
            
            # Read the digest content
            with open(most_recent_file, 'r', encoding='utf-8') as f:
                digest_content = f.read()
            
            logger.info(f"📄 Found recent digest: {most_recent_file.name} (timestamp: {timestamp})")
            return digest_content, timestamp
            
        except Exception as e:
            logger.error(f"Error finding recent digest: {e}")
            return None

    # ======================
    # TOPIC COMPILATION METHODS
    # ======================
    
    def get_processed_episodes(self, status_filter: str = 'digested') -> List[Dict]:
        """Get episodes ready for topic compilation"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT id, title, transcript_path, episode_id, published_date, priority_score
            FROM episodes 
            WHERE status = ? AND transcript_path IS NOT NULL
            ORDER BY published_date DESC
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
            return episodes
            
        except Exception as e:
            logger.error(f"Error fetching episodes: {e}")
            return []

    def analyze_topic_relevance(self, content: str) -> Dict[str, float]:
        """Calculate weighted topic scores for content"""
        content_lower = content.lower()
        topic_scores = {}
        
        for topic_id, topic_info in self.topic_definitions.items():
            score = 0.0
            keywords = topic_info['keywords']
            
            for keyword, weight in keywords.items():
                # Count occurrences and apply weight
                occurrences = content_lower.count(keyword.lower())
                score += occurrences * weight
            
            # Normalize by content length (per 1000 characters)
            normalized_score = (score / max(len(content), 1)) * 1000
            topic_scores[topic_id] = normalized_score
        
        return topic_scores

    def compile_topics_from_episodes(self, episodes: List[Dict]) -> Dict[str, Dict]:
        """Organize episodes by dominant topics with cross-references"""
        topic_episodes = defaultdict(list)
        episode_topics = {}
        
        for episode in episodes:
            transcript_path = episode['transcript_path']
            
            if not Path(transcript_path).exists():
                logger.warning(f"Transcript not found: {transcript_path}")
                continue
            
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Analyze topic relevance
                topic_scores = self.analyze_topic_relevance(content)
                
                # Find dominant topic (minimum threshold: 1.0)
                dominant_topic = max(topic_scores.items(), key=lambda x: x[1])
                
                if dominant_topic[1] >= 1.0:  # Minimum relevance threshold
                    topic_id = dominant_topic[0]
                    topic_episodes[topic_id].append({
                        **episode,
                        'topic_score': dominant_topic[1],
                        'all_topic_scores': topic_scores,
                        'transcript_content': content[:2000]  # First 2000 chars for context
                    })
                    episode_topics[episode['episode_id']] = topic_id
                
            except Exception as e:
                logger.error(f"Error analyzing episode {episode['episode_id']}: {e}")
                continue
        
        # Sort episodes within each topic by relevance score
        for topic_id in topic_episodes:
            topic_episodes[topic_id].sort(key=lambda x: x['topic_score'], reverse=True)
        
        return dict(topic_episodes), episode_topics

    # ======================
    # CLAUDE INTEGRATION METHODS
    # ======================

    def get_transcripts_for_claude(self) -> List[Dict]:
        """Get transcript data for Claude analysis"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Only get episodes with status='transcribed' to match pipeline behavior
            query = """
            SELECT id, title, transcript_path, episode_id, published_date, status
            FROM episodes 
            WHERE transcript_path IS NOT NULL 
            AND status = 'transcribed'
            AND published_date >= date('now', '-7 days')
            ORDER BY published_date DESC
            LIMIT 10
            """
            
            logger.info(f"Executing query: {query}")
            cursor.execute(query)
            transcripts = []
            
            all_rows = cursor.fetchall()
            logger.info(f"Query returned {len(all_rows)} rows")
            
            for row in all_rows:
                episode_id, title, transcript_path, episode_id_field, published_date, status = row
                logger.info(f"Processing episode {episode_id}: '{title}' (status: {status}, transcript: {transcript_path})")
                
                if transcript_path and Path(transcript_path).exists():
                    transcripts.append({
                        'id': episode_id,
                        'title': title,
                        'transcript_path': transcript_path,
                        'episode_id': episode_id_field,
                        'published_date': published_date
                    })
                    logger.info(f"✅ Added episode {episode_id} to transcripts list")
                else:
                    logger.warning(f"❌ Transcript file not found for episode {episode_id}: {transcript_path}")
            
            conn.close()
            logger.info(f"Found {len(transcripts)} transcripts for Claude analysis")
            return transcripts
            
        except Exception as e:
            logger.error(f"Error fetching transcripts: {e}")
            return []

    def create_claude_prompt(self, transcripts: List[Dict]) -> str:
        """Create optimized prompt for Claude digest generation"""
        prompt_sections = []
        
        prompt_sections.append("Generate a comprehensive daily podcast digest from these transcripts:")
        prompt_sections.append("")
        
        for i, transcript in enumerate(transcripts, 1):
            transcript_path = transcript['transcript_path']
            title = transcript['title']
            
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                prompt_sections.append(f"## Episode {i}: {title}")
                prompt_sections.append(content)
                prompt_sections.append("")
                
            except Exception as e:
                logger.error(f"Error reading transcript {transcript_path}: {e}")
                continue
        
        # Add specific instructions for digest generation
        prompt_sections.extend([
            "---",
            "",
            "Create a daily digest following this format:",
            "",
            "# Daily Podcast Digest - {current_date}",
            "",
            "## Key Topics",
            "- Organize content by themes, not individual episodes",
            "- Focus on actionable insights and key announcements", 
            "- Cross-reference related topics between episodes",
            "",
            "## Important Developments",
            "- Product launches and announcements",
            "- Technology breakthroughs",
            "- Industry trends and analysis",
            "",
            "## Notable Quotes",
            "- Include 2-3 most impactful quotes with context",
            "",
            "Requirements:",
            "- Write for audio consumption (conversational tone)",
            "- Keep total length under 1500 words",
            "- Focus on information that would be valuable to tech professionals",
            "- Use topic-based organization, not episode-by-episode summaries"
        ])
        
        return "\n".join(prompt_sections)

    def run_claude_analysis(self, prompt: str) -> Optional[str]:
        """Execute Claude analysis using headless integration"""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                temp_file = f.name
            
            logger.info("🤖 Running Claude analysis for digest generation...")
            
            cmd = [
                self.claude_cmd, 
                'headless', 
                '--prompt-file', temp_file,
                '--output-format', 'text'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            os.unlink(temp_file)
            
            if result.returncode == 0:
                digest_content = result.stdout.strip()
                if digest_content:
                    logger.info("✅ Claude analysis completed successfully")
                    return digest_content
                else:
                    logger.error("Claude analysis returned empty content")
                    return None
            else:
                logger.error(f"Claude analysis failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Claude analysis timed out")
            return None
        except Exception as e:
            logger.error(f"Error running Claude analysis: {e}")
            return None

    # ======================
    # TTS GENERATION METHODS
    # ======================

    def _optimize_for_tts(self, text: str) -> str:
        """Optimize text content for TTS generation"""
        # Remove markdown headers and formatting
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        # Convert bullet points to spoken format
        text = re.sub(r'^\s*[-*]\s+', 'Next, ', text, flags=re.MULTILINE)
        
        # Add pauses after sections
        text = re.sub(r'\n\n', '\n\n... \n\n', text)
        
        # Replace URLs with "link available"
        text = re.sub(r'https?://[^\s]+', 'link available', text)
        
        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = ' '.join(text.split())
        
        return text.strip()

    def generate_tts_audio(self, text: str, voice_config: Dict, filename: str) -> Optional[str]:
        """Generate audio using ElevenLabs TTS"""
        if not self.elevenlabs_api_key:
            logger.warning("No ElevenLabs API key - skipping TTS generation")
            return None
        
        try:
            url = f"{self.base_url}/text-to-speech/{voice_config['voice_id']}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }
            
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": voice_config.get("stability", 0.75),
                    "similarity_boost": voice_config.get("similarity_boost", 0.75),
                    "style": voice_config.get("style", 0.20)
                }
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=120)
            
            if response.status_code == 200:
                audio_path = self.output_dir / f"{filename}.mp3"
                with open(audio_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"🎵 Generated TTS audio: {audio_path.name}")
                return str(audio_path)
            else:
                logger.error(f"TTS generation failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating TTS audio: {e}")
            return None

    def generate_complete_digest_audio(self, digest_content: str, timestamp: str = None) -> Optional[str]:
        """Generate complete audio digest with metadata
        
        Args:
            digest_content: The digest content to convert to audio
            timestamp: Optional timestamp to use for consistent naming (if None, generates new one)
        """
        if not digest_content:
            logger.error("No digest content to convert")
            return None
        
        # Use provided timestamp or generate new one for consistent naming
        if timestamp is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            logger.info(f"🕐 Generated new timestamp: {timestamp}")
        else:
            logger.info(f"🕐 Using provided timestamp: {timestamp}")
        
        # ALWAYS save the full human-readable script first
        full_script_path = self.output_dir / f"claude_digest_full_{timestamp}.txt"
        with open(full_script_path, 'w', encoding='utf-8') as f:
            f.write(digest_content)
        
        logger.info(f"📝 Full digest script saved: {full_script_path.name}")
        
        # Optimize content for TTS
        tts_optimized = self._optimize_for_tts(digest_content)
        
        # Also save the TTS-optimized version for debugging
        tts_script_path = self.output_dir / f"claude_digest_tts_{timestamp}.txt"
        with open(tts_script_path, 'w', encoding='utf-8') as f:
            f.write(tts_optimized)
        
        logger.info(f"📝 TTS-optimized script saved: {tts_script_path.name}")
        
        # Generate audio file
        audio_path = self.output_dir / f"complete_topic_digest_{timestamp}.mp3"
        
        # Use professional host voice
        host_voice = self.voice_config["intro_outro"]
        
        generated_audio = self.generate_tts_audio(
            tts_optimized, 
            host_voice, 
            f"complete_topic_digest_{timestamp}"
        )
        
        if generated_audio:
            # Generate metadata
            metadata_path = self.output_dir / f"complete_topic_digest_{timestamp}.json"
            metadata = {
                "title": f"Daily Tech Digest - {datetime.now().strftime('%B %d, %Y')}",
                "description": "Daily digest of tech news and insights from leading podcasts and creators",
                "generation_time": datetime.now().isoformat(),
                "content_length": len(digest_content),
                "tts_optimized_length": len(tts_optimized),
                "audio_file": audio_path.name,
                "full_script_file": full_script_path.name,
                "tts_script_file": tts_script_path.name
            }
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"📊 Metadata saved: {metadata_path.name}")
            return str(audio_path)
        
        return None

    # ======================
    # MAIN WORKFLOW METHODS
    # ======================

    def generate_daily_digest(self) -> Optional[str]:
        """Generate TTS audio from existing digest file"""
        logger.info("🚀 Starting TTS generation from existing digest")
        
        # Step 1: Find the most recent digest file
        digest_result = self.find_most_recent_digest()
        if not digest_result:
            logger.error("No existing digest file found - TTS generation requires pre-existing digest")
            return None
        
        digest_content, timestamp = digest_result
        logger.info("✅ Found existing digest content")
        
        # Step 2: Generate TTS audio using the existing digest content and timestamp
        audio_path = self.generate_complete_digest_audio(digest_content, timestamp)
        
        if audio_path:
            logger.info(f"🎵 TTS audio generated successfully: {audio_path}")
            return audio_path
        else:
            logger.error("❌ TTS audio generation failed")
            return None

if __name__ == "__main__":
    generator = ClaudeTTSGenerator()
    result = generator.generate_daily_digest()
    
    if result:
        print(f"✅ Daily digest generated: {result}")
    else:
        print("❌ Daily digest generation failed")