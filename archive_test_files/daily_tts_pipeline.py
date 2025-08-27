#!/usr/bin/env python3
"""
Daily TTS Pipeline - Phase 3 Complete Implementation
Orchestrates topic compilation, TTS generation, and audio post-processing
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Import our Phase 3 modules
from topic_compiler import TopicCompiler
from tts_script_generator import TTSScriptGenerator  
from tts_generator import TTSGenerator
from audio_postprocessor import AudioPostProcessor

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DailyTTSPipeline:
    def __init__(self, 
                 db_path: str = "podcast_monitor.db",
                 output_dir: str = "daily_digests"):
        
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.topic_compiler = TopicCompiler(db_path)
        self.script_generator = TTSScriptGenerator(str(self.output_dir))
        self.tts_generator = TTSGenerator(db_path, audio_output_dir=str(self.output_dir))
        self.audio_processor = AudioPostProcessor(str(self.output_dir))
        
        # Pipeline state tracking
        self.pipeline_state = {
            "start_time": None,
            "episodes_processed": 0,
            "topics_identified": 0,
            "audio_segments_generated": 0,
            "final_audio_created": False,
            "errors": []
        }

    def run_daily_pipeline(self, dry_run: bool = False) -> Tuple[bool, Dict]:
        """Execute complete daily TTS pipeline"""
        
        logger.info("🎙️  Starting Daily TTS Pipeline")
        logger.info("=" * 50)
        
        self.pipeline_state["start_time"] = datetime.now()
        
        try:
            # Phase 1: Topic Compilation
            logger.info("Phase 1: Topic Analysis & Compilation")
            episodes = self.topic_compiler.get_processed_episodes()
            
            if not episodes:
                error_msg = "No digested episodes found for TTS generation"
                logger.error(error_msg)
                self.pipeline_state["errors"].append(error_msg)
                return False, self.pipeline_state
            
            self.pipeline_state["episodes_processed"] = len(episodes)
            logger.info(f"✅ Found {len(episodes)} episodes ready for processing")
            
            # Compile topics
            compilation = self.topic_compiler.generate_tts_optimized_compilation(episodes)
            
            if not compilation["topics"]:
                error_msg = "No topics identified from episodes"
                logger.error(error_msg)
                self.pipeline_state["errors"].append(error_msg)
                return False, self.pipeline_state
            
            self.pipeline_state["topics_identified"] = len(compilation["topics"])
            logger.info(f"✅ Identified {len(compilation['topics'])} topics for synthesis")
            
            # Phase 2: Script Generation
            logger.info("\nPhase 2: TTS Script Generation")
            script, production_notes = self.script_generator.generate_full_tts_script(episodes)
            
            if not script:
                error_msg = "Failed to generate TTS script"
                logger.error(error_msg)
                self.pipeline_state["errors"].append(error_msg)
                return False, self.pipeline_state
            
            logger.info(f"✅ Generated TTS script ({len(script)} characters)")
            
            if dry_run:
                logger.info("🔍 DRY RUN: Stopping before audio generation")
                return True, self.pipeline_state
            
            # Phase 3: Audio Generation
            logger.info("\nPhase 3: TTS Audio Generation")
            
            if not self.tts_generator.elevenlabs_api_key:
                error_msg = "ElevenLabs API key not configured"
                logger.error(error_msg)
                self.pipeline_state["errors"].append(error_msg)
                return False, self.pipeline_state
            
            # Generate audio segments for each topic
            audio_segments = []
            topic_order = []
            
            # Introduction segment
            intro_audio = self._generate_intro_audio(compilation)
            if intro_audio:
                audio_segments.append(intro_audio)
                topic_order.append("intro")
            
            # Topic segments
            for topic_key, topic_data in compilation["topics"].items():
                topic_audio = self._generate_topic_audio(topic_key, topic_data)
                if topic_audio:
                    audio_segments.append(topic_audio)
                    topic_order.append(topic_key)
                    self.pipeline_state["audio_segments_generated"] += 1
            
            # Conclusion segment
            conclusion_audio = self._generate_conclusion_audio(compilation)
            if conclusion_audio:
                audio_segments.append(conclusion_audio)
                topic_order.append("conclusion")
            
            if not audio_segments:
                error_msg = "No audio segments generated successfully"
                logger.error(error_msg)
                self.pipeline_state["errors"].append(error_msg)
                return False, self.pipeline_state
            
            logger.info(f"✅ Generated {len(audio_segments)} audio segments")
            
            # Phase 4: Audio Post-Processing
            logger.info("\nPhase 4: Audio Compilation & Post-Processing")
            
            episode_metadata = {
                "title": f"Daily Podcast Digest - {datetime.now().strftime('%B %d, %Y')}",
                "description": f"AI-synthesized insights from {self.pipeline_state['episodes_processed']} episodes across {self.pipeline_state['topics_identified']} topics",
                "episode_number": self.audio_processor._generate_episode_number(),
                "publication_date": datetime.now().strftime('%Y-%m-%d')
            }
            
            final_audio = self.audio_processor.create_podcast_episode(
                audio_segments, topic_order, episode_metadata
            )
            
            if final_audio:
                self.pipeline_state["final_audio_created"] = True
                logger.info(f"✅ Final podcast episode created: {Path(final_audio).name}")
                
                # Validate audio quality
                validation = self.audio_processor.validate_audio_quality(final_audio)
                logger.info(f"📊 Audio validation: {validation['duration']:.1f}s, {validation['file_size']/1024/1024:.1f}MB")
                
                return True, {
                    **self.pipeline_state,
                    "final_audio_path": final_audio,
                    "audio_validation": validation,
                    "success": True
                }
            else:
                error_msg = "Failed to create final podcast episode"
                logger.error(error_msg)
                self.pipeline_state["errors"].append(error_msg)
                return False, self.pipeline_state
                
        except Exception as e:
            error_msg = f"Pipeline execution error: {e}"
            logger.error(error_msg)
            self.pipeline_state["errors"].append(error_msg)
            return False, self.pipeline_state

    def _generate_intro_audio(self, compilation: Dict) -> Optional[str]:
        """Generate introduction audio segment"""
        
        metadata = compilation["metadata"]
        date_str = datetime.now().strftime('%A, %B %d')
        
        intro_text = f"""
        Welcome to your Daily Podcast Digest for {date_str}.
        
        Today's edition synthesizes insights from {metadata['total_episodes']} podcast episodes 
        across {metadata['topics_covered']} key themes. Rather than individual show summaries, 
        we'll explore cross-episode connections and emerging trends.
        
        Let's dive into today's most significant developments.
        """
        
        output_path = self.output_dir / f"intro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        
        # Use host voice for introduction
        voice_config = self.tts_generator.voice_config["intro_outro"]
        
        if self.tts_generator.generate_audio_segment(intro_text, voice_config, str(output_path)):
            return str(output_path)
        else:
            logger.error("Failed to generate intro audio")
            return None

    def _generate_topic_audio(self, topic_key: str, topic_data: Dict) -> Optional[str]:
        """Generate audio for a specific topic section"""
        
        script_text = topic_data.get("tts_script", "")
        if not script_text:
            logger.warning(f"No script available for topic: {topic_key}")
            return None
        
        output_path = self.output_dir / f"topic_{topic_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        
        # Use topic-specific voice
        voice_config = self.tts_generator.voice_config.get(topic_key, self.tts_generator.voice_config["intro_outro"])
        
        if self.tts_generator.generate_audio_segment(script_text, voice_config, str(output_path)):
            logger.info(f"✅ Generated {topic_data['display_name']} audio ({topic_data['episode_count']} episodes)")
            return str(output_path)
        else:
            logger.error(f"Failed to generate audio for topic: {topic_key}")
            return None

    def _generate_conclusion_audio(self, compilation: Dict) -> Optional[str]:
        """Generate conclusion audio segment"""
        
        metadata = compilation["metadata"]
        
        conclusion_text = f"""
        That wraps up today's Daily Podcast Digest. 
        
        We've synthesized insights from {metadata['total_episodes']} episodes 
        across {metadata['topics_covered']} major themes, focusing on connections 
        and emerging trends rather than individual show summaries.
        
        Tomorrow we'll continue tracking these evolving themes while introducing 
        new developments from across the podcast landscape.
        
        Thanks for listening. Stay curious, stay informed.
        """
        
        output_path = self.output_dir / f"conclusion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        
        # Use host voice for conclusion
        voice_config = self.tts_generator.voice_config["intro_outro"]
        
        if self.tts_generator.generate_audio_segment(conclusion_text, voice_config, str(output_path)):
            return str(output_path)
        else:
            logger.error("Failed to generate conclusion audio")
            return None

    def generate_pipeline_report(self, pipeline_result: Dict) -> str:
        """Generate comprehensive pipeline execution report"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.output_dir / f"pipeline_report_{timestamp}.json"
        
        # Calculate execution time
        if pipeline_result.get("start_time"):
            execution_time = datetime.now() - pipeline_result["start_time"]
            pipeline_result["execution_time_seconds"] = execution_time.total_seconds()
        
        # Add system info
        pipeline_result["system_info"] = {
            "python_version": sys.version,
            "pipeline_version": "3.0",
            "components": ["TopicCompiler", "TTSScriptGenerator", "TTSGenerator", "AudioPostProcessor"]
        }
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(pipeline_result, f, indent=2, default=str)
            
            logger.info(f"Pipeline report saved: {report_path}")
            return str(report_path)
            
        except Exception as e:
            logger.error(f"Error saving pipeline report: {e}")
            return ""


