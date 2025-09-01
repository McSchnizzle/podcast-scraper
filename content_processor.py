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
from openai_scorer import OpenAITopicScorer

# ASR backend detection and imports
import platform
import os
import logging

# Parakeet MLX for Apple Silicon (local development)
try:
    from parakeet_mlx import from_pretrained
    import mlx.core as mx
    from parakeet_mlx.audio import get_logmel, load_audio
    PARAKEET_MLX_AVAILABLE = True
    print("✅ Parakeet MLX available - using Apple Silicon optimized ASR")
except ImportError:
    PARAKEET_MLX_AVAILABLE = False

# Faster-Whisper for cross-platform (GitHub Actions, etc.) - 4x faster than OpenAI Whisper
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
    if not PARAKEET_MLX_AVAILABLE:
        print("✅ Faster-Whisper available - using optimized cross-platform ASR")
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

# Fallback to OpenAI Whisper if faster-whisper not available
try:
    import whisper
    WHISPER_AVAILABLE = True
    if not PARAKEET_MLX_AVAILABLE and not FASTER_WHISPER_AVAILABLE:
        print("✅ OpenAI Whisper available - using cross-platform ASR")
except ImportError:
    WHISPER_AVAILABLE = False

# Environment detection
IS_GITHUB_ACTIONS = os.getenv('GITHUB_ACTIONS') == 'true'
IS_APPLE_SILICON = platform.machine() == 'arm64' and platform.system() == 'Darwin'

# Determine ASR backend
if IS_APPLE_SILICON and PARAKEET_MLX_AVAILABLE and not IS_GITHUB_ACTIONS:
    ASR_BACKEND = 'parakeet_mlx'
    print("🍎 Using Parakeet MLX (Apple Silicon optimized)")
elif FASTER_WHISPER_AVAILABLE:
    ASR_BACKEND = 'faster_whisper'
    print("⚡ Using Faster-Whisper (4x faster cross-platform)")
elif WHISPER_AVAILABLE:
    ASR_BACKEND = 'whisper'
    print("🌐 Using OpenAI Whisper (cross-platform)")
else:
    ASR_BACKEND = None
    print("❌ No ASR backend available")
    if not IS_GITHUB_ACTIONS:  # Only raise error in local dev, not in CI
        raise ImportError("No ASR backend available. Install faster-whisper, whisper, or parakeet-mlx")

