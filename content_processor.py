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
    print("✅ Parakeet MLX available - using Apple Silicon optimized ASR")
except ImportError:
    PARAKEET_MLX_AVAILABLE = False
    print("❌ Parakeet MLX not available - cannot process audio")
    print("Install with: pip install parakeet-mlx")
    raise ImportError("Parakeet MLX is required for audio processing")

class ContentProcessor:
    def __init__(self, db_path="podcast_monitor.db", audio_dir="audio_cache", min_youtube_minutes=3.0):
        self.db_path = db_path
        self.audio_dir = Path(audio_dir)
        self.audio_dir.mkdir(exist_ok=True)
        self.min_youtube_minutes = min_youtube_minutes
        
        # Initialize Parakeet ASR models
        self.asr_model = None
        self.speaker_model = None
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
            print(f"❌ Error loading Parakeet MLX models: {e}")
            print("Cannot proceed without Parakeet MLX ASR")
            raise RuntimeError(f"Failed to initialize Parakeet MLX: {e}")
    
    def process_episode(self, episode_id):
        """Process a single episode: download audio, extract transcript, analyze content"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get episode info
        cursor.execute('''
            SELECT e.id, e.episode_id, e.title, e.audio_url, f.type, f.topic_category
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            WHERE e.id = ? AND e.status IN ('pending', 'pre-download')
        ''', (episode_id,))
        
        episode = cursor.fetchone()
        if not episode:
            print(f"Episode {episode_id} not found or already transcribed")
            conn.close()
            return None
        
        ep_id, episode_guid, title, audio_url, feed_type, topic_category = episode
        print(f"Processing: {title}")
        
        try:
            if feed_type == 'youtube':
                transcript = self._process_youtube_episode(audio_url, episode_guid)
            else:
                transcript = self._process_rss_episode(audio_url, episode_guid)
            
            # If audio was successfully obtained, mark as pending first
            if audio_path:
                cursor.execute('UPDATE episodes SET status = \'pending\' WHERE id = ?', (ep_id,))
                conn.commit()
            
            if transcript:
                # Save transcript
                transcript_path = self._save_transcript(episode_guid, transcript)
                
                # Analyze content
                analysis = self._analyze_content(transcript, topic_category)
                
                # Update database
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
        """Extract transcript from YouTube video"""
        video_id = self._extract_youtube_video_id(video_url)
        if not video_id:
            print(f"Could not extract video ID from {video_url}")
            return None
        
        try:
            # Fetch transcript using instance method  
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
        """Convert audio to transcript using Parakeet MLX ASR"""
        if self.asr_model is None:
            raise RuntimeError("Parakeet ASR model not initialized")
        return self._parakeet_mlx_transcribe(audio_file)
    
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
        """Process all pending episodes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM episodes WHERE status IN (\'pending\', \'pre-download\')')
        pending_episodes = cursor.fetchall()
        conn.close()
        
        results = []
        for (episode_id,) in pending_episodes:
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
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
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