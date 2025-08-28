#!/usr/bin/env python3
"""
Claude-Powered TTS Generator
Combines Claude Code headless analysis with ElevenLabs TTS
Enhanced with topic-based compilation
"""

import os
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import tempfile

from tts_generator import TTSGenerator
from topic_compiler import TopicCompiler

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
        
        # Initialize TTS generator and topic compiler
        self.tts_generator = TTSGenerator(db_path, audio_output_dir=str(self.output_dir))
        self.topic_compiler = TopicCompiler(db_path)
        
        # Claude Code settings
        self.claude_cmd = "claude"

    def get_transcripts_for_claude(self) -> List[Dict]:
        """Get transcript data for Claude analysis"""
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT id, title, transcript_path, episode_id
            FROM episodes 
            WHERE status = 'transcribed' 
            AND transcript_path IS NOT NULL
            ORDER BY id
            """
            
            cursor.execute(query)
            transcripts = []
            
            for row in cursor.fetchall():
                transcript_path = row[2]
                if transcript_path and Path(transcript_path).exists():
                    transcripts.append({
                        'id': row[0],
                        'title': row[1], 
                        'transcript_path': row[2],
                        'episode_id': row[3]
                    })
            
            conn.close()
            return transcripts
            
        except Exception as e:
            logger.error(f"Error getting transcripts: {e}")
            return []

    def mark_episodes_as_digested(self, episode_ids: List[str]) -> None:
        """Mark episodes as digested and move their transcripts"""
        import sqlite3
        import shutil
        from pathlib import Path
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create digested folder if it doesn't exist
            digested_dir = Path("transcripts/digested")
            digested_dir.mkdir(parents=True, exist_ok=True)
            
            for episode_id in episode_ids:
                # Get current transcript path
                cursor.execute("SELECT transcript_path FROM episodes WHERE episode_id = ?", (episode_id,))
                result = cursor.fetchone()
                
                if result and result[0]:
                    old_path = Path(result[0])
                    if old_path.exists():
                        # Move transcript to digested folder
                        new_path = digested_dir / old_path.name
                        shutil.move(str(old_path), str(new_path))
                        
                        # Update database with new path and status
                        cursor.execute("""
                            UPDATE episodes 
                            SET status = 'digested', transcript_path = ?
                            WHERE episode_id = ?
                        """, (str(new_path), episode_id))
                        
                        print(f"  📁 Moved {old_path.name} → digested/")
            
            conn.commit()
            conn.close()
            print(f"✅ Marked {len(episode_ids)} episodes as digested")
            
        except Exception as e:
            print(f"❌ Error marking episodes as digested: {e}")

    def create_claude_digest_prompt(self, transcripts: List[Dict]) -> str:
        """Create optimized prompt for Claude digest generation"""
        
        # Load instructions from file
        try:
            with open('claude_digest_instructions.md', 'r', encoding='utf-8') as f:
                instructions = f.read()
        except Exception as e:
            logger.warning(f"Could not load instructions file: {e}")
            instructions = "Generate a professional daily podcast digest focusing on cross-episode synthesis."
        
        prompt = f"""
You are tasked with creating a professional daily podcast digest. Follow these instructions precisely:

{instructions}

Now analyze the following {len(transcripts)} podcast episodes and CREATE the daily digest. Do not just list requirements - actually write the complete digest following the format specified above.

EPISODE DATA TO ANALYZE:
"""
        
        # Process transcripts in batches to handle token limits effectively
        batch_size = 8  # Process 8 episodes at a time for better synthesis
        processed_transcripts = transcripts[:batch_size]
        
        for transcript in processed_transcripts:
            try:
                with open(transcript['transcript_path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract key sections: first 2000 chars + last 1000 chars for better coverage
                if len(content) > 4000:
                    key_content = content[:2000] + "\n\n[... middle content truncated ...]\n\n" + content[-1000:]
                else:
                    key_content = content
                
                prompt += f"""
Episode {transcript['id']}: {transcript['title']}
Key Content: {key_content}

"""
            except Exception as e:
                logger.error(f"Error loading {transcript['transcript_path']}: {e}")
        
        # Add clear execution directive at the end
        prompt += f"""

