#!/usr/bin/env python3
"""
Daily Tech Digest Podcast Pipeline - Complete Automation
Single unified script that runs the complete daily workflow
"""

import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from utils.db import get_connection

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from content_processor import ContentProcessor

# Import existing modules
from feed_monitor import FeedMonitor
from openai_digest_integration import OpenAIDigestIntegration
from retention_cleanup import RetentionCleanup
from telemetry_manager import telemetry
from utils.datetime_utils import now_utc
from utils.episode_failures import FailureManager, ensure_failures_table_exists

# Configuration
CONFIG = {
    "RETENTION_DAYS": 14,  # Aligned with retention_cleanup.py default
    "MAX_RSS_EPISODES": 7,
    "CLEANUP_AUDIO_CACHE": True,
    "CLEANUP_INTERMEDIATE_FILES": True,
    "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
    "DIGEST_DISPLAY_TZ": os.getenv(
        "DIGEST_DISPLAY_TZ", "UTC"
    ),  # Display timezone for human-facing labels
    "ELEVENLABS_API_KEY": os.getenv("ELEVENLABS_API_KEY"),
    "DB_PATH": "podcast_monitor.db",
    "AUDIO_CACHE_DIR": "audio_cache",
    "TRANSCRIPTS_DIR": "transcripts",
    "DAILY_DIGESTS_DIR": "daily_digests",
}

# Logging will be configured in main() based on --verbose flag
logger = None


