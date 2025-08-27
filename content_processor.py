#!/usr/bin/env python3
"""
Content Processing Pipeline
Downloads audio, extracts transcripts, analyzes content for news and insights
"""

import os
import sqlite3
import requests
import subprocess
import tempfile
import json
from pathlib import Path
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi
import re
import hashlib

# Parakeet MLX imports for Apple Silicon optimized ASR
try:
    from parakeet_mlx import from_pretrained
    import mlx.core as mx
    from parakeet_mlx.audio import get_logmel, load_audio
    PARAKEET_MLX_AVAILABLE = True
    print("✅ Parakeet MLX available - using Apple Silicon optimized ASR for RSS transcription")
except ImportError:
    PARAKEET_MLX_AVAILABLE = False
    print("⚠️ Parakeet MLX not available - falling back to Whisper for RSS transcription")
    print("Install with: pip install parakeet-mlx")

class ContentProcessor:
    def __init__(self, db_path="podcast_monitor.db", audio_dir="audio_cache", min_youtube_minutes=3.0):
        self.db_path = db_path
        self.audio_dir = Path(audio_dir)
        self.audio_dir.mkdir(exist_ok=True)
        self.min_youtube_minutes = min_youtube_minutes
        
        # Initialize Parakeet ASR models if available
        self.asr_model = None
        self.speaker_model = None
        
        if PARAKEET_MLX_AVAILABLE:
            self._initialize_parakeet_mlx_models()
    
    def _initialize_parakeet_mlx_models(self):
        """Initialize Parakeet MLX ASR models for Apple Silicon optimized podcast transcription"""
        try:
            print("Initializing Parakeet MLX models for Apple Silicon...")
            
            # Load Parakeet TDT model optimized for Apple Silicon
            # This model provides superior podcast accuracy with MLX acceleration
            model_name = "mlx-community/parakeet-tdt-0.6b-v2"
            print(f"Loading ASR model: {model_name}")
            
            self.asr_model = from_pretrained(model_name)
            
            print("✅ Parakeet MLX ASR model loaded successfully")
            print("🍎 Using Apple Silicon Metal Performance Shaders acceleration")
            
            # Note: Speaker diarization with MLX is a more complex implementation
            # For now, we'll focus on high-quality single/multi-speaker transcription
            # and add basic speaker detection based on audio characteristics
            self.speaker_model = None  # Will implement basic speaker detection
            
        except Exception as e:
            print(f"⚠️ Error loading Parakeet MLX models: {e}")
            print("Falling back to Whisper for RSS transcription")
            self.asr_model = None
    
    def process_episode(self, episode_id):
        """Process a single episode: download audio, extract transcript, analyze content"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get episode info
        cursor.execute('''
            SELECT e.id, e.episode_id, e.title, e.audio_url, f.type, f.topic_category
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            WHERE e.id = ? AND e.processed = 0
        ''', (episode_id,))
        
        episode = cursor.fetchone()
        if not episode:
            print(f"Episode {episode_id} not found or already processed")
            conn.close()
            return None
        
        ep_id, episode_guid, title, audio_url, feed_type, topic_category = episode
        print(f"Processing: {title}")
        
        try:
            if feed_type == 'youtube':
                transcript = self._process_youtube_episode(audio_url, episode_guid)
            else:
                transcript = self._process_rss_episode(audio_url, episode_guid)
            
            if transcript:
                # Save transcript
                transcript_path = self._save_transcript(episode_guid, transcript)
                
                # Analyze content
                analysis = self._analyze_content(transcript, topic_category)
                
                # Update database
                cursor.execute('''
                    UPDATE episodes 
                    SET transcript_path = ?, processed = 1, 
                        priority_score = ?, content_type = ?
                    WHERE id = ?
                ''', (transcript_path, analysis['priority_score'], analysis['content_type'], ep_id))
                
                conn.commit()
                print(f"✅ Processed successfully - Priority: {analysis['priority_score']:.2f}")
                
                return {
                    'episode_id': ep_id,
                    'transcript_path': transcript_path,
                    'analysis': analysis
                }
            else:
                # Check if this was a YouTube video that was skipped due to length
                if feed_type == 'youtube' and transcript is None:
                    cursor.execute('UPDATE episodes SET processed = -1 WHERE id = ?', (ep_id,))  # -1 = skipped
                    conn.commit()
                    print("⏭️ Skipped (too short)")
                else:
                    print("❌ Failed to extract transcript")
                return None
                
        except Exception as e:
            print(f"Error processing episode: {e}")
            return None
        finally:
            conn.close()
    
    def _process_youtube_episode(self, video_url, episode_id):
        """Extract transcript from YouTube video"""
        video_id = self._extract_youtube_video_id(video_url)
        if not video_id:
            print(f"Could not extract video ID from {video_url}")
            return None
        
        try:
            # Create API instance and fetch transcript
            api = YouTubeTranscriptApi()
            transcript_data = api.fetch(video_id, languages=['en'])
            
            # Check video length before processing
            if not transcript_data:
                print("No transcript data available")
                return None
            
            # Get total duration from last transcript entry
            last_entry = transcript_data[-1]
            total_duration = last_entry.start + getattr(last_entry, 'duration', 0)
            duration_minutes = total_duration / 60
            
            # Skip videos shorter than minimum threshold
            if duration_minutes < self.min_youtube_minutes:
                print(f"Skipping short video ({duration_minutes:.1f} minutes) - only processing videos >{self.min_youtube_minutes} minutes")
                return None
            
            print(f"Processing video ({duration_minutes:.1f} minutes)")
            
            # Format transcript with timestamps
            transcript_lines = []
            for entry in transcript_data:
                timestamp = entry.start
                text = entry.text.strip()
                minutes = int(timestamp // 60)
                seconds = int(timestamp % 60)
                transcript_lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")
            
            return "\n".join(transcript_lines)
            
        except Exception as e:
            print(f"Error extracting YouTube transcript: {e}")
            return None
    
    def _process_rss_episode(self, audio_url, episode_id):
        """Download RSS audio and convert to transcript using ffmpeg + Whisper"""
        if not audio_url:
            print("No audio URL provided")
            return None
        
        try:
            # Download audio file
            audio_file = self._download_audio(audio_url, episode_id)
            if not audio_file:
                return None
            
            # Convert to transcript using Whisper
            transcript = self._audio_to_transcript(audio_file)
            
            # Clean up audio file (optional - keep for caching)
            # os.remove(audio_file)
            
            return transcript
            
        except Exception as e:
            print(f"Error processing RSS audio: {e}")
            return None
    
    def _download_audio(self, audio_url, episode_id):
        """Download audio file from RSS feed"""
        try:
            # Create filename based on episode ID
            file_hash = hashlib.md5(episode_id.encode()).hexdigest()[:8]
            audio_file = self.audio_dir / f"{file_hash}.mp3"
            
            # Skip if already exists
            if audio_file.exists():
                print(f"Audio file already exists: {audio_file}")
                return str(audio_file)
            
            print(f"Downloading audio from {audio_url}")
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
            response = requests.get(audio_url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(audio_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"Downloaded: {audio_file} ({audio_file.stat().st_size} bytes)")
            return str(audio_file)
            
        except Exception as e:
            print(f"Error downloading audio: {e}")
            return None
    
    def _audio_to_transcript(self, audio_file):
        """Convert audio to transcript using Parakeet MLX ASR or fallback to Whisper"""
        # Try Parakeet MLX first if available
        if PARAKEET_MLX_AVAILABLE and self.asr_model is not None:
            return self._parakeet_mlx_transcribe(audio_file)
        else:
            # Fallback to original Whisper method
            return self._whisper_transcribe(audio_file)
    
    def _parakeet_mlx_transcribe(self, audio_file):
        """High-quality podcast transcription using Parakeet MLX for Apple Silicon"""
        try:
            print("🎯 Transcribing with Parakeet MLX (Apple Silicon optimized)...")
            
            # Get audio file info for progress estimation
            probe_cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', audio_file]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            duration_seconds = 0
            if probe_result.returncode == 0 and probe_result.stdout.strip():
                try:
                    duration_seconds = float(probe_result.stdout.strip())
                    print(f"📊 Audio duration: {duration_seconds/60:.1f} minutes")
                except:
                    pass
            
            print("Running Parakeet MLX ASR inference...")
            if duration_seconds > 300:  # > 5 minutes
                print("⏳ Large audio file detected - this may take several minutes...")
                print("💡 Progress: Parakeet processes ~2min chunks with Apple Silicon acceleration")
            
            # Perform transcription using the MLX model with chunking for long audio
            import time
            start_time = time.time()
            
            result = self.asr_model.transcribe(
                audio_file,
                chunk_duration=60 * 2.0,  # 2 minutes per chunk
                overlap_duration=15.0     # 15 seconds overlap
            )
            
            processing_time = time.time() - start_time
            transcription = result.text
            
            if duration_seconds > 0:
                rtf = processing_time / duration_seconds  # Real-time factor
                print(f"⚡ Processing: {processing_time:.1f}s for {duration_seconds:.1f}s audio (RTF: {rtf:.2f}x)")
            else:
                print(f"⚡ Processing completed in {processing_time:.1f}s")
            
            if not transcription or not transcription.strip():
                print("❌ Parakeet MLX transcription failed - no output")
                return None
            
            transcript_text = transcription.strip()
            print(f"✅ Parakeet MLX transcription complete ({len(transcript_text)} chars)")
            
            # Add basic speaker detection based on audio characteristics
            # (MLX speaker diarization would require additional implementation)
            transcript_text = self._add_basic_speaker_detection(transcript_text, audio_file)
            
            return transcript_text
            
        except Exception as e:
            print(f"⚠️ Parakeet MLX transcription error: {e}")
            print("Falling back to Whisper...")
            return self._whisper_transcribe(audio_file)
    
    def _add_basic_speaker_detection(self, transcript_text, audio_file):
        """Add basic speaker detection based on audio characteristics and transcript analysis"""
        try:
            print("Analyzing audio for multi-speaker characteristics...")
            
            # Basic heuristics for speaker detection
            # 1. Check transcript length and structure
            # 2. Look for conversational patterns
            # 3. Analyze audio file duration and characteristics
            
            # Get audio file size and duration estimate
            file_size = os.path.getsize(audio_file)
            duration_estimate = file_size / (16000 * 2)  # rough estimate for 16kHz 16-bit
            
            # Analyze transcript for conversation indicators
            conversation_indicators = [
                'yeah', 'right', 'exactly', 'I think', 'you know', 'well',
                'so', 'but', 'and then', 'question:', 'answer:', 'host:',
                'guest:', 'interviewer:', 'speaker'
            ]
            
            indicator_count = sum(1 for indicator in conversation_indicators 
                                if indicator.lower() in transcript_text.lower())
            
            # Check for dialogue patterns (question-answer, back-and-forth)
            sentences = transcript_text.split('.')
            short_responses = sum(1 for sentence in sentences if len(sentence.strip()) < 50)
            
            # Determine if likely multi-speaker based on heuristics
            is_likely_conversation = (
                duration_estimate > 300 and  # > 5 minutes
                indicator_count > 5 and      # Conversational language
                short_responses > 3 and      # Short back-and-forth responses
                len(transcript_text) > 1000  # Substantial content
            )
            
            if is_likely_conversation:
                print("📻 Multi-speaker conversation characteristics detected")
                return f"[CONVERSATION DETECTED - Multiple speakers likely present]\n\n{transcript_text}"
            else:
                print("🎙️ Single-speaker monologue characteristics")
                return transcript_text
            
        except Exception as e:
            print(f"Speaker detection error: {e}")
            return transcript_text
    
    
    def _whisper_transcribe(self, audio_file):
        """Fallback transcription using original Whisper method"""
        try:
            print("🔄 Using Whisper fallback...")
            
            # Handle WAV conversion - skip if already correct format
            if audio_file.endswith('.wav'):
                # Check if already in correct format (16kHz mono)
                probe_cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'stream=sample_rate,channels', '-of', 'csv=p=0', audio_file]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                
                if probe_result.returncode == 0:
                    lines = probe_result.stdout.strip().split('\n')
                    if lines and '16000,1' in lines[0]:
                        # Already correct format - use directly
                        wav_file = audio_file
                        print("Audio already in correct format (16kHz mono)")
                    else:
                        # Need to convert existing WAV to correct format
                        wav_file = audio_file.replace('.wav', '_converted.wav')
                        ffmpeg_cmd = [
                            'ffmpeg', '-i', audio_file, 
                            '-ar', '16000',  # 16kHz sample rate
                            '-ac', '1',      # mono
                            '-y',            # overwrite
                            wav_file
                        ]
                        print("Converting WAV to correct format...")
                        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                        if result.returncode != 0:
                            print(f"ffmpeg error: {result.stderr}")
                            return None
                else:
                    # ffprobe failed, try conversion anyway
                    wav_file = audio_file.replace('.wav', '_converted.wav')
                    ffmpeg_cmd = [
                        'ffmpeg', '-i', audio_file, 
                        '-ar', '16000',  # 16kHz sample rate
                        '-ac', '1',      # mono
                        '-y',            # overwrite
                        wav_file
                    ]
                    print("Converting audio format...")
                    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        print(f"ffmpeg error: {result.stderr}")
                        return None
            else:
                # Convert MP3 to WAV
                wav_file = audio_file.replace('.mp3', '.wav')
                ffmpeg_cmd = [
                    'ffmpeg', '-i', audio_file, 
                    '-ar', '16000',  # 16kHz sample rate
                    '-ac', '1',      # mono
                    '-y',            # overwrite
                    wav_file
                ]
                print("Converting audio format...")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"ffmpeg error: {result.stderr}")
                    return None
            
            # Use Whisper for transcription (requires whisper installation)
            print("Transcribing audio...")
            whisper_cmd = ['whisper', wav_file, '--model', 'base', '--output_format', 'txt']
            
            result = subprocess.run(whisper_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Whisper error: {result.stderr}")
                # Fallback: try with different model
                whisper_cmd = ['whisper', wav_file, '--model', 'tiny', '--output_format', 'txt']
                result = subprocess.run(whisper_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Whisper fallback failed: {result.stderr}")
                    return None
            
            # Read transcript file
            transcript_file = wav_file.replace('.wav', '.txt')
            if os.path.exists(transcript_file):
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    transcript = f.read().strip()
                
                # Clean up temporary files
                os.remove(wav_file)
                os.remove(transcript_file)
                
                return transcript
            else:
                print("Transcript file not found")
                return None
                
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return None
    
    def _extract_youtube_video_id(self, video_url):
        """Extract YouTube video ID from URL"""
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:watch\?v=)([0-9A-Za-z_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)
        return None
    
    def _save_transcript(self, episode_id, transcript):
        """Save transcript to file"""
        transcript_dir = Path("transcripts")
        transcript_dir.mkdir(exist_ok=True)
        
        file_hash = hashlib.md5(episode_id.encode()).hexdigest()[:8]
        transcript_path = transcript_dir / f"{file_hash}.txt"
        
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcript)
        
        return str(transcript_path)
    
    def _analyze_content(self, transcript, topic_category):
        """Analyze transcript content for news extraction and priority scoring"""
        # Basic content analysis (will be enhanced with LLM integration)
        analysis = {
            'priority_score': 0.0,
            'content_type': 'discussion',
            'key_topics': [],
            'sentiment': 'neutral',
            'announcements': [],
            'insights': []
        }
        
        # Simple keyword-based priority scoring
        high_priority_keywords = [
            'launch', 'announce', 'release', 'unveil', 'introduce',
            'breakthrough', 'revolutionary', 'first', 'new product',
            'competition', 'merger', 'acquisition', 'partnership'
        ]
        
        medium_priority_keywords = [
            'update', 'improve', 'enhance', 'expand', 'growth',
            'trend', 'analysis', 'insight', 'strategy', 'future'
        ]
        
        # Count keyword matches
        transcript_lower = transcript.lower()
        high_matches = sum(1 for keyword in high_priority_keywords if keyword in transcript_lower)
        medium_matches = sum(1 for keyword in medium_priority_keywords if keyword in transcript_lower)
        
        # Calculate priority score (0.0 - 1.0)
        base_score = (high_matches * 0.8 + medium_matches * 0.3) / 10
        analysis['priority_score'] = min(base_score, 1.0)
        
        # Determine content type
        if high_matches > 2:
            analysis['content_type'] = 'announcement'
        elif 'interview' in transcript_lower or 'conversation' in transcript_lower:
            analysis['content_type'] = 'interview'
        else:
            analysis['content_type'] = 'discussion'
        
        # Extract potential announcements (simple regex for now)
        announcement_patterns = [
            r'(?i)(we are|we\'re)\s+(launching|releasing|announcing|introducing)\s+([^.]+)',
            r'(?i)(today|this week)\s+we\s+(launch|release|announce|introduce)\s+([^.]+)'
        ]
        
        for pattern in announcement_patterns:
            matches = re.findall(pattern, transcript)
            for match in matches:
                analysis['announcements'].append(' '.join(match))
        
        return analysis
    
    def process_all_pending(self):
        """Process all unprocessed episodes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM episodes WHERE processed = 0')
        pending_episodes = cursor.fetchall()
        conn.close()
        
        results = []
        for (episode_id,) in pending_episodes:
            result = self.process_episode(episode_id)
            if result:
                results.append(result)
        
        return results
    
    def get_processed_episodes(self, min_priority=0.3):
        """Get processed episodes above minimum priority threshold"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT e.id, e.title, e.published_date, e.transcript_path, 
                   e.priority_score, e.content_type, f.title as feed_title, f.topic_category
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            WHERE e.processed = 1 AND e.priority_score >= ?
            ORDER BY e.priority_score DESC, e.published_date DESC
        ''', (min_priority,))
        
        episodes = []
        for row in cursor.fetchall():
            episodes.append({
                'id': row[0],
                'title': row[1],
                'published_date': row[2],
                'transcript_path': row[3],
                'priority_score': row[4],
                'content_type': row[5],
                'feed_title': row[6],
                'topic_category': row[7]
            })
        
        conn.close()
        return episodes
    
    def get_processing_stats(self):
        """Get statistics on episode processing"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Count by processing status
        cursor.execute('''
            SELECT 
                COUNT(CASE WHEN processed = 1 THEN 1 END) as processed,
                COUNT(CASE WHEN processed = 0 THEN 1 END) as pending,
                COUNT(CASE WHEN processed = -1 THEN 1 END) as skipped,
                f.type,
                f.topic_category
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            GROUP BY f.type, f.topic_category
        ''')
        
        stats = cursor.fetchall()
        conn.close()
        
        return {
            'by_source': stats,
            'min_youtube_minutes': self.min_youtube_minutes
        }