EXECUTE NOW:
Write the complete daily podcast digest following the format above. Start with the markdown header and write the full digest - do not provide meta-commentary about the task. The output should be ready for TTS conversion.

Begin with: # Daily Podcast Digest - {datetime.now().strftime('%B %d, %Y')}
"""
        
        return prompt

    def generate_claude_digest(self) -> Optional[str]:
        """Generate digest using Claude Code headless mode with progress tracking"""
        
        logger.info("🧠 Generating Claude-powered digest")
        
        # Get transcripts
        transcripts = self.get_transcripts_for_claude()
        if not transcripts:
            logger.error("No transcripts available")
            return None
        
        logger.info(f"📊 Analyzing {len(transcripts)} transcripts with Claude")
        print(f"⏳ This will take 3-5 minutes to synthesize {len(transcripts)} episodes...")
        
        # Create prompt
        print("🔧 Preparing Claude prompt with instructions...")
        prompt = self.create_claude_digest_prompt(transcripts)
        print(f"📝 Prompt prepared ({len(prompt)} characters)")
        
        try:
            # Run Claude Code with progress monitoring
            print("🚀 Starting Claude Code analysis...")
            cmd = [self.claude_cmd, '-p', prompt]
            
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor progress
            import time
            start_time = time.time()
            
            while True:
                # Check if process is still running
                poll_result = process.poll()
                
                if poll_result is not None:
                    # Process completed
                    break
                
                # Show progress every 30 seconds
                elapsed = time.time() - start_time
                if elapsed > 0:
                    print(f"⏳ Claude analysis running... {elapsed:.0f}s elapsed")
                
                # Check timeout (5 minutes)
                if elapsed > 300:
                    print("⚠️  Analysis taking longer than expected, terminating...")
                    process.terminate()
                    return None
                
                time.sleep(30)  # Check every 30 seconds
            
            # Get results
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                digest_content = stdout.strip()
                
                if digest_content and len(digest_content) > 100:
                    elapsed = time.time() - start_time
                    print(f"✅ Claude analysis completed in {elapsed:.1f}s")
                    logger.info(f"✅ Claude digest generated ({len(digest_content)} characters)")
                    return digest_content
                else:
                    logger.error("Claude digest too short or empty")
                    return None
            else:
                logger.error(f"Claude Code failed: {stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error running Claude Code: {e}")
            return None

    def convert_claude_digest_to_audio(self, digest_content: str) -> Optional[str]:
        """Convert Claude-generated digest to TTS audio"""
        
        logger.info("🎙️ Converting Claude digest to audio")
        
        if not digest_content:
            logger.error("No digest content to convert")
            return None
        
        # Optimize content for TTS
        tts_optimized = self._optimize_for_tts(digest_content)
        
        # Generate audio file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        audio_path = self.output_dir / f"claude_digest_audio_{timestamp}.mp3"
        
        # Use professional host voice
        voice_config = self.tts_generator.voice_config["intro_outro"]
        
        success = self.tts_generator.generate_audio_segment(
            tts_optimized, voice_config, str(audio_path)
        )
        
        if success:
            # Save metadata
            metadata_path = audio_path.with_suffix('.json')
            metadata = {
                "title": f"Claude-Generated Daily Digest - {datetime.now().strftime('%B %d, %Y')}",
                "generated_by": "Claude Code + ElevenLabs TTS",
                "generation_time": datetime.now().isoformat(),
                "content_length": len(digest_content),
                "tts_optimized_length": len(tts_optimized),
                "audio_file": audio_path.name
            }
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            logger.info(f"✅ Claude digest audio generated: {audio_path.name}")
            return str(audio_path)
        else:
            logger.error("Failed to generate TTS audio")
            return None

    def _optimize_for_tts(self, content: str) -> str:
        """Optimize Claude digest content for TTS"""
        
        # Add podcast-style introduction
        date_str = datetime.now().strftime('%B %d, %Y')
        
        intro = f"""Welcome to your AI-powered Daily Podcast Digest for {date_str}. 
        
This digest was generated by Claude Code analysis of podcast transcripts, 
then synthesized into audio using ElevenLabs TTS.