def main():
    """CLI entry point for daily TTS pipeline"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Daily TTS Pipeline")
    parser.add_argument('--dry-run', action='store_true', help='Generate scripts without audio')
    parser.add_argument('--test', action='store_true', help='Run pipeline tests')
    parser.add_argument('--validate', action='store_true', help='Validate system requirements')
    args = parser.parse_args()
    
    pipeline = DailyTTSPipeline()
    
    print("🎙️  Daily TTS Pipeline - Phase 3")
    print("=" * 45)
    
    if args.validate:
        print("🔍 Validating system requirements...")
        
        # Check ElevenLabs API key
        if pipeline.tts_generator.elevenlabs_api_key:
            print("✅ ElevenLabs API key configured")
        else:
            print("❌ ElevenLabs API key missing")
            return 1
        
        # Check ffmpeg
        if pipeline.audio_processor.ffmpeg_available:
            print("✅ ffmpeg available")
        else:
            print("❌ ffmpeg not found")
            return 1
        
        # Check database
        episodes = pipeline.topic_compiler.get_processed_episodes()
        print(f"✅ Database contains {len(episodes)} ready episodes")
        
        print("✅ All system requirements validated")
        return 0
    
    if args.test:
        print("🧪 Running TTS pipeline test...")
        
        # Test TTS generation
        if pipeline.tts_generator.test_tts_generation():
            print("✅ TTS test successful")
        else:
            print("❌ TTS test failed")
            return 1
        
        return 0
    
    # Run full pipeline
    success, result = pipeline.run_daily_pipeline(dry_run=args.dry_run)
    
    if success:
        print("🎉 Daily TTS pipeline completed successfully!")
        
        if args.dry_run:
            print("📝 Dry run completed - scripts generated without audio")
        else:
            if result.get("final_audio_path"):
                print(f"🎵 Final podcast: {Path(result['final_audio_path']).name}")
                validation = result.get("audio_validation", {})
                if validation:
                    duration = validation.get("duration", 0)
                    size_mb = validation.get("file_size", 0) / 1024 / 1024
                    print(f"📊 Duration: {duration:.1f}s | Size: {size_mb:.1f}MB")
        
        # Generate report
        report_path = pipeline.generate_pipeline_report(result)
        if report_path:
            print(f"📋 Report: {Path(report_path).name}")
        
        return 0
    else:
        print("❌ Daily TTS pipeline failed")
        if result.get("errors"):
            print("Errors encountered:")
            for error in result["errors"]:
                print(f"  - {error}")
        return 1


if __name__ == "__main__":
    exit(main())