class DailyPodcastPipeline:
    def __init__(self, hours_back=None):
        self.db_path = CONFIG["DB_PATH"]
        self.feed_monitor = FeedMonitor(self.db_path)
        self.content_processor = ContentProcessor(
            db_path=self.db_path, audio_dir=CONFIG["AUDIO_CACHE_DIR"]
        )
        self.openai_integration = OpenAIDigestIntegration(
            db_path=self.db_path, transcripts_dir=CONFIG["TRANSCRIPTS_DIR"]
        )
        self.hours_back = hours_back

    def _get_display_weekday(self):
        """Get weekday in display timezone for human-facing labels"""
        display_tz = CONFIG["DIGEST_DISPLAY_TZ"]

        if display_tz == "UTC":
            return now_utc().strftime("%A")

        # For non-UTC display timezones, we still use UTC for all comparisons
        # but can show local time for user display
        try:
            from zoneinfo import ZoneInfo

            utc_now = now_utc()
            local_time = utc_now.astimezone(ZoneInfo(display_tz))
            return local_time.strftime("%A")
        except ImportError:
            # Fallback to UTC if zoneinfo not available
            logger.debug(f"zoneinfo not available, using UTC instead of {display_tz}")
            return now_utc().strftime("%A")
        except Exception as e:
            # Fallback to UTC if timezone is invalid
            logger.warning(f"Invalid DIGEST_DISPLAY_TZ '{display_tz}', using UTC: {e}")
            return now_utc().strftime("%A")

    def run_daily_workflow(self):
        """Execute complete daily workflow with weekday logic"""
        # Use UTC for all logic/comparisons, display timezone for user-facing labels
        utc_weekday = now_utc().strftime("%A")
        display_weekday = self._get_display_weekday()
        logger.info(f"🚀 Starting Daily Tech Digest Pipeline - {display_weekday}")
        logger.info("=" * 50)

        # Initialize telemetry for this run
        pipeline_start_time = time.time()
        if utc_weekday == "Friday":
            telemetry.set_pipeline_type("weekly")
        elif utc_weekday == "Monday":
            telemetry.set_pipeline_type("catchup")
        else:
            telemetry.set_pipeline_type("daily")

        # Self-healing: Backfill missing topic scores from previous runs
        from openai_scorer import run_backfill_scoring

        run_backfill_scoring()  # Keep an early pass for any leftovers

        # Ensure failure tracking tables exist
        ensure_failures_table_exists(CONFIG["DB_PATH"])
        ensure_failures_table_exists("youtube_transcripts.db")

        try:
            # Step 0: Process retry queue for failed episodes
            self._process_retry_queue()

            # Step 1: Monitor RSS feeds for new episodes
            self._monitor_rss_feeds()

            # Step 2: Process audio_cache files (transcribe to 'transcribed')
            self._process_audio_cache_files()

            # Step 3: Process pending episodes
            self._process_pending_episodes()

            # Step 4: CRITICAL - Re-score after new transcripts are created
            from openai_scorer import score_pending_in_db

            scored_rss = score_pending_in_db(
                "podcast_monitor.db", source="rss", max_to_score=200
            )
            scored_yt = score_pending_in_db(
                "youtube_transcripts.db", source="youtube", max_to_score=200
            )
            logger.info(
                f"Post-transcription scoring complete: RSS={scored_rss}, YT={scored_yt}"
            )

            # Step 5: Generate digest based on weekday logic
            if utc_weekday == "Friday":
                logger.info(
                    f"📅 {display_weekday} detected - generating daily + weekly digests"
                )
                digest_success = self._generate_weekly_digest()
            elif utc_weekday == "Monday":
                logger.info(
                    f"📅 {display_weekday} detected - generating catch-up digest"
                )
                digest_success = self._generate_catchup_digest()
            else:
                logger.info(f"📅 {display_weekday} - generating standard daily digest")
                digest_success = self._generate_daily_digest()

            if digest_success:
                # Transactional Publishing: Strict order with hard gates
                logger.info("🔒 Starting transactional publishing process...")

                # Step 6: Create TTS audio for today only
                today = now_utc().date().isoformat()
                mp3_files_created = self._create_tts_audio_today_only(today)

                if not mp3_files_created:
                    logger.info(f"RSS not updated: no new MP3s for {today}")
                    return False  # Exit without marking episodes as digested

                # Step 7: Deploy to GitHub releases (MUST succeed)
                deploy_success = self._deploy_to_github()
                if not deploy_success:
                    logger.error(
                        "❌ Transactional publishing failed: deployment failed"
                    )
                    return False  # Exit without marking episodes as digested

                # Step 8: Update RSS feed (MUST succeed)
                rss_success = self._update_rss_feed()
                if not rss_success:
                    logger.error(
                        "❌ Transactional publishing failed: RSS update failed"
                    )
                    return False  # Exit without marking episodes as digested

                # Step 9: ONLY NOW mark processed episodes as 'digested'
                self._mark_episodes_digested()
                logger.info("✅ Transactional publishing completed successfully")

            # Step 10: Cleanup old files and transcripts
            self._cleanup_old_files()

            logger.info("✅ Daily workflow completed successfully")

            # Finalize telemetry
            total_time = time.time() - pipeline_start_time
            telemetry.finalize_run(total_time)

            return True

        except Exception as e:
            logger.error(f"❌ Daily workflow failed: {e}")
            telemetry.record_error(f"Pipeline failed: {e}")

            # Still finalize telemetry for failed runs
            total_time = time.time() - pipeline_start_time
            telemetry.finalize_run(total_time)

            return False

    def _process_retry_queue(self):
        """Process failed episodes eligible for retry"""
        logger.info("🔄 Processing retry queue for failed episodes...")

        retry_results = {"total_processed": 0, "total_succeeded": 0, "total_failed": 0}

        # Process retries for both RSS and YouTube databases
        for db_name, db_path in [
            ("RSS", CONFIG["DB_PATH"]),
            ("YouTube", "youtube_transcripts.db"),
        ]:
            try:
                processor = ContentProcessor(
                    db_path=db_path, audio_dir=CONFIG["AUDIO_CACHE_DIR"]
                )
                results = processor.process_retry_queue(max_retries_per_run=3)

                if results["processed"] > 0:
                    logger.info(
                        f"📊 {db_name} retries: {results['succeeded']} succeeded, {results['failed']} failed"
                    )
                    retry_results["total_processed"] += results["processed"]
                    retry_results["total_succeeded"] += results["succeeded"]
                    retry_results["total_failed"] += results["failed"]
                else:
                    logger.info(f"📊 {db_name}: No episodes eligible for retry")

                # Record telemetry
                telemetry.record_metric(
                    f"{db_name.lower()}_retries_processed", results["processed"]
                )
                telemetry.record_metric(
                    f"{db_name.lower()}_retries_succeeded", results["succeeded"]
                )

            except Exception as e:
                logger.error(f"❌ Error processing {db_name} retry queue: {e}")

        if retry_results["total_processed"] > 0:
            logger.info(
                f"🔄 Total retry results: {retry_results['total_succeeded']}/{retry_results['total_processed']} succeeded"
            )

    def _monitor_rss_feeds(self):
        """Check RSS feeds for new episodes"""
        logger.info("📡 Checking RSS feeds for new episodes...")

        new_episodes = self.feed_monitor.check_new_episodes(hours_back=self.hours_back)

        if new_episodes:
            logger.info(f"Found {len(new_episodes)} new episodes")
            # Episodes from feed monitor already have correct status (pre-download)
            self._update_new_episodes_status(new_episodes)
        else:
            logger.info("No new episodes found")

    def _update_new_episodes_status(self, new_episodes):
        """Episodes are already created with 'pre-download' status by feed_monitor"""
        # No longer needed - feed_monitor.py now creates episodes with 'pre-download' status
        logger.info(
            "Episodes already created with 'pre-download' status by feed monitor"
        )

    def _process_audio_cache_files(self):
        """Process existing audio files in audio_cache with progress monitoring and time estimation"""
        logger.info("🎵 Processing audio cache files...")

        audio_cache = Path(CONFIG["AUDIO_CACHE_DIR"])
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
                duration, est_time, num_chunks = (
                    transcriber.estimate_transcription_time(str(audio_file))
                )
                file_estimates.append((audio_file, duration, est_time, num_chunks))
                total_estimated_time += est_time
            else:
                file_estimates.append((audio_file, 0, 60, 1))  # Default fallback
                total_estimated_time += 60

        logger.info(
            f"📊 Estimated total processing time: {total_estimated_time/60:.1f} minutes"
        )

        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        processed_files = 0
        start_time = time.time()

        for i, (audio_file, duration, est_time, num_chunks) in enumerate(
            file_estimates
        ):
            try:
                episode_id = (
                    audio_file.stem
                )  # Use filename as episode_id (already 8-char hash)

                # First, try to find existing episode by filename match
                cursor.execute(
                    "SELECT id, status FROM episodes WHERE episode_id = ?",
                    (episode_id,),
                )
                result = cursor.fetchone()

                if result:
                    db_id, current_status = result
                    if current_status == "transcribed":
                        logger.info(
                            f"⏭️ Episode {episode_id} already transcribed, skipping"
                        )
                        processed_files += 1
                        continue
                else:
                    # Try to find matching failed/pending episode by doing quick transcription sample
                    logger.info(
                        f"🔍 No direct match for {episode_id}, checking for failed episodes..."
                    )

                    # Get a small sample transcript to match against failed episodes
                    try:
                        if transcriber:
                            # Extract first 30 seconds for quick identification
                            import subprocess
                            import tempfile

                            with tempfile.NamedTemporaryFile(
                                suffix=".wav", delete=True
                            ) as temp_file:
                                subprocess.run(
                                    [
                                        "ffmpeg",
                                        "-i",
                                        str(audio_file),
                                        "-t",
                                        "30",
                                        "-y",
                                        temp_file.name,
                                    ],
                                    check=True,
                                    capture_output=True,
                                )
                                sample_transcript = transcriber.transcribe_file(
                                    temp_file.name
                                )

                            # Look for failed episodes and try to match by title keywords
                            cursor.execute(
                                "SELECT id, episode_id, title FROM episodes WHERE status IN ('failed', 'downloaded', 'pre-download') ORDER BY id DESC LIMIT 20"
                            )
                            failed_episodes = cursor.fetchall()

                            # Try to match by looking for key phrases
                            matched_episode = None
                            for (
                                failed_id,
                                failed_episode_id,
                                failed_title,
                            ) in failed_episodes:
                                # Extract key words from titles for matching
                                if sample_transcript:
                                    # Check for title keywords in transcript sample
                                    title_words = failed_title.lower().split()
                                    sample_lower = sample_transcript.lower()
                                    matches = sum(
                                        1
                                        for word in title_words
                                        if len(word) > 4 and word in sample_lower
                                    )
                                    if (
                                        matches >= 2
                                    ):  # At least 2 significant word matches
                                        matched_episode = (failed_id, failed_episode_id)
                                        logger.info(
                                            f"🎯 Matched {audio_file.name} to existing episode: {failed_title}"
                                        )
                                        break

                            if matched_episode:
                                db_id, episode_id = matched_episode
                            else:
                                # Create new episode entry as fallback
                                cursor.execute(
                                    """
                                    INSERT INTO episodes (episode_id, title, audio_url, status, published_date)
                                    VALUES (?, ?, ?, 'downloaded', datetime('now'))
                                """,
                                    (
                                        episode_id,
                                        f"Cached Audio: {audio_file.name}",
                                        str(audio_file),
                                    ),
                                )
                                db_id = cursor.lastrowid
                        else:
                            # Fallback without transcriber
                            cursor.execute(
                                """
                                INSERT INTO episodes (episode_id, title, audio_url, status, published_date)
                                VALUES (?, ?, ?, 'downloaded', datetime('now'))
                            """,
                                (
                                    episode_id,
                                    f"Cached Audio: {audio_file.name}",
                                    str(audio_file),
                                ),
                            )
                            db_id = cursor.lastrowid
                    except Exception as match_error:
                        logger.warning(
                            f"Could not match episode, creating new entry: {match_error}"
                        )
                        cursor.execute(
                            """
                            INSERT INTO episodes (episode_id, title, audio_url, status, published_date)
                            VALUES (?, ?, ?, 'downloaded', datetime('now'))
                        """,
                            (
                                episode_id,
                                f"Cached Audio: {audio_file.name}",
                                str(audio_file),
                            ),
                        )
                        db_id = cursor.lastrowid

                # Log processing start with time estimate
                logger.info(
                    f"🔄 Processing {i+1}/{len(audio_files)}: {audio_file.name}"
                )
                logger.info(
                    f"⏱️ Audio duration: {duration/60:.1f} min, estimated processing: {est_time/60:.1f} min"
                )
                if num_chunks > 1:
                    logger.info(f"📦 Will process in {num_chunks} chunks")

                # Track processing start time for this file
                file_start_time = time.time()

                # Transcribe the audio file with progress monitoring
                if transcriber:
                    transcript = transcriber.transcribe_file(str(audio_file))
                else:
                    transcript = self.content_processor._audio_to_transcript(
                        str(audio_file)
                    )

                file_processing_time = time.time() - file_start_time

                if transcript:
                    # Save transcript
                    transcript_path = self.content_processor._save_transcript(
                        episode_id, transcript
                    )

                    # Update database to 'transcribed' status
                    cursor.execute(
                        """
                        UPDATE episodes
                        SET transcript_path = ?, status = 'transcribed',
                            priority_score = 0.8, content_type = 'discussion'
                        WHERE id = ?
                    """,
                        (transcript_path, db_id),
                    )

                    processed_files += 1
                    logger.info(
                        f"✅ Transcribed: {audio_file.name} (took {file_processing_time/60:.1f} min)"
                    )
                else:
                    logger.error(f"❌ Failed to transcribe: {audio_file.name}")
                    cursor.execute(
                        "UPDATE episodes SET status = 'failed' WHERE id = ?", (db_id,)
                    )

                # Progress update
                elapsed_time = time.time() - start_time
                remaining_files = len(audio_files) - (i + 1)
                if processed_files > 0:
                    avg_time_per_file = elapsed_time / processed_files
                    estimated_remaining = avg_time_per_file * remaining_files
                    logger.info(
                        f"📈 Progress: {processed_files}/{len(audio_files)} files, ~{estimated_remaining/60:.1f} min remaining"
                    )

            except Exception as e:
                logger.error(f"Error processing {audio_file.name}: {e}")
                if "db_id" in locals():
                    cursor.execute(
                        "UPDATE episodes SET status = 'failed' WHERE id = ?", (db_id,)
                    )

        conn.commit()
        conn.close()

        total_time = time.time() - start_time
        logger.info(
            f"🏁 Audio cache processing complete: {processed_files} files in {total_time/60:.1f} minutes"
        )

    def _process_pending_episodes(self):
        """Process episodes awaiting transcription"""
        logger.info(
            "⚙️ Processing episodes awaiting transcription (pending/pre-download)..."
        )

        results = self.content_processor.process_all_pending()

        if results:
            logger.info(f"✅ Processed {len(results)} pending episodes")
        else:
            logger.info("No pending episodes to process")

    def _generate_daily_digest(self):
        """Generate daily digest from BOTH RSS and YouTube 'transcribed' episodes"""
        logger.info("📝 Generating daily digest from RSS + YouTube transcripts...")

        # Check RSS transcribed episodes
        conn = get_connection(self.db_path)
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
                conn = get_connection(youtube_db_path)
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT COUNT(*) FROM episodes WHERE status = 'transcribed'"
                )
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
        logger.info(
            f"📋 Total transcripts for digest: {rss_transcribed_count} RSS + {youtube_transcribed_count} YouTube = {total_transcribed}"
        )

        if total_transcribed == 0:
            logger.warning("No 'transcribed' episodes available from either database")
            return False

        # Generate OpenAI GPT-5 powered digest (reads from both databases automatically)
        success, digest_path, cross_refs_path = (
            self.openai_integration.generate_digest()
        )

        if success:
            logger.info(f"✅ Daily digest generated: {digest_path}")
            return True
        else:
            logger.error("❌ Failed to generate daily digest")
            return False

    def _generate_weekly_digest(self):
        """Generate Friday digest with weekly summary (7-day window)"""
        logger.info("📅 Generating FRIDAY digest with weekly overview...")

        # First generate regular daily digest
        daily_success = self._generate_daily_digest()
        if not daily_success:
            logger.error("❌ Failed to generate daily digest component")
            return False

        # Get episodes from the past 7 days that were already digested
        seven_days_ago = now_utc() - timedelta(days=7)

        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) FROM episodes
            WHERE digest_date IS NOT NULL
            AND datetime(digest_date) >= datetime(?)
        """,
            (seven_days_ago.strftime("%Y-%m-%d"),),
        )
        rss_weekly_count = cursor.fetchone()[0]

        conn.close()

        # Check YouTube database for weekly episodes
        youtube_weekly_count = 0
        youtube_db_path = "youtube_transcripts.db"
        if Path(youtube_db_path).exists():
            try:
                conn = get_connection(youtube_db_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT COUNT(*) FROM episodes
                    WHERE digest_date IS NOT NULL
                    AND datetime(digest_date) >= datetime(?)
                """,
                    (seven_days_ago.strftime("%Y-%m-%d"),),
                )
                youtube_weekly_count = cursor.fetchone()[0]

                conn.close()
            except Exception as e:
                logger.warning(f"Could not check YouTube weekly episodes: {e}")

        total_weekly = rss_weekly_count + youtube_weekly_count
        logger.info(f"📊 Weekly digest coverage: {total_weekly} episodes over 7 days")

        return True

    def _generate_catchup_digest(self):
        """Generate Monday catch-up digest (Friday 06:00 → Monday run)"""
        logger.info("📅 Generating MONDAY catch-up digest...")

        # Calculate window: Previous Friday 6 AM to now
        now = now_utc()

        # Find last Friday
        days_since_friday = (now.weekday() + 3) % 7  # Monday=0, Friday=4
        if days_since_friday == 0:  # Today is Friday
            days_since_friday = 7  # Last Friday was a week ago

        last_friday_6am = now - timedelta(days=days_since_friday)
        last_friday_6am = last_friday_6am.replace(
            hour=6, minute=0, second=0, microsecond=0
        )

        logger.info(
            f"🕰️ Catch-up window: {last_friday_6am.strftime('%Y-%m-%d %H:%M')} to {now.strftime('%Y-%m-%d %H:%M')}"
        )

        # Check for episodes in catch-up window
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # Look for episodes published since Friday 6 AM that haven't been digested
        cursor.execute(
            """
            SELECT COUNT(*) FROM episodes
            WHERE datetime(published_date) >= datetime(?)
            AND (digest_date IS NULL OR status = 'transcribed')
        """,
            (last_friday_6am.isoformat(),),
        )
        rss_catchup_count = cursor.fetchone()[0]

        conn.close()

        # Check YouTube database for catch-up episodes
        youtube_catchup_count = 0
        youtube_db_path = "youtube_transcripts.db"
        if Path(youtube_db_path).exists():
            try:
                conn = get_connection(youtube_db_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT COUNT(*) FROM episodes
                    WHERE datetime(published_date) >= datetime(?)
                    AND (digest_date IS NULL OR status = 'transcribed')
                """,
                    (last_friday_6am.isoformat(),),
                )
                youtube_catchup_count = cursor.fetchone()[0]

                conn.close()
            except Exception as e:
                logger.warning(f"Could not check YouTube catch-up episodes: {e}")

        total_catchup = rss_catchup_count + youtube_catchup_count
        logger.info(
            f"📊 Catch-up digest coverage: {total_catchup} episodes since Friday 6 AM"
        )

        if total_catchup == 0:
            logger.info("✅ No catch-up needed - no new episodes since Friday")
            return True

        # Generate digest from available transcribed episodes
        return self._generate_daily_digest()

    def _create_tts_audio(self):
        """Create TTS audio for the daily digest - CRITICAL FUNCTION"""
        logger.info("🎙️ Creating TTS audio...")
        logger.info("========================================")
        logger.info("🔥 TTS GENERATION - CRITICAL DEBUG INFO")
        logger.info("========================================")

        # Check environment variables
        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        if elevenlabs_key:
            logger.info(f"✅ ELEVENLABS_API_KEY found (length: {len(elevenlabs_key)})")
        else:
            logger.error("❌ ELEVENLABS_API_KEY is missing or empty!")

        # Check for existing digest files
        digest_files = list(Path("daily_digests").glob("daily_digest_*.md"))
        logger.info(
            f"📄 Found {len(digest_files)} digest files: {[f.name for f in digest_files]}"
        )

        # Check current directory contents
        logger.info("📁 Current directory contents:")
        for item in Path(".").iterdir():
            if item.is_file():
                logger.info(f"   📄 {item.name}")

        try:
            logger.info("🚀 Running multi-topic TTS generation subprocess...")
            logger.info("Command: python3 multi_topic_tts_generator.py")

            # Run TTS generation with enhanced logging
            result = subprocess.run(
                ["python3", "multi_topic_tts_generator.py"],
                capture_output=True,
                text=True,
                timeout=600,
            )

            logger.info(f"🔍 TTS subprocess return code: {result.returncode}")
            logger.info(f"🔍 TTS subprocess stdout length: {len(result.stdout)}")
            logger.info(f"🔍 TTS subprocess stderr length: {len(result.stderr)}")

            if result.stdout:
                logger.info("📝 TTS subprocess STDOUT:")
                for line in result.stdout.split("\n"):
                    if line.strip():
                        logger.info(f"   STDOUT: {line}")

            if result.stderr:
                logger.error("📝 TTS subprocess STDERR:")
                for line in result.stderr.split("\n"):
                    if line.strip():
                        logger.error(f"   STDERR: {line}")

            # Check what files were created after TTS
            logger.info("📁 Post-TTS daily_digests directory:")
            if Path("daily_digests").exists():
                for item in Path("daily_digests").iterdir():
                    logger.info(f"   📄 {item.name} ({item.stat().st_size} bytes)")
            else:
                logger.error("❌ daily_digests directory does not exist!")

            # Look for expected audio files
            audio_files = list(
                Path("daily_digests").glob("complete_topic_digest_*.mp3")
            )
            logger.info(
                f"🎵 Found {len(audio_files)} audio files: {[f.name for f in audio_files]}"
            )

            if result.returncode == 0:
                if audio_files:
                    logger.info("✅ TTS audio generated successfully with audio files!")
                    return True
                else:
                    logger.error(
                        "❌ TTS subprocess succeeded but NO AUDIO FILES found!"
                    )
                    return False
            else:
                logger.error(
                    f"❌ TTS generation failed with return code {result.returncode}"
                )
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ TTS generation timed out after 600 seconds")
            return False
        except Exception as e:
            logger.error(f"❌ Exception during TTS generation: {e}")
            import traceback

            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return False
        finally:
            logger.info("========================================")

    def _create_tts_audio_today_only(self, today: str) -> bool:
        """Create TTS audio for today's digests only - Transactional version"""
        logger.info(f"🎙️ Creating TTS audio for today only: {today}")

        # Check environment variables
        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        if elevenlabs_key:
            logger.info(f"✅ ELEVENLABS_API_KEY found (length: {len(elevenlabs_key)})")
        else:
            logger.error("❌ ELEVENLABS_API_KEY is missing or empty!")

        # Check for existing digest files
        digest_files = list(Path("daily_digests").glob("*_digest_*.md"))
        logger.info(
            f"📄 Found {len(digest_files)} total digest files: {[f.name for f in digest_files]}"
        )

        try:
            logger.info(f"🚀 Running TTS generation with --since {today}")

            # Run TTS generation with date filter
            result = subprocess.run(
                ["python3", "multi_topic_tts_generator.py", "--since", today],
                capture_output=True,
                text=True,
                timeout=600,
            )

            logger.info(f"🔍 TTS subprocess return code: {result.returncode}")

            if result.stdout:
                for line in result.stdout.split("\n"):
                    if line.strip():
                        logger.info(f"   {line}")

            if result.stderr:
                for line in result.stderr.split("\n"):
                    if line.strip():
                        logger.warning(f"   {line}")

            if result.returncode != 0:
                logger.error(
                    f"❌ TTS generation failed with return code {result.returncode}"
                )
                return False

            # Check if any MP3 files were generated today
            today_mp3s = []
            for mp3_file in Path("daily_digests").glob("*_digest_*.mp3"):
                # Extract timestamp from filename
                import re

                match = re.search(r"_digest_(\d{8})_", mp3_file.name)
                if match:
                    file_date = match.group(1)
                    expected_date = today.replace("-", "")
                    if file_date == expected_date:
                        today_mp3s.append(mp3_file)

            if today_mp3s:
                logger.info(f"✅ Generated {len(today_mp3s)} MP3 files for today:")
                for mp3 in sorted(today_mp3s):
                    logger.info(f"   🎵 {mp3.name}")
                return True
            else:
                logger.info(f"ℹ️  No MP3 files generated for today ({today})")
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ TTS generation timed out after 10 minutes")
            return False
        except Exception as e:
            logger.error(f"❌ TTS generation error: {e}")
            return False

    def _deploy_to_github(self):
        """Deploy latest episode to GitHub releases"""
        logger.info("🚀 Deploying to GitHub...")

        try:
            result = subprocess.run(
                ["python3", "deploy_multi_topic.py"],
                capture_output=True,
                text=True,
                timeout=300,
            )

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
            result = subprocess.run(
                ["python3", "rss_generator_multi_topic.py"],
                capture_output=True,
                text=True,
                timeout=120,
            )

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
        logger.info(
            "📋 Marking episodes as digested in both RSS and YouTube databases..."
        )

        # Mark RSS episodes as digested
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE episodes SET status = 'digested' WHERE status = 'transcribed'"
        )
        rss_updated_count = cursor.rowcount

        conn.commit()
        conn.close()

        # Mark YouTube episodes as digested
        youtube_updated_count = 0
        youtube_db_path = "youtube_transcripts.db"
        if Path(youtube_db_path).exists():
            try:
                conn = get_connection(youtube_db_path)
                cursor = conn.cursor()

                cursor.execute(
                    "UPDATE episodes SET status = 'digested' WHERE status = 'transcribed'"
                )
                youtube_updated_count = cursor.rowcount

                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"Could not update YouTube database: {e}")

        total_updated = rss_updated_count + youtube_updated_count
        logger.info(
            f"✅ Marked episodes as digested: {rss_updated_count} RSS + {youtube_updated_count} YouTube = {total_updated} total"
        )

    def _cleanup_old_files(self):
        """Clean up old files and transcripts using configured retention system"""
        retention_days = CONFIG["RETENTION_DAYS"]
        logger.info(f"🧹 Running {retention_days}-day retention cleanup...")

        try:
            cleanup = RetentionCleanup(retention_days=retention_days)
            results = cleanup.run_full_cleanup()

            total_files = (
                results["transcript_files_removed"] + results["digest_files_removed"]
            )
            total_episodes = (
                results["rss_episodes_cleaned"] + results["youtube_episodes_cleaned"]
            )

            if total_files > 0 or total_episodes > 0:
                logger.info(
                    f"✅ Retention cleanup completed: {total_files} files removed, {total_episodes} episodes cleaned"
                )
            else:
                logger.info("✅ No cleanup needed - all files within retention period")

        except Exception as e:
            logger.warning(f"⚠️  Retention cleanup failed: {e}")

    def get_status_summary(self):
        """Get current system status summary including failure statistics"""
        status_summary = {}

        # Process both RSS and YouTube databases
        for db_name, db_path in [
            ("RSS", self.db_path),
            ("YouTube", "youtube_transcripts.db"),
        ]:
            try:
                conn = get_connection(db_path)
                cursor = conn.cursor()

                # Get episode counts by status
                cursor.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM episodes
                    GROUP BY status
                    ORDER BY count DESC
                """
                )

                status_counts = dict(cursor.fetchall())

                # Get failure statistics using FailureManager
                failure_manager = FailureManager(db_path)
                failure_stats = failure_manager.get_failure_statistics(days_back=7)

                # Get retry candidates
                retry_candidates = failure_manager.get_retry_candidates()

                conn.close()

                status_summary[db_name] = {
                    "status_counts": status_counts,
                    "total_episodes": sum(status_counts.values()),
                    "failure_stats": failure_stats,
                    "retry_candidates": len(retry_candidates),
                }

            except Exception as e:
                status_summary[db_name] = {"error": str(e)}

        # Check audio_cache files
        audio_cache = Path(CONFIG["AUDIO_CACHE_DIR"])
        audio_cache_count = (
            len(list(audio_cache.glob("*.mp3"))) if audio_cache.exists() else 0
        )

        status_summary["system"] = {"audio_cache_files": audio_cache_count}

        return status_summary


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Daily Tech Digest Pipeline")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--run", action="store_true", help="Run daily workflow")
    parser.add_argument(
        "--rss-only",
        action="store_true",
        help="Process RSS feeds only (GitHub Actions mode)",
    )
    parser.add_argument("--cleanup", action="store_true", help="Run cleanup only")
    parser.add_argument(
        "--test", action="store_true", help="Test individual components"
    )
    parser.add_argument(
        "--hours-back",
        type=int,
        help="Override feed lookback hours (default: uses FEED_LOOKBACK_HOURS env var)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - no external API calls or costly operations",
    )
    parser.add_argument(
        "--timeout", type=int, default=0, help="Timeout in seconds (0 = no timeout)"
    )
    args = parser.parse_args()

    # Set up dry-run and mock mode environment variables
    if args.dry_run:
        os.environ["DRY_RUN"] = "1"
        os.environ["MOCK_OPENAI"] = "1"
        if not os.getenv("CI_SMOKE"):
            os.environ["CI_SMOKE"] = "1"

    # Set up timeout handling (Unix systems only)
    if args.timeout > 0:
        try:
            import signal

            def timeout_handler(signum, frame):
                if "logger" in globals():
                    logger.error(f"⏰ Operation timed out after {args.timeout} seconds")
                else:
                    print(f"⏰ Operation timed out after {args.timeout} seconds")
                sys.exit(124)  # Standard timeout exit code

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(args.timeout)
        except (ImportError, AttributeError):
            # Windows or system without SIGALRM support
            print(
                f"⚠️  Timeout not supported on this system (requested {args.timeout}s)"
            )

    # Set up centralized logging
    from utils.logging_setup import configure_logging

    configure_logging()
    global logger
    logger = logging.getLogger(__name__)

    # Override log level if verbose
    if args.verbose:
        os.environ["LOG_LEVEL"] = "DEBUG"
        configure_logging()  # Reconfigure with DEBUG level

    # Run startup preflight checks (PID-guarded, runs once per process)
    from utils.startup_preflight import run_startup_preflight

    run_startup_preflight()

    if args.dry_run:
        logger.info(
            "🧪 DRY RUN MODE: No external API calls or costly operations will be performed"
        )

    # Validate configuration and environment
    from config import config

    logger.info("🔧 Validating configuration and environment...")

    pipeline = DailyPodcastPipeline(hours_back=args.hours_back)

    if args.status:
        status = pipeline.get_status_summary()
        print("\n📊 System Status:")
        print("=" * 60)

        # Show status for each database
        for db_name in ["RSS", "YouTube"]:
            if db_name in status:
                db_status = status[db_name]
                if "error" in db_status:
                    print(f"\n❌ {db_name} Database: {db_status['error']}")
                    continue

                print(f"\n📊 {db_name} Database:")
                print(f"  Episodes by status: {db_status['status_counts']}")
                print(f"  Total episodes: {db_status['total_episodes']}")
                print(f"  Episodes eligible for retry: {db_status['retry_candidates']}")

                # Show failure statistics if available
                failure_stats = db_status.get("failure_stats", {})
                if failure_stats.get("total_failed_episodes", 0) > 0:
                    print(
                        f"  Failed episodes (last 7 days): {failure_stats['total_failed_episodes']}"
                    )
                    if failure_stats.get("retry_distribution"):
                        print(
                            f"  Retry attempts distribution: {failure_stats['retry_distribution']}"
                        )

        # Show system information
        if "system" in status:
            print(f"\n🗂️ System:")
            print(f"  Audio cache files: {status['system']['audio_cache_files']}")

        return

    if args.cleanup:
        logger.info("🧹 Running cleanup only...")
        pipeline._cleanup_old_files()
        return

    if args.test:
        logger.info("🧪 Testing components...")
        # Test each component
        print("Feed monitor:", "✅" if pipeline.feed_monitor else "❌")
        print(
            "Content processor:", "✅" if pipeline.content_processor.asr_model else "❌"
        )
        print(
            "OpenAI integration:",
            "✅" if pipeline.openai_integration.api_available else "❌",
        )
        return

    if args.run:
        # Run the complete daily workflow
        success = pipeline.run_daily_workflow()
        exit(0 if success else 1)

    if args.rss_only:
        # GitHub Actions mode: Process RSS + pull YouTube transcripts + generate unified digest
        logger.info("🚀 Starting GITHUB ACTIONS Pipeline")
        logger.info(
            "📝 GITHUB SCOPE: RSS processing + YouTube transcripts + Digest generation"
        )
        logger.info("=" * 75)

        try:
            # Pull latest changes (gets YouTube transcripts already pushed to repo)
            import subprocess

            subprocess.run(["git", "pull", "origin", "main"], check=True)
            logger.info(
                "✅ Pulled latest changes - YouTube transcripts already in repo"
            )

            # Step 1: Monitor RSS feeds and add new episodes
            pipeline._monitor_rss_feeds()

            # Step 2: Process RSS audio cache files → transcribe → mark 'transcribed'
            pipeline._process_audio_cache_files()

            # Step 3: Process pending RSS episodes → transcribe → mark 'transcribed'
            pipeline._process_pending_episodes()

            # Step 4: Generate digest from ALL 'transcribed' episodes (RSS + YouTube databases)
            logger.info(
                "📊 Generating digest from ALL 'transcribed' episodes (RSS + YouTube)"
            )
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
                logger.info(
                    "🔄 Local machine will pull digest status updates on next run"
                )
                exit(0)
            else:
                # Digest generation failed - this is a critical error
                logger.error("❌ CRITICAL: Daily digest generation failed")
                logger.error("🔄 Check API credentials and transcript availability")

                # Still run cleanup for housekeeping
                pipeline._cleanup_old_files()

                logger.error("❌ GITHUB ACTIONS workflow FAILED")
                exit(1)

        except Exception as e:
            logger.error(f"❌ GITHUB ACTIONS workflow failed: {e}")
            exit(1)

    if args.dry_run:
        # Dry run mode - perform validation and planning without expensive operations
        logger.info("🧪 Starting DRY RUN mode...")

        # Create dry-run summary
        dry_run_summary = {
            "would_process": {},
            "configuration": {},
            "estimated_actions": [],
        }

        # Check feeds without downloading
        try:
            from utils.datetime_utils import cutoff_utc

            cutoff = cutoff_utc(int(os.getenv("FEED_LOOKBACK_HOURS", "48")))
            logger.info(f"🕐 Dry run cutoff: {cutoff.isoformat()}Z UTC")

            # Simulate feed checking
            dry_run_summary["would_process"]["cutoff_time"] = cutoff.isoformat()
            dry_run_summary["would_process"][
                "feeds_to_check"
            ] = "RSS feeds would be checked"
            dry_run_summary["estimated_actions"].append(
                "Check RSS feeds for new episodes"
            )

            # Check current database state
            conn = get_connection(CONFIG["DB_PATH"])
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) FROM episodes GROUP BY status")
            status_counts = dict(cursor.fetchall())
            conn.close()

            dry_run_summary["would_process"]["current_episodes"] = status_counts

            if status_counts.get("transcribed", 0) > 0:
                dry_run_summary["estimated_actions"].append(
                    f"Generate digest from {status_counts['transcribed']} transcribed episodes"
                )
                dry_run_summary["estimated_actions"].append("Create TTS audio files")
                dry_run_summary["estimated_actions"].append("Deploy to GitHub releases")
                dry_run_summary["estimated_actions"].append("Update RSS feed")

            # Configuration check
            dry_run_summary["configuration"]["openai_mock"] = (
                os.getenv("MOCK_OPENAI") == "1"
            )
            dry_run_summary["configuration"]["ci_smoke"] = os.getenv("CI_SMOKE") == "1"

        except Exception as e:
            logger.error(f"❌ Dry run validation failed: {e}")
            exit(1)

        # Write dry-run summary
        import json

        summary_file = Path("dry_run_summary.json")
        with open(summary_file, "w") as f:
            json.dump(dry_run_summary, f, indent=2, default=str)

        logger.info(f"✅ DRY RUN completed - summary saved to {summary_file}")
        logger.info(
            f"📊 Would process: {len(dry_run_summary['estimated_actions'])} actions"
        )
        for action in dry_run_summary["estimated_actions"]:
            logger.info(f"   • {action}")

        exit(0)

    # Default: show help and status
    parser.print_help()
    print("\nCurrent status:")
    status = pipeline.get_status_summary()
    print(
        f"Episodes ready for digest: {status['database_status'].get('transcribed', 0)}"
    )
    print(f"Audio files to process: {status['audio_cache_files']}")


if __name__ == "__main__":
    main()
