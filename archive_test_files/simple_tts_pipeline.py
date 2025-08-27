#!/usr/bin/env python3
"""
Simplified TTS Pipeline - Phase 3 Core Implementation
Focus on TTS generation without complex audio processing initially
"""

import os
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from topic_compiler import TopicCompiler
from tts_generator import TTSGenerator

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class SimpleTTSPipeline:
    def __init__(self, db_path: str = "podcast_monitor.db", output_dir: str = "daily_digests"):
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.topic_compiler = TopicCompiler(db_path)
        self.tts_generator = TTSGenerator(db_path, audio_output_dir=str(self.output_dir))

    def generate_simple_daily_audio(self) -> Optional[str]:
        """Generate daily audio digest - simplified version"""
        
        logger.info("🎙️ Starting Simple TTS Pipeline")
        
        # Get episodes
        episodes = self.topic_compiler.get_processed_episodes()
        if not episodes:
            logger.error("No episodes found")
            return None
        
        logger.info(f"📊 Processing {len(episodes)} episodes")
        
        # Categorize episodes  
        compilation = self.topic_compiler.generate_tts_optimized_compilation(episodes)
        
        if not compilation["topics"]:
            logger.error("No topics identified")
            return None
        
        logger.info(f"🎯 Found {len(compilation['topics'])} topics")
        
        # Generate simple combined script
        script_parts = []
        
        # Intro
        date_str = datetime.now().strftime('%B %d, %Y')
        intro = f"""Welcome to your Daily Podcast Digest for {date_str}. 
        Today we're synthesizing insights from {len(episodes)} episodes across {len(compilation['topics'])} key topics."""
        
        script_parts.append(intro)
        
        # Topic sections
        for topic_key, topic_data in compilation["topics"].items():
            topic_name = topic_data["display_name"]
            episode_count = topic_data["episode_count"]
            
            topic_script = f"""
            
            In {topic_name}, we have {episode_count} episodes to explore.
            
            {topic_data.get('tts_script', '')}
            """
            
            script_parts.append(topic_script)
        
        # Conclusion
        conclusion = """
        
        That completes today's digest. Thank you for listening to your Daily Podcast Digest.
        """
        
        script_parts.append(conclusion)
        
        # Combine script
        full_script = " ".join(script_parts)
        
        # Generate single audio file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f"simple_daily_digest_{timestamp}.mp3"
        
        # Use host voice
        voice_config = self.tts_generator.voice_config["intro_outro"]
        
        success = self.tts_generator.generate_audio_segment(
            full_script, voice_config, str(output_file)
        )
        
        if success:
            logger.info(f"✅ Generated daily audio digest: {output_file}")
            
            # Generate metadata
            self._save_episode_metadata(str(output_file), {
                "title": f"Daily Podcast Digest - {date_str}",
                "episode_count": len(episodes),
                "topics_covered": len(compilation["topics"]),
                "generation_time": datetime.now().isoformat()
            })
            
            return str(output_file)
        else:
            logger.error("Failed to generate audio")
            return None

    def _save_episode_metadata(self, audio_file: str, metadata: Dict) -> None:
        """Save episode metadata"""
        
        info_file = Path(audio_file).with_suffix('.json')
        
        try:
            file_size = Path(audio_file).stat().st_size
            
            episode_info = {
                **metadata,
                "audio_file": Path(audio_file).name,
                "file_size": file_size,
                "format": "mp3",
                "generated_by": "SimpleTTSPipeline v3.0"
            }
            
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(episode_info, f, indent=2, default=str)
            
            logger.info(f"📋 Metadata saved: {info_file.name}")
            
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")


def main():
    """CLI entry point"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple TTS Pipeline")
    parser.add_argument('--test-api', action='store_true', help='Test ElevenLabs API')
    args = parser.parse_args()
    
    pipeline = SimpleTTSPipeline()
    
    print("🎙️ Simple TTS Pipeline - Phase 3")
    print("=" * 40)
    
    if args.test_api:
        print("🧪 Testing ElevenLabs API...")
        if pipeline.tts_generator.test_tts_generation("Hello, this is a test of the TTS system."):
            print("✅ API test successful")
            return 0
        else:
            print("❌ API test failed")
            return 1
    
    # Generate daily digest
    result = pipeline.generate_simple_daily_audio()
    
    if result:
        print(f"🎉 Success! Generated: {Path(result).name}")
        
        # Show file info
        file_size = Path(result).stat().st_size / 1024 / 1024
        print(f"📊 File size: {file_size:.2f} MB")
        
        return 0
    else:
        print("❌ Failed to generate daily digest")
        return 1


if __name__ == "__main__":
    exit(main())