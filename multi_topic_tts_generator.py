#!/usr/bin/env python3
"""
Multi-Topic TTS Generator
Processes topic-specific digest markdown files and generates corresponding MP3s
"""

import os
import json
import re
import logging
import requests
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Import music integration
try:
    from music_integration import MusicIntegrator
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Music integration not available - TTS will generate without music")
    MusicIntegrator = None

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultiTopicTTSGenerator:
    def __init__(self, output_dir: str = "daily_digests"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # ElevenLabs configuration
        self.elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY')
        if not self.elevenlabs_api_key:
            logger.warning("ELEVENLABS_API_KEY not found in environment - TTS will be skipped")
            self.api_available = False
        else:
            self.api_available = True
        
        self.base_url = "https://api.elevenlabs.io/v1"
        
        # Default voice for unknown topics (must be defined before loading config)
        self.default_voice = {
            "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel
            "voice_settings": {
                "stability": 0.75,
                "similarity_boost": 0.75,
                "style": 0.20
            }
        }
        
        # Load topic-specific voice configurations from topics.json
        self.voice_config = self._load_topic_config()
        
        # Initialize music integrator if available
        self.music_integrator = MusicIntegrator() if MusicIntegrator else None
        if self.music_integrator:
            logger.info("🎵 Music integration enabled")
        else:
            logger.info("🎵 Music integration disabled - TTS only")
    
    def _load_topic_config(self) -> Dict:
        """Load topic configuration from topics.json"""
        try:
            topics_config_path = Path("topics.json")
            if topics_config_path.exists():
                with open(topics_config_path, 'r', encoding='utf-8') as f:
                    topics_config = json.load(f)
                
                # Convert to format expected by TTS generator
                voice_config = {}
                for topic, config in topics_config.items():
                    # Convert topic name to snake_case for internal use
                    topic_key = topic.lower().replace(' ', '_').replace('&', 'and')
                    voice_config[topic_key] = {
                        "voice_id": config.get("voice_id", self.default_voice["voice_id"]),
                        "display_name": config.get("display_name", topic),
                        **config.get("voice_settings", self.default_voice["voice_settings"])
                    }
                
                logger.info(f"✅ Loaded voice config for {len(voice_config)} topics")
                return voice_config
            else:
                logger.warning("topics.json not found, using default voice configuration")
                return self._get_default_voice_config()
        except Exception as e:
            logger.error(f"Error loading topics.json: {e}, using default configuration")
            return self._get_default_voice_config()
    
    def _get_default_voice_config(self) -> Dict:
        """Fallback voice configuration"""
        return {
            "ai_news": {
                "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel - clear, professional
                "display_name": "AI News & Developments",
                "stability": 0.75,
                "similarity_boost": 0.75,
                "style": 0.15
            },
            "tech_product_releases": {
                "voice_id": "AZnzlk1XvdvUeBnXmlld",  # Domi - energetic, engaging
                "display_name": "Tech Product Releases",
                "stability": 0.70,
                "similarity_boost": 0.80,
                "style": 0.25
            },
            "tech_news_and_tech_culture": {
                "voice_id": "EXAVITQu4vr4xnSDxMaL",  # Bella - warm, creative
                "display_name": "Tech News & Culture",
                "stability": 0.65,
                "similarity_boost": 0.75,
                "style": 0.35
            },
            "community_organizing": {
                "voice_id": "ErXwobaYiN019PkySvjV",  # Antoni - authoritative
                "display_name": "Community Organizing",
                "stability": 0.80,
                "similarity_boost": 0.70,
                "style": 0.10
            },
            "social_justice": {
                "voice_id": "VR6AewLTigWG4xSOukaG",  # Arnold - confident
                "display_name": "Social Justice",
                "stability": 0.85,
                "similarity_boost": 0.75,
                "style": 0.20
            },
            "societal_culture_change": {
                "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam - thoughtful
                "display_name": "Societal Culture Change",
                "stability": 0.75,
                "similarity_boost": 0.80,
                "style": 0.30
            }
        }
    
    def find_unprocessed_digests(self) -> List[Dict]:
        """Find topic digest MD files that don't have corresponding MP3s"""
        unprocessed = []
        
        # Pattern for topic-specific digests: {topic}_digest_{timestamp}.md
        topic_pattern = re.compile(r'^([a-zA-Z_]+)_digest_(\d{8}_\d{6})\.md$')
        
        for md_file in self.output_dir.glob("*_digest_*.md"):
            match = topic_pattern.match(md_file.name)
            if not match:
                continue
            
            topic, timestamp_str = match.groups()
            
            # Check if MP3 already exists
            mp3_file = self.output_dir / f"{topic}_digest_{timestamp_str}.mp3"
            if mp3_file.exists():
                continue
            
            # Parse timestamp
            try:
                file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except ValueError:
                logger.warning(f"Invalid timestamp format in {md_file.name}")
                continue
            
            unprocessed.append({
                'topic': topic,
                'timestamp': timestamp_str,
                'date': file_date,
                'md_file': md_file,
                'mp3_file': mp3_file
            })
        
        # Sort by date (oldest first)
        unprocessed.sort(key=lambda x: x['date'])
        return unprocessed
    
    def _optimize_for_tts(self, text: str) -> str:
        """Optimize text content for TTS generation"""
        # Remove markdown headers and formatting
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        # Convert bullet points to spoken format
        text = re.sub(r'^\s*[-*•]\s+', 'Next, ', text, flags=re.MULTILINE)
        
        # Add pauses after sections
        text = re.sub(r'\n\n', '\n\n... \n\n', text)
        
        # Replace URLs with "link available"
        text = re.sub(r'https?://[^\s]+', 'link available', text)
        
        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = ' '.join(text.split())
        
        return text.strip()
    
    def generate_tts_audio(self, text: str, voice_config: Dict, filename: str) -> Optional[str]:
        """Generate TTS audio using ElevenLabs API"""
        if not self.api_available:
            logger.warning(f"⚠️  ElevenLabs API not available - skipping TTS for {filename}")
            return None
        
        try:
            logger.info(f"🎙️  Generating TTS audio: {filename}")
            
            headers = {
                'xi-api-key': self.elevenlabs_api_key,
                'Content-Type': 'application/json'
            }
            
            data = {
                'text': text,
                'model_id': 'eleven_multilingual_v2',
                'voice_settings': {
                    'stability': voice_config.get('stability', 0.75),
                    'similarity_boost': voice_config.get('similarity_boost', 0.75),
                    'style': voice_config.get('style', 0.20),
                    'use_speaker_boost': True
                }
            }
            
            url = f"{self.base_url}/text-to-speech/{voice_config['voice_id']}/stream"
            
            response = requests.post(url, headers=headers, json=data, stream=True, timeout=60)
            response.raise_for_status()
            
            # Save audio to file
            audio_path = self.output_dir / f"{filename}.mp3"
            with open(audio_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = audio_path.stat().st_size
            logger.info(f"✅ TTS audio generated: {filename}.mp3 ({file_size:,} bytes)")
            return str(audio_path)
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ TTS generation timeout for {filename}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ TTS API error for {filename}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error generating TTS for {filename}: {e}")
            return None
    
    def process_digest(self, digest_info: Dict) -> bool:
        """Process a single digest file to generate TTS audio"""
        topic = digest_info['topic']
        timestamp = digest_info['timestamp']
        md_file = digest_info['md_file']
        mp3_file = digest_info['mp3_file']
        
        logger.info(f"🔄 Processing {topic} digest ({timestamp})")
        
        try:
            # Read digest content
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                logger.warning(f"⚠️  Empty content in {md_file.name}")
                return False
            
            # Optimize for TTS
            tts_optimized = self._optimize_for_tts(content)
            
            # Save TTS-optimized version for debugging
            tts_script_path = self.output_dir / f"{topic}_digest_tts_{timestamp}.txt"
            with open(tts_script_path, 'w', encoding='utf-8') as f:
                f.write(tts_optimized)
            
            logger.info(f"📝 TTS-optimized script saved: {tts_script_path.name}")
            
            # Get voice configuration for this topic
            voice_config = self.voice_config.get(topic, self.default_voice.copy())
            if topic not in self.voice_config:
                logger.info(f"⚠️  Using default voice for unknown topic: {topic}")
            
            # Generate audio
            audio_filename = f"{topic}_digest_{timestamp}"
            generated_audio = self.generate_tts_audio(tts_optimized, voice_config, audio_filename)
            
            if generated_audio:
                # Enhance with music if available
                final_audio_path = generated_audio
                if self.music_integrator:
                    try:
                        logger.info(f"🎵 Adding music enhancement for {topic}")
                        enhanced_audio = self.music_integrator.enhance_tts_with_music(generated_audio, topic)
                        if enhanced_audio != generated_audio:
                            # Replace original with enhanced version
                            enhanced_path = Path(enhanced_audio)
                            original_path = Path(generated_audio)
                            enhanced_path.rename(original_path)
                            logger.info(f"✅ Audio enhanced with music")
                        final_audio_path = generated_audio
                    except Exception as e:
                        logger.warning(f"⚠️  Music enhancement failed: {e}, using TTS-only audio")
                
                # Generate metadata
                topic_display = voice_config.get('display_name', topic.replace('_', ' ').title())
                date_display = digest_info['date'].strftime('%B %d, %Y')
                
                metadata_path = self.output_dir / f"{topic}_digest_{timestamp}.json"
                metadata = {
                    "title": f"{topic_display} - {date_display}",
                    "description": f"Daily digest covering {topic_display.lower()}",
                    "topic": topic,
                    "timestamp": timestamp,
                    "date": digest_info['date'].isoformat(),
                    "voice_config": voice_config,
                    "generated_at": datetime.now().isoformat(),
                    "audio_file": f"{audio_filename}.mp3",
                    "markdown_file": md_file.name,
                    "tts_script_file": tts_script_path.name,
                    "music_enhanced": self.music_integrator is not None
                }
                
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)
                
                logger.info(f"📄 Metadata saved: {metadata_path.name}")
                logger.info(f"✅ Successfully processed {topic} digest")
                return True
            else:
                logger.error(f"❌ Failed to generate audio for {topic} digest")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error processing {topic} digest: {e}")
            return False
    
    def process_all_unprocessed(self) -> Tuple[int, int]:
        """Process all unprocessed digest files"""
        unprocessed = self.find_unprocessed_digests()
        
        if not unprocessed:
            logger.info("✅ No unprocessed digest files found")
            return 0, 0
        
        logger.info(f"🎯 Found {len(unprocessed)} unprocessed digest files")
        
        success_count = 0
        failed_count = 0
        
        for digest_info in unprocessed:
            success = self.process_digest(digest_info)
            if success:
                success_count += 1
            else:
                failed_count += 1
            
            # Add delay between requests to respect API limits
            if self.api_available and digest_info != unprocessed[-1]:
                time.sleep(1)
        
        logger.info(f"📊 Processing complete: {success_count} successful, {failed_count} failed")
        return success_count, failed_count


def main():
    """Process all unprocessed topic digest files"""
    generator = MultiTopicTTSGenerator()
    
    success_count, failed_count = generator.process_all_unprocessed()
    
    if success_count > 0:
        print(f"🎙️  Successfully generated {success_count} TTS audio files")
    
    if failed_count > 0:
        print(f"❌ Failed to generate {failed_count} TTS audio files")
        return 1
    
    if success_count == 0 and failed_count == 0:
        print("✅ No unprocessed digest files found")
    
    return 0


if __name__ == "__main__":
    exit(main())