class ContentProcessor:
    def __init__(self, db_path="podcast_monitor.db", audio_dir="audio_cache", min_youtube_minutes=3.0):
        self.db_path = db_path
        self.audio_dir = Path(audio_dir)
        self.audio_dir.mkdir(exist_ok=True)
        self.min_youtube_minutes = min_youtube_minutes
        
        # Initialize OpenAI scorer for topic relevance
        self.openai_scorer = OpenAITopicScorer(db_path)
        
        # Initialize ASR models based on environment
        self.asr_model = None
        self.speaker_model = None
        self.asr_backend = ASR_BACKEND
        self._initialize_asr_models()
    
    def _initialize_asr_models(self):
        """Initialize ASR models based on detected backend"""
        if self.asr_backend == 'parakeet_mlx':
            self._initialize_parakeet_mlx_models()
        elif self.asr_backend == 'faster_whisper':
            self._initialize_faster_whisper_models()
        elif self.asr_backend == 'whisper':
            self._initialize_whisper_models()
        else:
            print("⚠️ No ASR backend available - audio processing will be skipped")
    
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
            print(f"❌ Error loading Parakeet MLX models: {e}")
            print("Cannot proceed without Parakeet MLX ASR")
            raise RuntimeError(f"Failed to initialize Parakeet MLX: {e}")
    
    def _initialize_whisper_models(self):
        """Initialize OpenAI Whisper models for cross-platform transcription"""
        try:
            print("Initializing OpenAI Whisper models...")
            
            # Use medium model for good quality/speed balance
            # Options: tiny, base, small, medium, large
            model_name = "medium"
            print(f"Loading Whisper model: {model_name}")
            
            self.asr_model = whisper.load_model(model_name)
            
            print("✅ OpenAI Whisper ASR model loaded successfully")
            print("🌐 Using cross-platform Whisper transcription")
            
            # Whisper doesn't have separate speaker models
            self.speaker_model = None
            
        except Exception as e:
            print(f"❌ Error loading Whisper models: {e}")
            print("Cannot proceed without Whisper ASR")
            raise RuntimeError(f"Failed to initialize Whisper: {e}")
    
    def _initialize_faster_whisper_models(self):
        """Initialize Faster-Whisper models for optimized cross-platform transcription"""
        try:
            print("Initializing Faster-Whisper models...")
            
            # Use medium model for good quality/speed balance
            # Available models: tiny, base, small, medium, large-v1, large-v2, large-v3, turbo
            model_size = "medium"
            print(f"Loading Faster-Whisper model: {model_size}")
            
            # Initialize with optimizations for CPU
            self.asr_model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",  # Use int8 for faster CPU inference
                num_workers=4,  # Use multiple threads
                download_root=None  # Use default cache
            )
            
            print("✅ Faster-Whisper ASR model loaded successfully")
            print("⚡ Using optimized CTranslate2 engine (4x faster)")
            
            # Faster-Whisper doesn't have separate speaker models
            self.speaker_model = None
            
        except Exception as e:
            print(f"❌ Error loading Faster-Whisper models: {e}")
            print("Cannot proceed without Faster-Whisper ASR")
            raise RuntimeError(f"Failed to initialize Faster-Whisper: {e}")
    
    def process_episode(self, episode_id):
        """Process a single episode: download audio, extract transcript, analyze content"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get episode info with feed details
        cursor.execute('''
            SELECT e.id, e.episode_id, e.title, e.audio_url, f.type, f.topic_category, f.title
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            WHERE e.id = ? AND e.status IN ('downloaded', 'pre-download')
        ''', (episode_id,))
        
        episode = cursor.fetchone()
        if not episode:
            print(f"Episode {episode_id} not found or already transcribed")
            conn.close()
            return None
        
        ep_id, episode_guid, title, audio_url, feed_type, topic_category, feed_title = episode
        print(f"\n🎬 Processing Episode from {feed_title}")
        print(f"📺 Title: {title}")
        print(f"🔖 Category: {topic_category or 'General'}")
        print(f"⚙️ Type: {feed_type}")
        
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
                
                # Score episode with OpenAI for topic relevance
                topic_scores = None
                if self.openai_scorer.api_available:
                    print(f"🤖 Scoring episode topics with OpenAI...")
                    try:
                        topic_scores = self.openai_scorer.score_transcript(transcript, episode_guid)
                        if topic_scores and not topic_scores.get('error'):
                            print(f"✅ Topic scoring completed")
                            # Show top 2 scoring topics
                            topic_items = [(k, v) for k, v in topic_scores.items() 
                                         if k in ['Technology', 'Business', 'Philosophy', 'Politics', 'Culture']
                                         and isinstance(v, (int, float))]
                            if topic_items:
                                top_topics = sorted(topic_items, key=lambda x: x[1], reverse=True)[:2]
                                for topic, score in top_topics:
                                    print(f"   {topic}: {score:.2f}")
                        else:
                            print("⚠️ Topic scoring failed, proceeding without scores")
                    except Exception as e:
                        print(f"⚠️ Topic scoring error: {e}")
                        topic_scores = None
                else:
                    print("⏭️ OpenAI API not available, skipping topic scoring")
                
                # Update database with transcript and analysis
                if topic_scores:
                    cursor.execute('''
                        UPDATE episodes 
                        SET transcript_path = ?, status = 'transcribed', 
                            priority_score = ?, content_type = ?, 
                            topic_relevance_json = ?, scores_version = ?
                        WHERE id = ?
                    ''', (transcript_path, analysis['priority_score'], analysis['content_type'], 
                         json.dumps(topic_scores), topic_scores.get('version', '1.0'), ep_id))
                else:
                    cursor.execute('''
                        UPDATE episodes 
                        SET transcript_path = ?, status = 'transcribed', 
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
                    cursor.execute('UPDATE episodes SET status = ? WHERE id = ?', ('failed', ep_id))
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
        """Extract transcript from YouTube video with GitHub Actions fallback"""
        video_id = self._extract_youtube_video_id(video_url)
        if not video_id:
            print(f"Could not extract video ID from {video_url}")
            return None
        
        try:
            # Check if we're in GitHub Actions environment
            is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
            
            if is_github_actions:
                print("🚨 Running in GitHub Actions - YouTube API may be blocked by cloud IPs")
                print("💡 Attempting YouTube transcript API with timeout...")
            
            # Fetch transcript with reduced timeout in GitHub Actions
            api = YouTubeTranscriptApi()
            
            # Simple timeout approach for GitHub Actions (Linux)
            if is_github_actions:
                import threading
                import time
                
                class TimeoutError(Exception):
                    pass
                
                transcript_data = None
                exception_occurred = None
                
                def fetch_with_timeout():
                    nonlocal transcript_data, exception_occurred
                    try:
                        transcript_data = api.fetch(video_id, languages=['en'])
                    except Exception as e:
                        exception_occurred = e
                
                # Start fetch in thread with timeout
                thread = threading.Thread(target=fetch_with_timeout)
                thread.daemon = True
                thread.start()
                thread.join(timeout=15)  # 15 second timeout
                
                if thread.is_alive():
                    raise TimeoutError("YouTube API request timed out in GitHub Actions")
                
                if exception_occurred:
                    raise exception_occurred
                    
                if transcript_data is None:
                    raise RuntimeError("YouTube API request failed")
            else:
                # Normal fetch for local development
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
                reason = f"Skipped: Video too short ({duration_minutes:.1f} minutes, minimum: {self.min_youtube_minutes} minutes)"
                print(reason)
                
                # Log skip reason to database
                self._log_episode_failure(video_url, reason)
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
            error_msg = str(e)
            is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
            
            if is_github_actions:
                if "blocked" in error_msg.lower() or "forbidden" in error_msg.lower() or "timeout" in error_msg.lower():
                    skip_reason = "YouTube API blocked by GitHub Actions cloud IPs - requires local processing"
                    print(f"🚨 GitHub Actions limitation: {skip_reason}")
                    self._log_episode_failure(video_url, f"GITHUB_ACTIONS_SKIP: {skip_reason}")
                    return None
            
            print(f"Error extracting YouTube transcript: {error_msg}")
            
            # Log failure reason to database
            self._log_episode_failure(video_url, f"YouTube: {error_msg}")
            return None
    
    def _process_rss_episode(self, audio_url, episode_id):
        """Download RSS audio and convert to transcript using Parakeet MLX ASR"""
        if not audio_url:
            print("No audio URL provided")
            return None
        
        try:
            # Download audio file
            audio_file = self._download_audio(audio_url, episode_id)
            if not audio_file:
                return None
            
            # Convert to transcript using Parakeet MLX
            transcript = self._audio_to_transcript(audio_file)
            
            # Note: Audio file cleanup now handled by workflow after database update
            # This ensures we only delete files after successful processing and DB update
            
            return transcript
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error processing RSS audio: {error_msg}")
            
            # Log failure reason to database
            self._log_episode_failure(episode_id, f"RSS: {error_msg}")
            return None
    
    def _download_audio(self, audio_url, episode_id):
        """Download audio file from RSS feed or use local file if path provided"""
        try:
            # Check if this is a local file path
            if os.path.exists(audio_url):
                print(f"Using local audio file: {audio_url}")
                return audio_url
            
            # Use episode_id directly as filename (should already be 8-char hash)
            file_hash = episode_id
            # Preserve original extension if possible
            if audio_url.endswith('.wav'):
                audio_file = self.audio_dir / f"{file_hash}.wav"
            elif audio_url.endswith('.m4a'):
                audio_file = self.audio_dir / f"{file_hash}.m4a"
            else:
                audio_file = self.audio_dir / f"{file_hash}.mp3"
            
            # Skip if already exists
            if audio_file.exists():
                print(f"Audio file already exists: {audio_file}")
                return str(audio_file)
            
            print(f"Downloading audio from {audio_url}")
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
            # Follow redirects and increase timeout for large podcast files
            response = requests.get(audio_url, headers=headers, stream=True, timeout=120, allow_redirects=True)
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
        """Convert audio to transcript using available ASR backend"""
        if self.asr_model is None:
            raise RuntimeError("ASR model not initialized")
        
        if self.asr_backend == 'parakeet_mlx':
            return self._parakeet_mlx_transcribe(audio_file)
        elif self.asr_backend == 'faster_whisper':
            return self._faster_whisper_transcribe(audio_file)
        elif self.asr_backend == 'whisper':
            return self._whisper_transcribe(audio_file)
        else:
            raise RuntimeError(f"Unsupported ASR backend: {self.asr_backend}")
    
    def _parakeet_mlx_transcribe(self, audio_file):
        """High-quality podcast transcription using robust workflow with progress monitoring"""
        try:
            # Import the robust transcriber
            from robust_transcriber import RobustTranscriber
            
            # Create transcriber instance (reuse existing model if possible)
            transcriber = RobustTranscriber()
            if self.asr_model:
                transcriber.asr_model = self.asr_model
            
            # Use the robust transcription workflow
            transcript_text = transcriber.transcribe_file(audio_file)
            
            if not transcript_text:
                print("❌ Robust transcription workflow failed")
                return None
            
            # Add basic speaker detection
            transcript_text = self._add_basic_speaker_detection(transcript_text, audio_file)
            
            return transcript_text
            
        except Exception as e:
            print(f"❌ Parakeet MLX transcription failed: {e}")
            raise RuntimeError(f"Transcription failed: {e}")
    
    def _whisper_transcribe(self, audio_file):
        """Cross-platform transcription using OpenAI Whisper"""
        try:
            print(f"🌐 Transcribing with Whisper: {audio_file}")
            
            # Transcribe with Whisper (force FP32 for CPU compatibility)
            result = self.asr_model.transcribe(
                str(audio_file),
                language=None,  # Auto-detect language
                task="transcribe",  # Not translate
                verbose=False,
                fp16=False  # Explicitly disable FP16 to avoid CPU warnings
            )
            
            # Extract text from segments with timestamps
            transcript_lines = []
            for segment in result.get('segments', []):
                start_time = segment.get('start', 0)
                text = segment.get('text', '').strip()
                
                if text:
                    minutes = int(start_time // 60)
                    seconds = int(start_time % 60)
                    transcript_lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")
            
            transcript_text = "\n".join(transcript_lines)
            
            if not transcript_text:
                raise RuntimeError("No transcription content generated")
            
            print(f"✅ Whisper transcription complete: {len(transcript_text)} characters")
            
            # Add basic speaker detection (Whisper doesn't do speaker diarization)
            transcript_text = self._add_basic_speaker_detection(transcript_text, audio_file)
            
            return transcript_text
            
        except Exception as e:
            print(f"❌ Whisper transcription failed: {e}")
            raise RuntimeError(f"Transcription failed: {e}")
    
    def _faster_whisper_transcribe(self, audio_file):
        """Enhanced chunked transcription using Faster-Whisper with Parakeet-style logging"""
        try:
            print(f"\n🎯 Starting Faster-Whisper transcription: {Path(audio_file).name}")
            
            # Use the robust chunking workflow similar to Parakeet
            import time
            import subprocess
            import math
            
            # Step 1: Estimate duration and determine chunking strategy with detailed logging
            duration = self._get_audio_duration(audio_file)
            if duration == 0:
                print("❌ Could not analyze audio file")
                raise RuntimeError("Could not analyze audio file")
            
            # Enhanced analysis display
            file_size_mb = Path(audio_file).stat().st_size / (1024*1024)
            max_chunk_duration = 600  # 10 minutes
            num_chunks = math.ceil(duration / max_chunk_duration)
            
            # Estimate processing time using Faster-Whisper performance metrics
            # Faster-Whisper is typically 4x faster than OpenAI Whisper, so ~0.05-0.1x RTF
            estimated_rtf = 0.08  # Conservative estimate for CPU processing
            estimated_total_time = duration * estimated_rtf
            if num_chunks > 1:
                estimated_total_time += num_chunks * 10  # Add chunking overhead
            
            print(f"📊 Audio Analysis Complete:")
            print(f"   • File: {Path(audio_file).name} ({file_size_mb:.1f}MB)")
            print(f"   • Duration: {duration/60:.1f} minutes ({duration:.1f}s)")
            print(f"   • Chunks: {num_chunks} × {max_chunk_duration//60}min")
            print(f"   • Estimated processing time: {estimated_total_time/60:.1f} minutes")
            print(f"   • Target RTF: ~{estimated_rtf:.3f}x (4x faster than Whisper)")
            
            # Step 2: Split into chunks if needed with enhanced logging
            chunks = self._split_audio_for_faster_whisper(audio_file, max_chunk_duration)
            if not chunks:
                print("❌ Failed to prepare file for transcription")
                raise RuntimeError("Failed to prepare audio chunks")
            
            # Step 3: Process each chunk with detailed progress tracking
            all_transcripts = []
            total_chars = 0
            total_processing_time = 0
            
            print(f"\n🚀 Starting Faster-Whisper transcription pipeline...")
            print(f"{'='*60}")
            overall_start = time.time()
            
            for i, chunk_file in enumerate(chunks, 1):
                chunk_path = Path(chunk_file)
                chunk_size_mb = chunk_path.stat().st_size / (1024*1024)
                chunk_duration = self._get_audio_duration(chunk_file)
                
                print(f"\n🎬 Processing Chunk {i}/{len(chunks)}")
                print(f"   📄 File: {chunk_path.name}")
                print(f"   📏 Size: {chunk_size_mb:.1f}MB")
                print(f"   ⏱️  Duration: {chunk_duration/60:.1f}min")
                
                # Estimate this chunk's processing time
                chunk_est_time = chunk_duration * estimated_rtf
                print(f"   🎯 Estimated processing: {chunk_est_time:.1f}s")
                
                chunk_start_time = time.time()
                chunk_transcript = self._transcribe_faster_whisper_chunk(chunk_file, i, len(chunks))
                chunk_processing_time = time.time() - chunk_start_time
                total_processing_time += chunk_processing_time
                
                if chunk_transcript:
                    all_transcripts.append(chunk_transcript)
                    total_chars += len(chunk_transcript)
                    
                    # Calculate actual performance metrics
                    actual_rtf = chunk_processing_time / chunk_duration if chunk_duration > 0 else 0
                    speedup = chunk_est_time / chunk_processing_time if chunk_processing_time > 0 else 1
                    
                    print(f"   ✅ Transcription complete!")
                    print(f"   📊 Performance: {chunk_processing_time:.1f}s actual (RTF: {actual_rtf:.3f}x)")
                    print(f"   📝 Output: {len(chunk_transcript)} characters")
                    
                    # Show overall progress with time estimates
                    elapsed_total = time.time() - overall_start
                    if i < len(chunks):
                        avg_time_per_chunk = elapsed_total / i
                        remaining_chunks = len(chunks) - i
                        est_remaining = avg_time_per_chunk * remaining_chunks
                        progress_pct = (i / len(chunks)) * 100
                        
                        print(f"   📈 Overall Progress: {progress_pct:.1f}% ({i}/{len(chunks)} chunks)")
                        print(f"   ⏰ Time: {elapsed_total/60:.1f}min elapsed, ~{est_remaining/60:.1f}min remaining")
                else:
                    print(f"   ⚠️ Chunk {i} produced no transcription")
                
                print(f"   {'-'*50}")
            
            # Step 4: Combine all transcripts with summary
            final_transcript = "\n\n".join(all_transcripts)
            
            if not final_transcript:
                raise RuntimeError("No transcription content generated from any chunk")
            
            # Step 5: Cleanup chunks
            self._cleanup_audio_chunks(chunks, audio_file)
            
            # Final summary matching Parakeet style
            total_time = time.time() - overall_start
            overall_rtf = total_time / duration if duration > 0 else 0
            
            print(f"\n🏁 Faster-Whisper Transcription Complete!")
            print(f"{'='*60}")
            print(f"📊 Final Statistics:")
            print(f"   • Total time: {total_time/60:.1f} minutes ({total_time:.1f}s)")
            print(f"   • Overall RTF: {overall_rtf:.3f}x")
            print(f"   • Processing speed: {duration/total_time:.1f}x realtime")
            print(f"   • Output: {len(final_transcript):,} characters from {len(chunks)} chunks")
            print(f"   • Average per chunk: {len(final_transcript)//len(chunks):,} chars")
            
            # Add basic speaker detection
            final_transcript = self._add_basic_speaker_detection(final_transcript, audio_file)
            
            return final_transcript
            
        except Exception as e:
            print(f"❌ Faster-Whisper transcription failed: {e}")
            raise RuntimeError(f"Transcription failed: {e}")
    
    def _get_audio_duration(self, audio_file):
        """Get audio duration using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'csv=p=0',
                '-show_entries', 'format=duration', str(audio_file)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception as e:
            print(f"⚠️ Could not get duration: {e}")
        return 0
    
    def _split_audio_for_faster_whisper(self, input_file, chunk_duration=600):
        """Split audio into chunks for faster-whisper processing"""
        try:
            base_path = Path(input_file)
            chunk_dir = base_path.parent / f"{base_path.stem}_chunks"
            chunk_dir.mkdir(exist_ok=True)
            
            duration = self._get_audio_duration(input_file)
            if duration <= chunk_duration:
                print(f"📄 File duration ({duration/60:.1f}min) within chunk limit - no splitting needed")
                return [str(input_file)]
            
            print(f"✂️ Splitting {duration/60:.1f}min audio into {chunk_duration//60}min chunks...")
            
            chunk_files = []
            start_time = 0
            chunk_num = 1
            
            while start_time < duration:
                chunk_file = chunk_dir / f"chunk_{chunk_num:03d}.wav"
                
                # Use ffmpeg to extract chunk
                ffmpeg_cmd = [
                    'ffmpeg', '-y', '-i', str(input_file),
                    '-ss', str(start_time), '-t', str(chunk_duration),
                    '-c', 'copy', str(chunk_file)
                ]
                
                print(f"📄 Creating chunk {chunk_num}: {start_time//60:.0f}m-{(start_time+chunk_duration)//60:.0f}m")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0 and chunk_file.exists() and chunk_file.stat().st_size > 1000:
                    chunk_files.append(str(chunk_file))
                    print(f"✅ Chunk {chunk_num} created: {chunk_file.stat().st_size//1024//1024}MB")
                else:
                    print(f"❌ Failed to create chunk {chunk_num}")
                    break
                
                start_time += chunk_duration
                chunk_num += 1
            
            return chunk_files if chunk_files else [str(input_file)]
            
        except Exception as e:
            print(f"❌ Error splitting audio: {e}")
            return [str(input_file)]
    
    def _transcribe_faster_whisper_chunk(self, chunk_file, chunk_num, total_chunks):
        """Transcribe a single chunk with enhanced Faster-Whisper logging"""
        try:
            # Get chunk start time for timestamp adjustment
            chunk_name = Path(chunk_file).stem
            chunk_start_offset = 0
            if 'chunk_' in chunk_name:
                chunk_number = int(chunk_name.split('_')[1]) - 1
                chunk_start_offset = chunk_number * 600  # 10 minutes per chunk
            
            print(f"   🎙️ Starting Faster-Whisper ASR...")
            print(f"   ⚙️ VAD filter: Enabled (skip silence >500ms)")
            print(f"   🔧 Beam size: 5 (quality/speed balance)")
            
            # Start transcription timer
            import time
            transcribe_start = time.time()
            
            # Transcribe chunk with detailed settings
            segments, info = self.asr_model.transcribe(
                str(chunk_file),
                language=None,  # Auto-detect language
                task="transcribe",
                vad_filter=True,  # Skip silence for faster processing
                vad_parameters=dict(min_silence_duration_ms=500),  # Skip 500ms+ silence
                beam_size=5,  # Good quality/speed balance
                temperature=0,  # Deterministic
                word_timestamps=False
            )
            
            transcribe_time = time.time() - transcribe_start
            
            # Show ASR engine results
            if hasattr(info, 'language') and hasattr(info, 'language_probability'):
                print(f"   🌐 Language: {info.language} ({info.language_probability:.1%} confidence)")
            if hasattr(info, 'duration'):
                print(f"   ⏱️  Audio processed: {info.duration:.1f}s")
            if hasattr(info, 'duration_after_vad'):
                vad_removed = info.duration - info.duration_after_vad
                vad_removed_pct = (vad_removed / info.duration) * 100 if info.duration > 0 else 0
                print(f"   🔇 VAD removed: {vad_removed:.1f}s ({vad_removed_pct:.1f}% silence)")
            
            # Extract text with adjusted timestamps
            print(f"   📝 Processing segments...")
            transcript_lines = []
            segment_count = 0
            
            for segment in segments:
                adjusted_time = segment.start + chunk_start_offset
                text = segment.text.strip()
                
                if text:
                    minutes = int(adjusted_time // 60)
                    seconds = int(adjusted_time % 60)
                    transcript_lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")
                    segment_count += 1
            
            final_transcript = "\n".join(transcript_lines)
            
            # Report segment processing results
            print(f"   📊 Segments: {segment_count} text segments extracted")
            print(f"   ⏱️  ASR time: {transcribe_time:.1f}s")
            
            return final_transcript
            
        except Exception as e:
            print(f"   ❌ Error transcribing chunk {chunk_num}: {e}")
            return None
    
    def _cleanup_audio_chunks(self, chunk_files, original_file):
        """Clean up temporary audio chunks"""
        try:
            if len(chunk_files) <= 1:
                return  # No chunks created
            
            # Remove chunk files and directory
            for chunk_file in chunk_files:
                chunk_path = Path(chunk_file)
                if chunk_path.exists() and str(chunk_path) != str(original_file):
                    chunk_path.unlink()
            
            # Remove chunk directory if empty
            base_path = Path(original_file)
            chunk_dir = base_path.parent / f"{base_path.stem}_chunks"
            if chunk_dir.exists():
                try:
                    chunk_dir.rmdir()
                    print(f"🧹 Cleaned up chunk directory")
                except OSError:
                    pass  # Directory not empty
                    
        except Exception as e:
            print(f"⚠️ Error cleaning up chunks: {e}")
    
    def _log_episode_failure(self, episode_id, failure_reason):
        """Log episode failure or skip to database with reason and timestamp"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Determine if this is a skip or failure
            is_skip = failure_reason.startswith('Skipped:')
            status = 'skipped' if is_skip else 'failed'
            new_status = 'failed'
            
            # Update episode with failure/skip information
            cursor.execute("""
                UPDATE episodes 
                SET status = ?,
                    status = ?,
                    failure_reason = ?,
                    failure_timestamp = datetime('now'),
                    retry_count = CASE WHEN ? THEN retry_count ELSE retry_count + 1 END
                WHERE episode_id = ? OR audio_url = ?
            """, (new_status, status, failure_reason, is_skip, episode_id, episode_id))
            
            conn.commit()
            conn.close()
            
            action = "skip" if is_skip else "failure"
            print(f"📝 Logged {action}: {failure_reason}")
            
        except Exception as log_error:
            print(f"⚠️ Could not log {action} to database: {log_error}")
    
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
        
        # Use episode_id directly as filename (should already be 8-char hash)
        transcript_path = transcript_dir / f"{episode_id}.txt"
        
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
        """Process all episodes awaiting transcription (pending/pre-download status)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM episodes WHERE status IN (\'pending\', \'pre-download\')')
        episodes_to_process = cursor.fetchall()
        conn.close()
        
        results = []
        for (episode_id,) in episodes_to_process:
            result = self.process_episode(episode_id)
            if result:
                results.append(result)
        
        return results
    
    def get_transcribed_episodes(self, min_priority=0.3):
        """Get transcribed episodes above minimum priority threshold"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT e.id, e.title, e.published_date, e.transcript_path, 
                   e.priority_score, e.content_type, f.title as feed_title, f.topic_category
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            WHERE e.status IN ('transcribed', 'digested') AND e.priority_score >= ?
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
                COUNT(CASE WHEN status IN ('transcribed', 'digested') THEN 1 END) as transcribed,
                COUNT(CASE WHEN status = 'pre-download' THEN 1 END) as pre_download,
                COUNT(CASE WHEN status = 'downloaded' THEN 1 END) as downloaded,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
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
        print("❌ Parakeet MLX not available - cannot process audio")
        print("   Install Parakeet MLX with: pip install parakeet-mlx")
        return
    
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