"""
        
        # Clean up markdown for speech
        import re
        
        # Remove markdown headers
        content = re.sub(r'^#+\s*', '', content, flags=re.MULTILINE)
        
        # Convert markdown bold to emphasis
        content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)
        
        # Clean up formatting for speech
        content = re.sub(r'\n+', '. ', content)
        content = re.sub(r'\s+', ' ', content)
        
        # Add conclusion
        conclusion = """

That completes today's Claude-generated digest. Thank you for listening to your 
AI-powered Daily Podcast Digest."""
        
        return intro + content + conclusion

    def generate_topic_based_digests(self) -> Dict[str, str]:
        """Generate separate Claude digests for each topic"""
        
        logger.info("🎯 Generating topic-based Claude digests")
        
        # Get episodes and categorize by topic
        all_episodes = self.topic_compiler.get_processed_episodes()
        compilation_data = self.topic_compiler.compile_topics(all_episodes)
        
        # Extract episodes by topic from compilation data
        topic_episodes = {}
        for topic_key in self.topic_compiler.topic_definitions.keys():
            topic_episodes[topic_key] = []
        
        # Group episodes by their strongest topic
        for episode in all_episodes:
            content = self.topic_compiler._load_transcript_content(episode['transcript_path'])
            if not content:
                continue
                
            full_text = f"{episode['title']} {content}"
            best_topic = None
            best_score = 0.0
            
            for topic_key in self.topic_compiler.topic_definitions.keys():
                score = self.topic_compiler.analyze_topic_weight(full_text, topic_key)
                if score > best_score and score > 0.3:  # Minimum relevance threshold
                    best_score = score
                    best_topic = topic_key
            
            if best_topic:
                episode['topic_score'] = best_score
                topic_episodes[best_topic].append(episode)
        
        topic_digests = {}
        
        for topic_key, episodes in topic_episodes.items():
            if not episodes:
                logger.info(f"⏭️ Skipping {topic_key} - no episodes")
                continue
                
            logger.info(f"📝 Generating {topic_key} digest from {len(episodes)} episodes")
            
            # Create topic-specific prompt
            digest_content = self.generate_topic_digest(topic_key, episodes)
            
            if digest_content:
                topic_digests[topic_key] = digest_content
                logger.info(f"✅ {topic_key}: {len(digest_content)} characters")
            else:
                logger.error(f"❌ Failed to generate {topic_key} digest")
        
        return topic_digests

    def generate_topic_digest(self, topic_key: str, episodes: List[Dict]) -> Optional[str]:
        """Generate Claude digest for specific topic"""
        
        # Load instructions
        try:
            with open('claude_digest_instructions.md', 'r', encoding='utf-8') as f:
                instructions = f.read()
        except Exception as e:
            logger.warning(f"Could not load instructions file: {e}")
            return None
        
        # Get topic info
        topic_info = self.topic_compiler.topic_definitions.get(topic_key, {})
        topic_name = topic_info.get('display_name', topic_key)
        focus_area = topic_info.get('synthesis_focus', 'key insights')
        
        prompt = f"""
You are creating a focused topic segment for a daily podcast digest. Follow these guidelines:

{instructions}

CURRENT TASK:
Create a focused digest segment for the topic "{topic_name}" based on {len(episodes)} relevant episodes. Focus specifically on {focus_area}.

FORMAT REQUIREMENTS:
- Write 400-600 words for this topic segment
- Start with topic header: "## {topic_name}"
- Focus on cross-episode synthesis within this topic area
- Use engaging narrative suitable for audio
- End with 2-3 key takeaways specific to this topic

EPISODE DATA FOR {topic_name.upper()}:
"""
        
        # Add episode content for this topic
        for episode in episodes[:5]:  # Limit to top 5 episodes per topic
            try:
                with open(episode['transcript_path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract relevant sections
                if len(content) > 3000:
                    key_content = content[:1500] + "\n\n[...]\n\n" + content[-1000:]
                else:
                    key_content = content
                
                prompt += f"""
Episode: {episode['title']}
Relevance Score: {episode.get('topic_score', 'N/A')}
Key Content: {key_content}

"""
            except Exception as e:
                logger.error(f"Error loading {episode['transcript_path']}: {e}")
        
        prompt += f"""

EXECUTE NOW:
Write the complete {topic_name} segment following the format above. Focus only on this topic area and provide substantive analysis.