def main():
    """CLI interface for content processing"""
    processor = ContentProcessor()
    
    print("Daily Podcast Digest - Content Processor")
    print("========================================")
    
    # Check system dependencies
    print("Checking dependencies...")
    
    # Check ffmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ ffmpeg available")
        else:
            print("❌ ffmpeg not found - required for audio conversion")
    except FileNotFoundError:
        print("❌ ffmpeg not installed - install with: brew install ffmpeg")
    
    # Check ASR engines
    if PARAKEET_MLX_AVAILABLE:
        print("✅ Parakeet MLX available - using Apple Silicon optimized ASR for RSS transcription")
        if processor.asr_model:
            print("✅ Parakeet MLX ASR model loaded successfully")
            print("🍎 Apple Silicon Metal acceleration enabled")
        print("✅ Basic speaker detection available")
    else:
        print("⚠️ Parakeet MLX not available - using Whisper fallback")
        print("   Install Parakeet MLX with: pip install parakeet-mlx")
    
    # Check Whisper (fallback)
    try:
        result = subprocess.run(['whisper', '--help'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Whisper available (fallback)")
        else:
            print("❌ Whisper not found - required for fallback transcription")
    except FileNotFoundError:
        print("❌ Whisper not installed - install with: pip install openai-whisper")
    
    # Process pending episodes
    print("\nProcessing all pending episodes...")
    results = processor.process_all_pending()
    
    if results:
        print(f"\n✅ Processed {len(results)} episodes")
        
        # Show high-priority results
        high_priority = processor.get_processed_episodes(min_priority=0.5)
        if high_priority:
            print(f"\nHigh-priority content ({len(high_priority)} episodes):")
            for ep in high_priority[:5]:  # Show top 5
                print(f"  🎯 {ep['title']}")
                print(f"     Priority: {ep['priority_score']:.2f} | Type: {ep['content_type']}")
                print(f"     Source: {ep['feed_title']} ({ep['topic_category']})")
                print()
    else:
        print("No episodes to process")

if __name__ == "__main__":
    main()