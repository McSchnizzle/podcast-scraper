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

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
    
    def generate_master_music(self, topic: str, duration: int = 60) -> Optional[str]:
        """Generate a master music file that can be used for intro, background, and outro"""
        if not self.elevenlabs_api_key:
            logger.warning("ElevenLabs API key not available - skipping music generation")
            return None
        
        topic_config = self.topics_config.get(topic, {})
        music_prompt = topic_config.get("music_prompt", f"Background music suitable for {topic} content")
        
        # Check cache first
        cache_filename = f"{topic}_master_{duration}s.mp3"
        cache_path = self.music_cache_dir / cache_filename
        
        if cache_path.exists():
            logger.info(f"📻 Using cached master music: {cache_filename}")
            return str(cache_path)
        
        try:
            logger.info(f"🎵 Generating {duration}s master music for {topic}")
            
            headers = {
                'xi-api-key': self.elevenlabs_api_key,
                'Content-Type': 'application/json'
            }
            
            # Create comprehensive prompt for versatile music
            full_prompt = f"""Create versatile background music for {topic} content: {music_prompt}. 
            The music should work well for intros, background ambiance, and outros. 
            Include subtle dynamic variations with a clear opening, sustained middle section suitable for looping, 
            and a natural conclusion. Keep it instrumental and at moderate volume."""
            
            data = {
                'prompt': full_prompt,
                'music_length_ms': duration * 1000,
                'model_id': 'music_v1'
            }
            
            url = "https://api.elevenlabs.io/v1/music/compose"
            response = requests.post(url, headers=headers, json=data, timeout=120)
            
            if response.status_code == 200:
                with open(cache_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"✅ Generated master music: {cache_filename} ({len(response.content)} bytes)")
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
    
    def extract_music_segment(self, master_file: str, start_seconds: int, duration_seconds: int, output_file: str) -> bool:
        """Extract a specific segment from the master music file using ffmpeg"""
        try:
            cmd = [
                'ffmpeg',
                '-i', master_file,
                '-ss', str(start_seconds),
                '-t', str(duration_seconds),
                '-c', 'copy',  # Copy without re-encoding for speed
                '-y',
                output_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"✅ Extracted {duration_seconds}s segment starting at {start_seconds}s")
                return True
            else:
                logger.error(f"❌ Failed to extract segment: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error extracting music segment: {e}")
            return False
    
    def generate_music(self, topic: str, music_type: str = "background") -> Optional[str]:
        """Generate music using the efficient master music approach"""
        # Generate or use cached master music file
        master_music = self.generate_master_music(topic, duration=60)
        if not master_music:
            return None
        
        # Define segments for different music types
        segment_config = {
            "intro": {"start": 0, "duration": 8},      # First 8 seconds
            "background": {"start": 10, "duration": 40},  # Middle 40 seconds (loopable)
            "outro": {"start": 52, "duration": 8}     # Last 8 seconds
        }
        
        config = segment_config.get(music_type, segment_config["background"])
        
        # Check if segment already exists
        segment_filename = f"{topic}_{music_type}.mp3"
        segment_path = self.music_cache_dir / segment_filename
        
        if segment_path.exists():
            logger.info(f"📻 Using cached segment: {segment_filename}")
            return str(segment_path)
        
        # Extract the segment
        success = self.extract_music_segment(
            master_music, 
            config["start"], 
            config["duration"], 
            str(segment_path)
        )
        
        if success:
            logger.info(f"✅ Generated {music_type} from master: {segment_filename}")
            return str(segment_path)
        else:
            logger.error(f"❌ Failed to generate {music_type} segment")
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
                    # Create simple sine wave tones
                    if config["freq"] == "440,554,659":  # Major chord intro
                        sine_filter = f'sine=frequency=440:duration={config["duration"]}'
                    elif config["freq"] == "659,554,440":  # Descending chord outro  
                        sine_filter = f'sine=frequency=440:duration={config["duration"]}'
                    else:  # Single frequency for background
                        sine_filter = f'sine=frequency={config["freq"]}:duration={config["duration"]}'
                    
                    cmd = [
                        'ffmpeg',
                        '-f', 'lavfi',
                        '-i', sine_filter,
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
        """Mix TTS audio with intro and outro music only (no background during speech)"""
        logger.info(f"🎧 Adding intro/outro music for {topic}")
        
        # Get music files
        intro_music = self.generate_music(topic, "intro")
        outro_music = self.generate_music(topic, "outro")
        
        # Fallback to static files if generation failed
        if not intro_music:
            intro_music = str(self.music_cache_dir / "static_intro.mp3")
        if not outro_music:
            outro_music = str(self.music_cache_dir / "static_outro.mp3")
        
        # Ensure static files exist
        self.create_static_music_files()
        
        try:
            # Simple approach: intro + narration + outro
            settings = self.default_music_settings
            
            cmd = [
                'ffmpeg',
                '-i', intro_music,  # Input 0: Intro music
                '-i', audio_file,   # Input 1: Main narration
                '-i', outro_music,  # Input 2: Outro music
                '-filter_complex',
                f'[0]volume={settings["background_volume"]}[intro_low];[2]volume={settings["background_volume"]}[outro_low];[intro_low][1][outro_low]concat=n=3:v=0:a=1[final]',
                '-map', '[final]',
                '-c:a', 'libmp3lame',
                '-b:a', '128k',
                '-y',
                output_file
            ]
            
            logger.info(f"🔄 Adding intro/outro music...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info(f"✅ Audio enhanced with intro/outro: {output_file}")
                return True
            else:
                logger.error(f"❌ Music enhancement failed: {result.stderr}")
                # Fallback: just copy the original file
                subprocess.run(['cp', audio_file, output_file])
                logger.info(f"📄 Fallback: copied original audio to {output_file}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Audio enhancement timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Error enhancing audio: {e}")
            # Fallback: just copy the original file
            try:
                subprocess.run(['cp', audio_file, output_file], check=True)
                logger.info(f"📄 Fallback: copied original audio to {output_file}")
            except Exception as copy_error:
                logger.error(f"❌ Fallback copy also failed: {copy_error}")
            return False
    
    def add_segment_transition(self, topic: str, transition_type: str = "soft") -> Optional[str]:
        """Generate a short transition sound for between digest segments"""
        # Use a shorter segment from the background music
        transition_duration = 2 if transition_type == "soft" else 3
        
        cache_filename = f"{topic}_transition_{transition_type}.mp3"
        cache_path = self.music_cache_dir / cache_filename
        
        if cache_path.exists():
            logger.info(f"📻 Using cached transition: {cache_filename}")
            return str(cache_path)
        
        # Get the background music and extract a short transition
        background_music = self.generate_music(topic, "background")
        if not background_music:
            return None
        
        try:
            # Extract a short segment for transitions (start at 15 seconds to avoid intro part)
            success = self.extract_music_segment(
                background_music, 
                15,  # Start 15 seconds in
                transition_duration, 
                str(cache_path)
            )
            
            if success:
                logger.info(f"✅ Generated {transition_type} transition: {cache_filename}")
                return str(cache_path)
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating transition: {e}")
            return None
    
    def enhance_tts_with_music(self, tts_file: str, topic: str) -> str:
        """Enhance a TTS file with intro/outro music (no background during speech)"""
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