Begin with: ## {topic_name}
"""
        
        # Generate using Claude
        try:
            cmd = [self.claude_cmd, '-p', prompt]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            else:
                logger.error(f"Claude failed for {topic_key}: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating {topic_key} digest: {e}")
            return None

    def create_multi_topic_audio(self, topic_digests: Dict[str, str]) -> Optional[str]:
        """Create multi-topic audio with transitions"""
        
        logger.info("🎼 Creating multi-topic audio compilation")
        
        audio_segments = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Generate intro with joke and date
        jokes = [
            "Why don't podcasters ever get lost? Because they always follow their feed!",
            "What's a podcast's favorite type of music? Anything with good feeds and speeds!",
            "Why did the AI cross the road? To get to the other data!",
            "What do you call a podcast about gardening? A pod-cast!",
            "Why don't robots ever panic? They have excellent error handling!"
        ]
        
        import random
        daily_joke = random.choice(jokes)
        
        intro_text = f"""Welcome to your Daily Podcast Digest for {datetime.now().strftime('%B %d, %Y')}. 

Here's your daily tech joke: {daily_joke}

Today we'll explore {len(topic_digests)} key topic areas from our latest podcast episodes."""
        
        intro_path = self.output_dir / f"intro_{timestamp}.mp3"
        intro_voice = self.tts_generator.voice_config["intro_outro"]
        
        if self.tts_generator.generate_audio_segment(intro_text, intro_voice, str(intro_path)):
            audio_segments.append(str(intro_path))
        
        # Generate music transition using ElevenLabs
        transition_text = "♪ ♪ ♪"  # Musical notes for ElevenLabs to interpret as music
        music_voice = self.tts_generator.voice_config["intro_outro"]  # Use intro voice for music
        
        # Generate topic segments with specific voices and transitions
        topic_keys = list(topic_digests.keys())
        for i, (topic_key, digest_content) in enumerate(topic_digests.items()):
            topic_voice = self.tts_generator.voice_config.get(topic_key, self.tts_generator.voice_config["intro_outro"])
            topic_path = self.output_dir / f"topic_{topic_key}_{timestamp}.mp3"
            
            if self.tts_generator.generate_audio_segment(digest_content, topic_voice, str(topic_path)):
                audio_segments.append(str(topic_path))
                
                # Skip music transitions - ElevenLabs doesn't generate music properly
        
        # Generate outro with joke
        outro_jokes = [
            "Why do podcasts make terrible comedians? They always end on a cliffhanger!",
            "What's the difference between a podcast and a broken clock? The podcast is right way more than twice a day!",
            "Why don't AIs ever get tired? They run on renewable energy - data!",
            "What do you call a podcast host who never stops talking? Unemployed!",
            "Why was the neural network bad at dating? It kept overfitting!"
        ]
        
        outro_joke = random.choice(outro_jokes)
        
        outro_text = f"""That completes today's topic-based podcast digest. 

And here's your closing tech joke: {outro_joke}

Thanks for listening!"""
        outro_path = self.output_dir / f"outro_{timestamp}.mp3"
        
        if self.tts_generator.generate_audio_segment(outro_text, intro_voice, str(outro_path)):
            audio_segments.append(str(outro_path))
        
        # Simple audio concatenation using ffmpeg
        if len(audio_segments) > 1:
            final_path = self.output_dir / f"complete_topic_digest_{timestamp}.mp3"
            
            if self._concatenate_audio_segments(audio_segments, str(final_path)):
                logger.info(f"✅ Multi-topic audio created: {final_path.name}")
                return str(final_path)
        
        return None

    def _concatenate_audio_segments(self, segments: List[str], output_path: str) -> bool:
        """Simple audio concatenation without complex filters"""
        
        try:
            # Create temporary file list for ffmpeg with absolute paths
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for segment in segments:
                    abs_path = str(Path(segment).resolve())
                    if Path(abs_path).exists():
                        f.write(f"file '{abs_path}'\n")
                concat_list = f.name
            
            # Simple concatenation command - re-encode to avoid codec issues
            cmd = [
                'ffmpeg', '-f', 'concat', '-safe', '0', 
                '-i', concat_list, 
                '-c:a', 'mp3', '-b:a', '128k',
                output_path, 
                '-y'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Cleanup
            Path(concat_list).unlink(missing_ok=True)
            
            if result.returncode == 0:
                logger.info("✅ Audio segments concatenated successfully")
                
                # Clean up intermediate TTS files
                try:
                    for segment_file in segment_files:
                        Path(segment_file).unlink(missing_ok=True)
                    logger.info(f"🧹 Cleaned up {len(segment_files)} intermediate TTS files")
                except Exception as e:
                    logger.warning(f"⚠️ Cleanup warning: {e}")
                
                return True
            else:
                logger.error(f"❌ Concatenation failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error concatenating segments: {e}")
            return False

    def run_topic_based_workflow(self) -> Tuple[bool, Optional[str]]:
        """Complete workflow: Topic analysis → Claude digests → Multi-topic audio"""
        
        print("🎯🎙️ Topic-Based Claude + TTS Workflow")
        print("=" * 45)
        
        # Generate topic-based digests
        topic_digests = self.generate_topic_based_digests()
        
        if not topic_digests:
            print("❌ No topic digests generated")
            return False, None
        
        print(f"✅ Generated {len(topic_digests)} topic digests")
        
        # Create multi-topic audio
        audio_path = self.create_multi_topic_audio(topic_digests)
        
        if audio_path:
            file_size = Path(audio_path).stat().st_size / 1024 / 1024
            print(f"✅ Multi-topic audio: {Path(audio_path).name} ({file_size:.1f}MB)")
            return True, audio_path
        else:
            print("❌ Multi-topic audio generation failed")
            return False, None

    def run_claude_tts_workflow(self) -> Tuple[bool, Optional[str]]:
        """Complete workflow: Claude analysis → TTS audio"""
        
        print("🧠🎙️ Claude + TTS Workflow")
        print("=" * 35)
        
        # Generate Claude digest
        digest_content = self.generate_claude_digest()
        
        if not digest_content:
            print("❌ Claude digest generation failed")
            return False, None
        
        print(f"✅ Claude digest: {len(digest_content)} characters")
        
        # Convert to audio
        audio_path = self.convert_claude_digest_to_audio(digest_content)
        
        if audio_path:
            file_size = Path(audio_path).stat().st_size / 1024 / 1024
            print(f"✅ TTS audio: {Path(audio_path).name} ({file_size:.1f}MB)")
            return True, audio_path
        else:
            print("❌ TTS audio generation failed")
            return False, None


def main():
    """CLI entry point"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude-Powered TTS Generator")
    parser.add_argument('--digest-only', action='store_true', help='Generate digest text only')
    parser.add_argument('--audio-only', action='store_true', help='Convert existing digest to audio')
    parser.add_argument('--topic-based', action='store_true', help='Generate topic-based multi-voice compilation')
    args = parser.parse_args()
    
    generator = ClaudeTTSGenerator()
    
    if args.digest_only:
        print("📝 Generating Claude digest only...")
        digest = generator.generate_claude_digest()
        if digest:
            # Save full digest to file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            digest_path = generator.output_dir / f"claude_digest_full_{timestamp}.txt"
            
            with open(digest_path, 'w', encoding='utf-8') as f:
                f.write(digest)
            
            print("✅ Digest generated")
            print(f"📁 Full digest saved: {digest_path.name}")
            print("Preview:")
            print("-" * 40)
            print(digest[:500] + "..." if len(digest) > 500 else digest)
            return 0
        else:
            print("❌ Digest generation failed")
            return 1
    
    if args.topic_based:
        print("🎯 Running topic-based workflow...")
        success, audio_path = generator.run_topic_based_workflow()
        
        if success:
            # Mark episodes as digested and move transcripts
            transcripts = generator.get_transcripts_for_claude()
            episode_ids = [t['episode_id'] for t in transcripts]
            generator.mark_episodes_as_digested(episode_ids)
        
        return 0 if success else 1
    
    # Run complete workflow (original single digest)
    success, audio_path = generator.run_claude_tts_workflow()
    
    if success:
        # Mark episodes as digested and move transcripts
        transcripts = generator.get_transcripts_for_claude()
        episode_ids = [t['episode_id'] for t in transcripts]
        generator.mark_episodes_as_digested(episode_ids)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())