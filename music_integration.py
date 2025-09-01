#!/usr/bin/env python3
"""
Music Integration for Multi-Topic TTS
Integrates background music with TTS narration using ffmpeg
"""

import os
import json
import requests
import subprocess
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import tempfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MusicIntegrator:
    def __init__(self):
        self.elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY')
        self.music_cache_dir = Path("music_cache")
        self.music_cache_dir.mkdir(exist_ok=True)
        
        # Load topic configuration for music prompts
        self.topics_config = self._load_topics_config()
        
        # Default music settings
        self.default_music_settings = {
            "intro_duration": 5,  # seconds
            "outro_duration": 3,  # seconds
            "background_volume": 0.15,  # 15% volume for background music
            "fade_in_duration": 2,
            "fade_out_duration": 2
        }
    
    def _load_topics_config(self) -> Dict:
        """Load topic configuration from topics.json"""
        try:
            topics_config_path = Path("topics.json")
            if topics_config_path.exists():
                with open(topics_config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning("topics.json not found")
                return {}
        except Exception as e:
            logger.error(f"Error loading topics.json: {e}")
            return {}
    
    def generate_music(self, topic: str, music_type: str = "background") -> Optional[str]:
        """Generate music using ElevenLabs Music API"""
        if not self.elevenlabs_api_key:
            logger.warning("ElevenLabs API key not available - skipping music generation")
            return None
        
        topic_config = self.topics_config.get(topic, {})
        music_prompt = topic_config.get("music_prompt", f"Background music suitable for {topic} content")
        
        # Check cache first
        cache_filename = f"{topic}_{music_type}.mp3"
        cache_path = self.music_cache_dir / cache_filename
        
        if cache_path.exists():
            logger.info(f"📻 Using cached music: {cache_filename}")
            return str(cache_path)
        
        try:
            logger.info(f"🎵 Generating {music_type} music for {topic}")
            
            headers = {
                'xi-api-key': self.elevenlabs_api_key,
                'Content-Type': 'application/json'
            }
            
            # Adjust prompt based on music type
            if music_type == "intro":
                full_prompt = f"Upbeat intro music: {music_prompt}, 5 seconds, energetic opening"
                duration = 5
            elif music_type == "outro":
                full_prompt = f"Closing outro music: {music_prompt}, 3 seconds, conclusive ending"
                duration = 3
            else:  # background
                full_prompt = f"Subtle background music: {music_prompt}, loopable, low energy for narration"
                duration = 60  # Generate longer background music
            
            data = {
                'text': full_prompt,
                'duration_seconds': duration,
                'prompt_influence': 0.7
            }
            
            # Note: This is a placeholder - ElevenLabs Music API endpoint may be different
            url = "https://api.elevenlabs.io/v1/music/generate"
            
            response = requests.post(url, headers=headers, json=data, timeout=120)
            
            if response.status_code == 200:
                with open(cache_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"✅ Generated {music_type} music: {cache_filename}")
                return str(cache_path)
            else:
                logger.error(f"❌ Music generation failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Music generation request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error generating music: {e}")
            return None
    
    def create_static_music_files(self):
        """Create static intro/outro/background music files as fallback"""
        logger.info("🎵 Creating static music files as fallback...")
        
        # Create simple tone-based music using ffmpeg
        static_files = {
            "intro": {"duration": 5, "freq": "440,554,659", "description": "Major chord intro"},
            "outro": {"duration": 3, "freq": "659,554,440", "description": "Descending chord outro"},
            "background": {"duration": 60, "freq": "220", "description": "Low ambient tone"}
        }
        
        for music_type, config in static_files.items():
            cache_path = self.music_cache_dir / f"static_{music_type}.mp3"
            
            if not cache_path.exists():
                try:
                    # Generate simple tones using ffmpeg
                    cmd = [
                        'ffmpeg',
                        '-f', 'lavfi',
                        '-i', f'sine=frequency={config["freq"]}:duration={config["duration"]}',
                        '-af', 'volume=0.1',  # Very quiet
                        '-y',
                        str(cache_path)
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0:
                        logger.info(f"✅ Created static {music_type} music ({config['description']})")
                    else:
                        logger.error(f"❌ Failed to create static {music_type} music: {result.stderr}")
                        
                except Exception as e:
                    logger.error(f"❌ Error creating static {music_type} music: {e}")
    
    def mix_audio_with_music(self, audio_file: str, topic: str, output_file: str) -> bool:
        """Mix TTS audio with intro, background, and outro music"""
        logger.info(f"🎧 Mixing audio with music for {topic}")
        
        # Get or generate music files
        intro_music = self.generate_music(topic, "intro")
        background_music = self.generate_music(topic, "background")
        outro_music = self.generate_music(topic, "outro")
        
        # Fallback to static files if generation failed
        if not intro_music:
            intro_music = str(self.music_cache_dir / "static_intro.mp3")
        if not background_music:
            background_music = str(self.music_cache_dir / "static_background.mp3")
        if not outro_music:
            outro_music = str(self.music_cache_dir / "static_outro.mp3")
        
        # Ensure static files exist
        self.create_static_music_files()
        
        try:
            # Get audio duration
            duration_cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format',
                audio_file
            ]
            duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
            duration_info = json.loads(duration_result.stdout)
            audio_duration = float(duration_info['format']['duration'])
            
            # Create complex ffmpeg filter for mixing
            settings = self.default_music_settings
            
            # Build ffmpeg command with complex filtering
            cmd = [
                'ffmpeg',
                '-i', audio_file,  # Input 0: Main narration
                '-i', intro_music,  # Input 1: Intro music
                '-i', background_music,  # Input 2: Background music
                '-i', outro_music,  # Input 3: Outro music
                '-filter_complex',
                f'''
                [1]volume={settings["background_volume"]}[intro];
                [2]volume={settings["background_volume"]},aloop=loop=-1:duration={audio_duration}[bg];
                [3]volume={settings["background_volume"]}[outro];
                [intro][0]concat=n=2:v=0:a=1[intro_narration];
                [intro_narration][bg]amix=inputs=2:duration=longest[with_bg];
                [with_bg][outro]concat=n=2:v=0:a=1[final]
                '''.strip().replace('\n', '').replace(' ', ''),
                '-map', '[final]',
                '-c:a', 'libmp3lame',
                '-b:a', '128k',
                '-y',
                output_file
            ]
            
            logger.info(f"🔄 Running ffmpeg audio mixing...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info(f"✅ Audio mixed successfully: {output_file}")
                return True
            else:
                logger.error(f"❌ Audio mixing failed: {result.stderr}")
                # Fallback: just copy the original file
                subprocess.run(['cp', audio_file, output_file])
                logger.info(f"📄 Fallback: copied original audio to {output_file}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Audio mixing timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Error mixing audio: {e}")
            # Fallback: just copy the original file
            try:
                subprocess.run(['cp', audio_file, output_file], check=True)
                logger.info(f"📄 Fallback: copied original audio to {output_file}")
            except Exception as copy_error:
                logger.error(f"❌ Fallback copy also failed: {copy_error}")
            return False
    
    def enhance_tts_with_music(self, tts_file: str, topic: str) -> str:
        """Enhance a TTS file with music and return the enhanced filename"""
        input_path = Path(tts_file)
        enhanced_filename = input_path.stem + "_enhanced" + input_path.suffix
        enhanced_path = input_path.parent / enhanced_filename
        
        success = self.mix_audio_with_music(str(input_path), topic, str(enhanced_path))
        
        if success:
            return str(enhanced_path)
        else:
            # Return original file if enhancement failed
            return tts_file


def main():
    """Test music integration functionality"""
    integrator = MusicIntegrator()
    
    # Create static music files
    integrator.create_static_music_files()
    
    # Test music generation for each topic
    topics = ["AI News", "Tech Product Releases", "Community Organizing"]
    
    for topic in topics:
        logger.info(f"\n🎵 Testing music generation for: {topic}")
        
        for music_type in ["intro", "background", "outro"]:
            music_file = integrator.generate_music(topic, music_type)
            if music_file:
                logger.info(f"  ✅ {music_type}: {music_file}")
            else:
                logger.info(f"  ❌ {music_type}: Failed")
    
    logger.info("\n🎧 Music integration test complete")


if __name__ == "__main__":
    main()