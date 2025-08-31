#!/usr/bin/env python3
"""
Daily Tech Digest Podcast Pipeline - Complete Automation
Single unified script that runs the complete daily workflow
"""

import os
import sqlite3
import subprocess
import shutil
import time
from pathlib import Path
from datetime import datetime, timedelta
import logging
import tempfile

# Import existing modules
from feed_monitor import FeedMonitor
from content_processor import ContentProcessor
from claude_api_integration import ClaudeAPIIntegration

# Configuration
CONFIG = {
    'RETENTION_DAYS': 7,
    'MAX_RSS_EPISODES': 7,
    'CLEANUP_AUDIO_CACHE': True,
    'CLEANUP_INTERMEDIATE_FILES': True,
    'GITHUB_TOKEN': os.getenv('GITHUB_TOKEN'),
    'ELEVENLABS_API_KEY': os.getenv('ELEVENLABS_API_KEY'),
    'DB_PATH': 'podcast_monitor.db',
    'AUDIO_CACHE_DIR': 'audio_cache',
    'TRANSCRIPTS_DIR': 'transcripts',
    'DAILY_DIGESTS_DIR': 'daily_digests'
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DailyPodcastPipeline:
    def __init__(self):
        self.db_path = CONFIG['DB_PATH']
        self.feed_monitor = FeedMonitor(self.db_path)
        self.content_processor = ContentProcessor(
            db_path=self.db_path, 
            audio_dir=CONFIG['AUDIO_CACHE_DIR']
        )
        self.claude_integration = ClaudeAPIIntegration(
            db_path=self.db_path,
            transcripts_dir=CONFIG['TRANSCRIPTS_DIR']
        )
        
    def run_daily_workflow(self):
        """Execute complete daily workflow"""
        logger.info("🚀 Starting Daily Tech Digest Pipeline")
        logger.info("=" * 50)
        
        try:
            # Step 1: Monitor RSS feeds for new episodes
            self._monitor_rss_feeds()
            
            # Step 2: Process audio_cache files (transcribe to 'transcribed')
            self._process_audio_cache_files()
            
            # Step 3: Process pending episodes
            self._process_pending_episodes()
            
            # Step 4: Generate daily digest from ONLY 'transcribed' episodes
            digest_success = self._generate_daily_digest()
            
            if digest_success:
                # Step 5: Create TTS audio
                self._create_tts_audio()
                
                # Step 6: Deploy to GitHub releases
                self._deploy_to_github()
                
                # Step 7: Update RSS feed
                self._update_rss_feed()
                
                # Step 8: Mark processed episodes as 'digested'
                self._mark_episodes_digested()
            
            # Step 9: Cleanup old files and transcripts
            self._cleanup_old_files()
            
            logger.info("✅ Daily workflow completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Daily workflow failed: {e}")
            return False
    
    def _monitor_rss_feeds(self):
        """Check RSS feeds for new episodes"""
        logger.info("📡 Checking RSS feeds for new episodes...")
        
        new_episodes = self.feed_monitor.check_new_episodes(hours_back=24)
        
        if new_episodes:
            logger.info(f"Found {len(new_episodes)} new episodes")
            # Episodes from feed monitor already have correct status (pre-download)
            self._update_new_episodes_status(new_episodes)
        else:
            logger.info("No new episodes found")
    
    def _update_new_episodes_status(self, new_episodes):
        """Episodes are already created with 'pre-download' status by feed_monitor"""
        # No longer needed - feed_monitor.py now creates episodes with 'pre-download' status
        logger.info("Episodes already created with 'pre-download' status by feed monitor")
    
    def _process_audio_cache_files(self):
        """Process existing audio files in audio_cache with progress monitoring and time estimation"""
        logger.info("🎵 Processing audio cache files...")
        
        audio_cache = Path(CONFIG['AUDIO_CACHE_DIR'])
        if not audio_cache.exists():
            logger.info("No audio_cache directory found")
            return
        
        # Find all MP3 files in audio_cache
        audio_files = list(audio_cache.glob("*.mp3"))
        
        if not audio_files:
            logger.info("No MP3 files found in audio_cache")
            return
        
        logger.info(f"Found {len(audio_files)} MP3 files to process")
        
        # Import robust transcriber for time estimation
        try:
            from robust_transcriber import RobustTranscriber
            transcriber = RobustTranscriber()
        except ImportError:
            logger.warning("RobustTranscriber not available, using basic transcription")
            transcriber = None
        
        # Estimate total processing time
        total_estimated_time = 0
        file_estimates = []
        
        for audio_file in audio_files:
            if transcriber:
                duration, est_time, num_chunks = transcriber.estimate_transcription_time(str(audio_file))
                file_estimates.append((audio_file, duration, est_time, num_chunks))
                total_estimated_time += est_time
            else:
                file_estimates.append((audio_file, 0, 60, 1))  # Default fallback
                total_estimated_time += 60
        
        logger.info(f"📊 Estimated total processing time: {total_estimated_time/60:.1f} minutes")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        processed_files = 0
        start_time = time.time()
        
        for i, (audio_file, duration, est_time, num_chunks) in enumerate(file_estimates):
            try:
                episode_id = audio_file.stem  # Use filename as episode_id (already 8-char hash)
                
                # First, try to find existing episode by filename match
                cursor.execute("SELECT id, status FROM episodes WHERE episode_id = ?", (episode_id,))
                result = cursor.fetchone()
                
                if result:
                    db_id, current_status = result
                    if current_status == 'transcribed':
                        logger.info(f"⏭️ Episode {episode_id} already transcribed, skipping")
                        processed_files += 1
                        continue
                else:
                    # Try to find matching failed/pending episode by doing quick transcription sample
                    logger.info(f"🔍 No direct match for {episode_id}, checking for failed episodes...")
                    
                    # Get a small sample transcript to match against failed episodes
                    try:
                        if transcriber:
                            # Extract first 30 seconds for quick identification
                            import tempfile
                            import subprocess
                            with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as temp_file:
                                subprocess.run([
                                    'ffmpeg', '-i', str(audio_file), '-t', '30', '-y', temp_file.name
                                ], check=True, capture_output=True)
                                sample_transcript = transcriber.transcribe_file(temp_file.name)
                            
                            # Look for failed episodes and try to match by title keywords
                            cursor.execute("SELECT id, episode_id, title FROM episodes WHERE status IN ('failed', 'downloaded', 'pre-download') ORDER BY id DESC LIMIT 20")
                            failed_episodes = cursor.fetchall()
                            
                            # Try to match by looking for key phrases
                            matched_episode = None
                            for failed_id, failed_episode_id, failed_title in failed_episodes:
                                # Extract key words from titles for matching
                                if sample_transcript:
                                    # Check for title keywords in transcript sample
                                    title_words = failed_title.lower().split()
                                    sample_lower = sample_transcript.lower()
                                    matches = sum(1 for word in title_words if len(word) > 4 and word in sample_lower)
                                    if matches >= 2:  # At least 2 significant word matches
                                        matched_episode = (failed_id, failed_episode_id)
                                        logger.info(f"🎯 Matched {audio_file.name} to existing episode: {failed_title}")
                                        break
                            
                            if matched_episode:
                                db_id, episode_id = matched_episode
                            else:
                                # Create new episode entry as fallback
                                cursor.execute("""
                                    INSERT INTO episodes (episode_id, title, audio_url, status, published_date)
                                    VALUES (?, ?, ?, 'downloaded', datetime('now'))
                                """, (episode_id, f"Cached Audio: {audio_file.name}", str(audio_file)))
                                db_id = cursor.lastrowid
                        else:
                            # Fallback without transcriber
                            cursor.execute("""
                                INSERT INTO episodes (episode_id, title, audio_url, status, published_date)
                                VALUES (?, ?, ?, 'downloaded', datetime('now'))
                            """, (episode_id, f"Cached Audio: {audio_file.name}", str(audio_file)))
                            db_id = cursor.lastrowid
                    except Exception as match_error:
                        logger.warning(f"Could not match episode, creating new entry: {match_error}")
                        cursor.execute("""
                            INSERT INTO episodes (episode_id, title, audio_url, status, published_date)
                            VALUES (?, ?, ?, 'downloaded', datetime('now'))
                        """, (episode_id, f"Cached Audio: {audio_file.name}", str(audio_file)))
                        db_id = cursor.lastrowid
                
                # Log processing start with time estimate
                logger.info(f"🔄 Processing {i+1}/{len(audio_files)}: {audio_file.name}")
                logger.info(f"⏱️ Audio duration: {duration/60:.1f} min, estimated processing: {est_time/60:.1f} min")
                if num_chunks > 1:
                    logger.info(f"📦 Will process in {num_chunks} chunks")
                
                # Track processing start time for this file
                file_start_time = time.time()
                
                # Transcribe the audio file with progress monitoring
                if transcriber:
                    transcript = transcriber.transcribe_file(str(audio_file))
                else:
                    transcript = self.content_processor._audio_to_transcript(str(audio_file))
                
                file_processing_time = time.time() - file_start_time
                
                if transcript:
                    # Save transcript
                    transcript_path = self.content_processor._save_transcript(episode_id, transcript)
                    
                    # Update database to 'transcribed' status
                    cursor.execute("""
                        UPDATE episodes 
                        SET transcript_path = ?, status = 'transcribed', 
                            priority_score = 0.8, content_type = 'discussion'
                        WHERE id = ?
                    """, (transcript_path, db_id))
                    
                    processed_files += 1
                    logger.info(f"✅ Transcribed: {audio_file.name} (took {file_processing_time/60:.1f} min)")
                else:
                    logger.error(f"❌ Failed to transcribe: {audio_file.name}")
                    cursor.execute("UPDATE episodes SET status = 'failed' WHERE id = ?", (db_id,))
                
                # Progress update
                elapsed_time = time.time() - start_time
                remaining_files = len(audio_files) - (i + 1)
                if processed_files > 0:
                    avg_time_per_file = elapsed_time / processed_files
                    estimated_remaining = avg_time_per_file * remaining_files
                    logger.info(f"📈 Progress: {processed_files}/{len(audio_files)} files, ~{estimated_remaining/60:.1f} min remaining")
                
            except Exception as e:
                logger.error(f"Error processing {audio_file.name}: {e}")
                if 'db_id' in locals():
                    cursor.execute("UPDATE episodes SET status = 'failed' WHERE id = ?", (db_id,))
        
        conn.commit()
        conn.close()
        
        total_time = time.time() - start_time
        logger.info(f"🏁 Audio cache processing complete: {processed_files} files in {total_time/60:.1f} minutes")
    
    def _process_pending_episodes(self):
        """Process episodes awaiting transcription"""
        logger.info("⚙️ Processing episodes awaiting transcription (pending/pre-download)...")
        
        results = self.content_processor.process_all_pending()
        
        if results:
            logger.info(f"✅ Processed {len(results)} pending episodes")
        else:
            logger.info("No pending episodes to process")
    
    def _generate_daily_digest(self):
        """Generate daily digest from BOTH RSS and YouTube 'transcribed' episodes"""
        logger.info("📝 Generating daily digest from RSS + YouTube transcripts...")
        
        # Check RSS transcribed episodes
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM episodes WHERE status = 'transcribed'")
        rss_transcribed_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT status, COUNT(*) FROM episodes GROUP BY status")
        rss_status_counts = cursor.fetchall()
        logger.info("📊 RSS Episode status breakdown:")
        for status, count in rss_status_counts:
            logger.info(f"   {status}: {count} episodes")
        
        conn.close()
        
        # Check YouTube transcribed episodes
        youtube_transcribed_count = 0
        youtube_db_path = "youtube_transcripts.db"
        if Path(youtube_db_path).exists():
            try:
                conn = sqlite3.connect(youtube_db_path)
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM episodes WHERE status = 'transcribed'")
                youtube_transcribed_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT status, COUNT(*) FROM episodes GROUP BY status")
                youtube_status_counts = cursor.fetchall()
                logger.info("📊 YouTube Episode status breakdown:")
                for status, count in youtube_status_counts:
                    logger.info(f"   {status}: {count} episodes")
                
                conn.close()
            except Exception as e:
                logger.warning(f"Could not check YouTube database: {e}")
        else:
            logger.info("📊 No YouTube database found")
        
        total_transcribed = rss_transcribed_count + youtube_transcribed_count
        logger.info(f"📋 Total transcripts for digest: {rss_transcribed_count} RSS + {youtube_transcribed_count} YouTube = {total_transcribed}")
        
        if total_transcribed == 0:
            logger.warning("No 'transcribed' episodes available from either database")
            return False
        
        # Generate Claude-powered digest (reads from both databases automatically)
        success, digest_path, cross_refs_path = self.claude_integration.generate_api_digest()
        
        if success:
            logger.info(f"✅ Daily digest generated: {digest_path}")
            return True
        else:
            logger.error("❌ Failed to generate daily digest")
            return False
    
    def _create_tts_audio(self):
        """Create TTS audio for the daily digest"""
        logger.info("🎙️ Creating TTS audio...")
        
        try:
            # Run TTS generation
            result = subprocess.run([
                'python3', 'claude_tts_generator.py'
            ], capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                logger.info("✅ TTS audio generated successfully")
                return True
            else:
                logger.error(f"❌ TTS generation failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating TTS audio: {e}")
            return False
    
    def _deploy_to_github(self):
        """Deploy latest episode to GitHub releases"""
        logger.info("🚀 Deploying to GitHub...")
        
        try:
            result = subprocess.run([
                'python3', 'deploy_episode.py'
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info("✅ Deployed to GitHub successfully")
                return True
            else:
                logger.error(f"❌ GitHub deployment failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error deploying to GitHub: {e}")
            return False
    
    def _update_rss_feed(self):
        """Update RSS feed with latest episode"""
        logger.info("📡 Updating RSS feed...")
        
        try:
            result = subprocess.run([
                'python3', 'rss_generator.py'
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                logger.info("✅ RSS feed updated successfully")
                return True
            else:
                logger.error(f"❌ RSS feed update failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating RSS feed: {e}")
            return False
    
    def _mark_episodes_digested(self):
        """Mark all 'transcribed' episodes as 'digested' in BOTH databases"""
        logger.info("📋 Marking episodes as digested in both RSS and YouTube databases...")
        
        # Mark RSS episodes as digested
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE episodes SET status = 'digested' WHERE status = 'transcribed'")
        rss_updated_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        # Mark YouTube episodes as digested
        youtube_updated_count = 0
        youtube_db_path = "youtube_transcripts.db"
        if Path(youtube_db_path).exists():
            try:
                conn = sqlite3.connect(youtube_db_path)
                cursor = conn.cursor()
                
                cursor.execute("UPDATE episodes SET status = 'digested' WHERE status = 'transcribed'")
                youtube_updated_count = cursor.rowcount
                
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"Could not update YouTube database: {e}")
        
        total_updated = rss_updated_count + youtube_updated_count
        logger.info(f"✅ Marked episodes as digested: {rss_updated_count} RSS + {youtube_updated_count} YouTube = {total_updated} total")
    
    def _cleanup_old_files(self):
        """Clean up old files and transcripts"""
        logger.info("🧹 Cleaning up old files...")
        
        cutoff_date = datetime.now() - timedelta(days=CONFIG['RETENTION_DAYS'])
        
        # Clean old transcripts in digested folder
        self._cleanup_old_transcripts(cutoff_date)
        
        # Clean old audio files from daily_digests
        self._cleanup_old_audio_digests()
        
        # Clean audio_cache if configured
        if CONFIG['CLEANUP_AUDIO_CACHE']:
            self._cleanup_audio_cache()
        
        # Clean intermediate files
        if CONFIG['CLEANUP_INTERMEDIATE_FILES']:
            self._cleanup_intermediate_files()
        
        # Clean old failed episodes from database
        self._cleanup_old_failed_episodes(cutoff_date)
    
    def _cleanup_old_transcripts(self, cutoff_date):
        """Delete old transcripts from digested folder"""
        digested_dir = Path(CONFIG['TRANSCRIPTS_DIR']) / 'digested'
        
        if not digested_dir.exists():
            return
        
        cleaned_count = 0
        for transcript_file in digested_dir.glob("*.txt"):
            if transcript_file.stat().st_mtime < cutoff_date.timestamp():
                transcript_file.unlink()
                cleaned_count += 1
        
        logger.info(f"Cleaned {cleaned_count} old transcript files")
    
    def _cleanup_old_audio_digests(self):
        """Keep only latest 3 audio digests"""
        daily_digests_dir = Path(CONFIG['DAILY_DIGESTS_DIR'])
        
        if not daily_digests_dir.exists():
            return
        
        # Find all complete digest files
        audio_files = list(daily_digests_dir.glob("complete_topic_digest_*.mp3"))
        audio_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Keep only latest 3
        for old_file in audio_files[3:]:
            old_file.unlink()
            logger.info(f"Deleted old audio digest: {old_file.name}")
    
    def _cleanup_audio_cache(self):
        """Clean up audio_cache after processing"""
        audio_cache = Path(CONFIG['AUDIO_CACHE_DIR'])
        
        if not audio_cache.exists():
            return
        
        # Remove chunk directories
        for chunk_dir in audio_cache.glob("*_chunks/"):
            shutil.rmtree(chunk_dir)
            logger.info(f"Cleaned chunk directory: {chunk_dir.name}")
        
        # Remove processed MP3 files (only after they're marked as transcribed)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for mp3_file in audio_cache.glob("*.mp3"):
            episode_id = mp3_file.stem  # Use filename as episode_id (8-char hash)
            cursor.execute("SELECT status FROM episodes WHERE episode_id = ?", (episode_id,))
            result = cursor.fetchone()
            
            if result and result[0] in ('transcribed', 'digested'):
                mp3_file.unlink()
                logger.info(f"Cleaned processed audio: {mp3_file.name}")
        
        conn.close()
    
    def _cleanup_intermediate_files(self):
        """Clean up intermediate files"""
        # Clean temp TTS files
        for temp_file in Path('.').glob("intro_*.mp3"):
            temp_file.unlink()
        for temp_file in Path('.').glob("outro_*.mp3"):
            temp_file.unlink()
        for temp_file in Path('.').glob("topic_*.mp3"):
            temp_file.unlink()
        
        logger.info("Cleaned intermediate TTS files")
    
    def _cleanup_old_failed_episodes(self, cutoff_date):
        """Remove old failed episodes from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM episodes 
            WHERE status = 'failed' AND failure_timestamp < ?
        """, (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Cleaned {deleted_count} old failed episodes from database")
    
    def get_status_summary(self):
        """Get current system status summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get episode counts by status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM episodes
            GROUP BY status
            ORDER BY count DESC
        """)
        
        status_counts = dict(cursor.fetchall())
        
        # Check audio_cache files
        audio_cache = Path(CONFIG['AUDIO_CACHE_DIR'])
        audio_cache_count = len(list(audio_cache.glob("*.mp3"))) if audio_cache.exists() else 0
        
        conn.close()
        
        return {
            'database_status': status_counts,
            'audio_cache_files': audio_cache_count,
            'total_episodes': sum(status_counts.values())
        }

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Daily Tech Digest Pipeline")
    parser.add_argument('--status', action='store_true', help='Show current status')
    parser.add_argument('--run', action='store_true', help='Run daily workflow')
    parser.add_argument('--rss-only', action='store_true', help='Process RSS feeds only (GitHub Actions mode)')
    parser.add_argument('--cleanup', action='store_true', help='Run cleanup only')
    parser.add_argument('--test', action='store_true', help='Test individual components')
    args = parser.parse_args()
    
    pipeline = DailyPodcastPipeline()
    
    if args.status:
        status = pipeline.get_status_summary()
        print("\n📊 System Status:")
        print("================")
        print(f"Database episodes: {status['database_status']}")
        print(f"Audio cache files: {status['audio_cache_files']}")
        print(f"Total episodes: {status['total_episodes']}")
        return
    
    if args.cleanup:
        logger.info("🧹 Running cleanup only...")
        pipeline._cleanup_old_files()
        return
    
    if args.test:
        logger.info("🧪 Testing components...")
        # Test each component
        print("Feed monitor:", "✅" if pipeline.feed_monitor else "❌")
        print("Content processor:", "✅" if pipeline.content_processor.asr_model else "❌")
        print("Claude integration:", "✅" if pipeline.claude_integration.api_available else "❌")
        return
    
    if args.run:
        # Run the complete daily workflow
        success = pipeline.run_daily_workflow()
        exit(0 if success else 1)
    
    if args.rss_only:
        # GitHub Actions mode: Process RSS + pull YouTube transcripts + generate unified digest
        logger.info("🚀 Starting GITHUB ACTIONS Pipeline")
        logger.info("📝 GITHUB SCOPE: RSS processing + YouTube transcripts + Digest generation")
        logger.info("=" * 75)
        
        try:
            # Pull latest changes (gets YouTube transcripts already pushed to repo)
            import subprocess
            subprocess.run(['git', 'pull', 'origin', 'main'], check=True) 
            logger.info("✅ Pulled latest changes - YouTube transcripts already in repo")
            
            # Step 1: Monitor RSS feeds and add new episodes
            pipeline._monitor_rss_feeds()
            
            # Step 2: Process RSS audio cache files → transcribe → mark 'transcribed'
            pipeline._process_audio_cache_files()
            
            # Step 3: Process pending RSS episodes → transcribe → mark 'transcribed'  
            pipeline._process_pending_episodes()
            
            # Step 4: Generate digest from ALL 'transcribed' episodes (RSS + YouTube databases)
            logger.info("📊 Generating digest from ALL 'transcribed' episodes (RSS + YouTube)")
            digest_success = pipeline._generate_daily_digest()
            
            if digest_success:
                # Step 5: Create TTS audio
                pipeline._create_tts_audio()
                
                # Step 6: Deploy to GitHub releases
                pipeline._deploy_to_github()
                
                # Step 7: Update RSS feed
                pipeline._update_rss_feed()
                
                # Step 8: Mark ALL processed episodes as 'digested' (both databases)
                pipeline._mark_episodes_digested()
            
            # Step 9: Cleanup old files and episodes
            pipeline._cleanup_old_files()
            
            logger.info("✅ GITHUB ACTIONS workflow completed successfully")
            logger.info("🔄 Local machine will pull digest status updates on next run")
            exit(0)
            
        except Exception as e:
            logger.error(f"❌ GITHUB ACTIONS workflow failed: {e}")
            exit(1)
    
    # Default: show help and status
    parser.print_help()
    print("\nCurrent status:")
    status = pipeline.get_status_summary()
    print(f"Episodes ready for digest: {status['database_status'].get('transcribed', 0)}")
    print(f"Audio files to process: {status['audio_cache_files']}")

if __name__ == "__main__":
    main()