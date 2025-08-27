#!/usr/bin/env python3
"""
Audio Post-Processing Pipeline for Daily Podcast Digest
Phase 3: Professional audio compilation with intro music and chapter markers
"""

import os
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import tempfile
import shutil

# Audio processing with fallback
try:
    from pydub import AudioSegment
    from pydub.utils import which
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub not available - using ffmpeg directly")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioPostProcessor:
    def __init__(self, output_dir: str = "daily_digests"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Audio settings for podcast production
        self.audio_settings = {
            "sample_rate": 44100,
            "bit_rate": "128k", 
            "format": "mp3",
            "channels": 1,  # Mono for podcast
            "lufs_target": -16,  # Podcast loudness standard
            "peak_limit": -1.0   # Peak limiting
        }
        
        # Chapter marker templates
        self.chapter_templates = {
            "intro": "Introduction & Overview",
            "ai_tools": "AI Tools & Technology",
            "product_launches": "Product Launches & Announcements", 
            "creative_applications": "Creative Applications",
            "technical_insights": "Technical Deep Dives",
            "business_analysis": "Business & Market Analysis",
            "social_commentary": "Social & Cultural Commentary",
            "conclusion": "Summary & Conclusion"
        }
        
        # Audio assets directory
        self.assets_dir = self.output_dir / "audio_assets"
        self.assets_dir.mkdir(exist_ok=True)
        
        # Check for ffmpeg availability
        self.ffmpeg_available = self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("ffmpeg not found - some audio processing features will be limited")
            return False

    def create_intro_music(self, duration: float = 15.0) -> str:
        """Create or prepare intro music"""
        
        intro_music_path = self.assets_dir / "intro_music.mp3"
        
        # For now, create a simple tone as placeholder
        # In production, you'd add actual music files
        if not intro_music_path.exists():
            self._generate_placeholder_music(str(intro_music_path), duration, "intro")
        
        return str(intro_music_path)

    def create_transition_music(self, duration: float = 8.0) -> str:
        """Create or prepare transition music"""
        
        transition_music_path = self.assets_dir / "transition_music.mp3"
        
        if not transition_music_path.exists():
            self._generate_placeholder_music(str(transition_music_path), duration, "transition")
        
        return str(transition_music_path)

    def create_outro_music(self, duration: float = 12.0) -> str:
        """Create or prepare outro music"""
        
        outro_music_path = self.assets_dir / "outro_music.mp3"
        
        if not outro_music_path.exists():
            self._generate_placeholder_music(str(outro_music_path), duration, "outro")
        
        return str(outro_music_path)

    def _generate_placeholder_music(self, output_path: str, duration: float, music_type: str) -> bool:
        """Generate placeholder music using ffmpeg"""
        
        if not self.ffmpeg_available:
            logger.warning(f"Cannot generate {music_type} music - ffmpeg not available")
            return False
        
        try:
            # Generate different tones for different music types
            frequency_map = {
                "intro": "440",      # A note - energetic
                "transition": "330", # E note - neutral
                "outro": "220"       # A note lower - concluding
            }
            
            frequency = frequency_map.get(music_type, "440")
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'sine=frequency={frequency}:duration={duration}',
                '-af', f'volume=0.3,fade=t=in:st=0:d=1,fade=t=out:st={duration-1}:d=1',
                '-b:a', '128k',
                '-ar', '44100',
                '-ac', '1',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"Generated {music_type} music: {output_path}")
                return True
            else:
                logger.error(f"Error generating {music_type} music: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error generating placeholder music: {e}")
            return False

    def process_tts_segments(self, segment_files: List[str], topic_order: List[str]) -> str:
        """Process TTS segments with music and transitions"""
        
        if not self.ffmpeg_available:
            logger.error("ffmpeg required for audio processing")
            return ""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        try:
            # Create temporary working directory
            with tempfile.TemporaryDirectory(prefix="podcast_") as temp_dir:
                temp_path = Path(temp_dir)
                
                # Prepare music assets
                intro_music = self.create_intro_music()
                transition_music = self.create_transition_music()
                outro_music = self.create_outro_music()
                
                # Create file list for concatenation
                concat_list = []
                chapter_markers = []
                current_time = 0.0
                
                # Add intro music
                if intro_music and Path(intro_music).exists():
                    concat_list.append(f"file '{intro_music}'")
                    chapter_markers.append({
                        "time": current_time,
                        "title": self.chapter_templates["intro"]
                    })
                    current_time += self._get_audio_duration(intro_music)
                
                # Process segments with transitions
                for i, (segment_file, topic_key) in enumerate(zip(segment_files, topic_order)):
                    if not Path(segment_file).exists():
                        continue
                    
                    # Add transition music before content (except first)
                    if i > 0 and transition_music and Path(transition_music).exists():
                        concat_list.append(f"file '{transition_music}'")
                        current_time += self._get_audio_duration(transition_music)
                    
                    # Add chapter marker for this topic
                    chapter_title = self.chapter_templates.get(topic_key, f"Topic: {topic_key}")
                    chapter_markers.append({
                        "time": current_time,
                        "title": chapter_title
                    })
                    
                    # Add main content
                    concat_list.append(f"file '{segment_file}'")
                    current_time += self._get_audio_duration(segment_file)
                
                # Add outro music
                if outro_music and Path(outro_music).exists():
                    chapter_markers.append({
                        "time": current_time,
                        "title": self.chapter_templates["conclusion"]
                    })
                    concat_list.append(f"file '{outro_music}'")
                
                # Create concatenation file
                concat_file = temp_path / "concat_list.txt"
                with open(concat_file, 'w') as f:
                    f.write('\n'.join(concat_list))
                
                # Generate temporary combined audio
                temp_output = temp_path / "temp_combined.mp3"
                
                concat_cmd = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0', 
                    '-i', str(concat_file),
                    '-c', 'copy',
                    str(temp_output)
                ]
                
                result = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=600)
                
                if result.returncode != 0:
                    logger.error(f"Audio concatenation failed: {result.stderr}")
                    return ""
                
                # Apply post-processing
                final_output = self.output_dir / f"daily_podcast_digest_{timestamp}.mp3"
                
                success = self._apply_audio_postprocessing(
                    str(temp_output), 
                    str(final_output),
                    chapter_markers
                )
                
                if success:
                    logger.info(f"Final podcast audio generated: {final_output}")
                    return str(final_output)
                else:
                    return ""
        
        except Exception as e:
            logger.error(f"Error processing TTS segments: {e}")
            return ""

    def _get_audio_duration(self, audio_file: str) -> float:
        """Get audio file duration in seconds"""
        
        if not self.ffmpeg_available:
            return 10.0  # Default estimate
        
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                audio_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                probe_data = json.loads(result.stdout)
                duration = float(probe_data['format']['duration'])
                return duration
            else:
                return 10.0  # Fallback estimate
                
        except Exception as e:
            logger.error(f"Error getting audio duration for {audio_file}: {e}")
            return 10.0

    def _apply_audio_postprocessing(self, input_path: str, output_path: str, chapter_markers: List[Dict]) -> bool:
        """Apply professional audio post-processing"""
        
        if not self.ffmpeg_available:
            logger.error("ffmpeg required for audio post-processing")
            return False
        
        try:
            # Create chapter metadata file
            chapters_file = Path(output_path).parent / f"{Path(output_path).stem}_chapters.txt"
            
            with open(chapters_file, 'w') as f:
                f.write(";FFMETADATA1\n")
                for i, marker in enumerate(chapter_markers):
                    start_time = int(marker["time"] * 1000)  # Convert to milliseconds
                    end_time = int(chapter_markers[i+1]["time"] * 1000) if i+1 < len(chapter_markers) else None
                    
                    f.write(f"[CHAPTER]\n")
                    f.write(f"TIMEBASE=1/1000\n")
                    f.write(f"START={start_time}\n")
                    if end_time:
                        f.write(f"END={end_time}\n")
                    f.write(f"title={marker['title']}\n\n")
            
            # Apply audio processing with normalization and chapter markers
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-i', str(chapters_file),
                '-map_metadata', '1',
                '-af', f'loudnorm=I={self.audio_settings["lufs_target"]}:TP={self.audio_settings["peak_limit"]}:LRA=7',
                '-b:a', self.audio_settings["bit_rate"],
                '-ar', str(self.audio_settings["sample_rate"]),
                '-ac', str(self.audio_settings["channels"]),
                '-metadata', f'title=Daily Podcast Digest - {datetime.now().strftime("%Y-%m-%d")}',
                '-metadata', 'artist=Daily Podcast Digest AI',
                '-metadata', 'genre=News & Politics',
                '-metadata', f'date={datetime.now().year}',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            
            if result.returncode == 0:
                logger.info(f"Audio post-processing completed: {output_path}")
                
                # Cleanup temporary chapter file
                chapters_file.unlink()
                
                return True
            else:
                logger.error(f"Audio post-processing failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error in audio post-processing: {e}")
            return False

    def create_podcast_episode(self, tts_segments: List[str], topic_order: List[str], 
                             episode_metadata: Optional[Dict] = None) -> Optional[str]:
        """Create complete podcast episode with full post-processing"""
        
        logger.info("Creating complete podcast episode...")
        
        # Process segments with music and transitions
        final_audio = self.process_tts_segments(tts_segments, topic_order)
        
        if not final_audio:
            logger.error("Failed to create podcast episode")
            return None
        
        # Add podcast metadata
        if episode_metadata:
            enhanced_audio = self._add_podcast_metadata(final_audio, episode_metadata)
            if enhanced_audio:
                # Remove intermediate file
                Path(final_audio).unlink()
                final_audio = enhanced_audio
        
        # Generate RSS-ready episode info
        self._generate_episode_info(final_audio, episode_metadata or {})
        
        logger.info(f"Complete podcast episode created: {final_audio}")
        return final_audio

    def _add_podcast_metadata(self, audio_file: str, metadata: Dict) -> Optional[str]:
        """Add comprehensive podcast metadata"""
        
        if not self.ffmpeg_available:
            return audio_file
        
        output_file = str(Path(audio_file).with_suffix('.final.mp3'))
        
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', audio_file,
                '-codec', 'copy'
            ]
            
            # Add metadata
            if metadata.get('title'):
                cmd.extend(['-metadata', f'title={metadata["title"]}'])
            if metadata.get('description'): 
                cmd.extend(['-metadata', f'comment={metadata["description"]}'])
            if metadata.get('episode_number'):
                cmd.extend(['-metadata', f'track={metadata["episode_number"]}'])
            if metadata.get('publication_date'):
                cmd.extend(['-metadata', f'date={metadata["publication_date"]}'])
            
            # Standard podcast metadata
            cmd.extend([
                '-metadata', 'artist=Daily Podcast Digest',
                '-metadata', 'album=Daily Podcast Digest',
                '-metadata', 'genre=News & Politics',
                '-metadata', 'language=en',
                output_file
            ])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            
            if result.returncode == 0:
                logger.info(f"Metadata added to podcast episode: {output_file}")
                return output_file
            else:
                logger.error(f"Metadata addition failed: {result.stderr}")
                return audio_file
                
        except Exception as e:
            logger.error(f"Error adding metadata: {e}")
            return audio_file

    def _generate_episode_info(self, audio_file: str, metadata: Dict) -> None:
        """Generate episode information file for RSS feed"""
        
        info_file = Path(audio_file).with_suffix('.json')
        
        # Get audio file stats
        file_size = Path(audio_file).stat().st_size
        duration = self._get_audio_duration(audio_file)
        
        episode_info = {
            "audio_file": str(Path(audio_file).name),
            "file_size": file_size,
            "duration": duration,
            "publication_date": datetime.now().isoformat(),
            "title": metadata.get('title', f"Daily Podcast Digest - {datetime.now().strftime('%Y-%m-%d')}"),
            "description": metadata.get('description', "AI-generated daily digest from podcast monitoring"),
            "episode_number": metadata.get('episode_number', self._generate_episode_number()),
            "categories": ["Technology", "News", "AI"],
            "guid": f"daily-digest-{datetime.now().strftime('%Y%m%d')}",
            "enclosure": {
                "url": f"https://your-domain.com/episodes/{Path(audio_file).name}",
                "length": file_size,
                "type": "audio/mpeg"
            }
        }
        
        try:
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(episode_info, f, indent=2, default=str)
            
            logger.info(f"Episode info generated: {info_file}")
            
        except Exception as e:
            logger.error(f"Error generating episode info: {e}")

    def _get_audio_duration(self, audio_file: str) -> float:
        """Get audio duration using ffprobe"""
        
        if not self.ffmpeg_available:
            return 0.0
        
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                audio_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                probe_data = json.loads(result.stdout)
                return float(probe_data['format']['duration'])
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error getting audio duration: {e}")
            return 0.0

    def _generate_episode_number(self) -> int:
        """Generate episode number based on date"""
        
        # Simple episode numbering: days since epoch
        epoch = datetime(2024, 1, 1)  # Arbitrary start date
        days_since = (datetime.now() - epoch).days
        return days_since

    def normalize_audio_levels(self, audio_file: str) -> bool:
        """Normalize audio to podcast standards"""
        
        if not self.ffmpeg_available:
            return False
        
        try:
            temp_file = str(Path(audio_file).with_suffix('.normalized.mp3'))
            
            cmd = [
                'ffmpeg', '-y',
                '-i', audio_file,
                '-af', f'loudnorm=I={self.audio_settings["lufs_target"]}:TP={self.audio_settings["peak_limit"]}:LRA=7',
                '-b:a', self.audio_settings["bit_rate"],
                '-ar', str(self.audio_settings["sample_rate"]),
                temp_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                # Replace original with normalized version
                shutil.move(temp_file, audio_file)
                logger.info(f"Audio normalized to {self.audio_settings['lufs_target']} LUFS")
                return True
            else:
                logger.error(f"Audio normalization failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error normalizing audio: {e}")
            return False

    def validate_audio_quality(self, audio_file: str) -> Dict:
        """Validate final audio quality"""
        
        validation = {
            "file_exists": Path(audio_file).exists(),
            "file_size": 0,
            "duration": 0.0,
            "sample_rate": 0,
            "bit_rate": "",
            "channels": 0,
            "loudness_lufs": None,
            "peak_level": None
        }
        
        if not validation["file_exists"]:
            return validation
        
        validation["file_size"] = Path(audio_file).stat().st_size
        
        if self.ffmpeg_available:
            try:
                # Get basic audio info
                cmd = [
                    'ffprobe', '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format', '-show_streams',
                    audio_file
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    probe_data = json.loads(result.stdout)
                    
                    if 'format' in probe_data:
                        validation["duration"] = float(probe_data['format'].get('duration', 0))
                        validation["bit_rate"] = probe_data['format'].get('bit_rate', 'unknown')
                    
                    if 'streams' in probe_data and probe_data['streams']:
                        audio_stream = probe_data['streams'][0]
                        validation["sample_rate"] = int(audio_stream.get('sample_rate', 0))
                        validation["channels"] = int(audio_stream.get('channels', 0))
                
            except Exception as e:
                logger.error(f"Error validating audio quality: {e}")
        
        return validation


def main():
    """CLI entry point for audio post-processing"""
    
    processor = AudioPostProcessor()
    
    print("🎵 Audio Post-Processing Pipeline")
    print("=" * 40)
    
    # Check system requirements
    if not processor.ffmpeg_available:
        print("❌ ffmpeg not found - install with: brew install ffmpeg")
        return 1
    
    print("✅ Audio processing system ready")
    print("✅ Music assets will be generated as needed")
    print(f"✅ Output directory: {processor.output_dir}")
    
    # Test music generation
    print("\n🎵 Testing music generation...")
    intro_music = processor.create_intro_music()
    if intro_music and Path(intro_music).exists():
        print(f"✅ Intro music ready: {Path(intro_music).name}")
    else:
        print("❌ Failed to generate intro music")
    
    return 0


if __name__ == "__main__":
    exit(main())