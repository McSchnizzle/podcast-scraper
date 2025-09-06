#!/usr/bin/env python3
"""
Local YouTube Processor - Handles YouTube feeds separately from GitHub Actions
Designed to run locally via cron/launchctl to avoid GitHub Actions IP blocking
"""

import argparse
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from config import config
from content_processor import ContentProcessor
from utils.datetime_utils import now_utc
from utils.db import get_connection
from utils.logging_setup import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


class YouTubeProcessor:
    def __init__(self, youtube_db_path: str = "youtube_transcripts.db"):
        self.youtube_db_path = youtube_db_path
        # YouTube processor uses OpenAI, not Claude
        self.config = config

        # Initialize YouTube-specific database
        self._init_youtube_database()

        # Content processor for transcription (handles YouTube vs RSS automatically)
        self.content_processor = ContentProcessor(
            db_path=youtube_db_path,  # Use YouTube-specific database
            audio_dir="audio_cache",
        )

    def _init_youtube_database(self):
        """Initialize YouTube-specific database with same schema"""
        conn = get_connection(self.youtube_db_path)
        cursor = conn.cursor()

        # Feeds table - YouTube feeds only
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                type TEXT NOT NULL CHECK(type = 'youtube'),
                topic_category TEXT NOT NULL,
                last_checked TIMESTAMP,
                active BOOLEAN DEFAULT 1
            )
        """
        )

        # Episodes table - YouTube episodes only
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER,
                episode_id TEXT UNIQUE,
                title TEXT NOT NULL,
                published_date TIMESTAMP,
                audio_url TEXT,
                transcript_path TEXT,
                status TEXT DEFAULT 'pre-download',
                priority_score REAL DEFAULT 0.0,
                content_type TEXT,
                failure_reason TEXT,
                failure_timestamp TIMESTAMP,
                retry_count INTEGER DEFAULT 0,
                FOREIGN KEY (feed_id) REFERENCES feeds (id)
            )
        """
        )

        conn.commit()
        conn.close()
        logger.info(f"✅ YouTube database initialized: {self.youtube_db_path}")

    def sync_youtube_feeds(self):
        """Sync YouTube feeds from config to YouTube database"""
        conn = get_connection(self.youtube_db_path)
        cursor = conn.cursor()

        # Get YouTube feeds from config
        youtube_feeds = [
            feed for feed in self.config.get_feed_config() if feed["type"] == "youtube"
        ]

        logger.info(f"Syncing {len(youtube_feeds)} YouTube feeds to database...")

        for feed in youtube_feeds:
            cursor.execute(
                """
                INSERT OR REPLACE INTO feeds (url, title, type, topic_category, active, last_checked)
                VALUES (?, ?, ?, ?, 1, datetime('now'))
            """,
                (feed["url"], feed["title"], feed["type"], feed["topic_category"]),
            )

        conn.commit()
        conn.close()
        logger.info(f"✅ Synced {len(youtube_feeds)} YouTube feeds")

    def check_new_youtube_episodes(self, hours_back: int = 168) -> List[Dict]:
        """Check for new YouTube episodes (default: 7 days back to catch missed episodes)"""
        from feed_monitor import FeedMonitor

        # Create temporary feed monitor with YouTube database
        feed_monitor = FeedMonitor(db_path=self.youtube_db_path)

        # Check for new episodes going back specified hours (default 7 days = 168 hours)
        logger.info(
            f"🔍 Checking for YouTube episodes from last {hours_back} hours ({hours_back/24:.1f} days)"
        )
        new_episodes = feed_monitor.check_new_episodes(hours_back=hours_back)

        logger.info(f"Found {len(new_episodes)} new YouTube episodes")
        return new_episodes

    def process_pending_youtube_episodes(self) -> int:
        """Process pending YouTube episodes using YouTube Transcript API with smart throttling"""
        import time

        conn = get_connection(self.youtube_db_path)
        cursor = conn.cursor()

        # Get pending YouTube episodes (only 'pre-download' status)
        cursor.execute(
            """
            SELECT id, title, audio_url, episode_id FROM episodes
            WHERE status = 'pre-download'
            AND audio_url IS NOT NULL
            AND transcript_path IS NULL
            ORDER BY published_date DESC
        """
        )

        pending_episodes = cursor.fetchall()

        if not pending_episodes:
            logger.info("No pending YouTube episodes to process")
            conn.close()
            return 0

        logger.info(
            f"🎬 Processing {len(pending_episodes)} YouTube episodes with smart throttling..."
        )

        processed_count = 0
        consecutive_failures = 0
        failed_episodes = []

        def process_episode(episode_data):
            """Process a single YouTube episode"""
            nonlocal processed_count, consecutive_failures
            episode_id, title, video_url, episode_guid = episode_data

            try:
                logger.info(f"📺 Processing: {title}")

                # Use YouTube Transcript API directly (no video download)
                transcript = self.content_processor._process_youtube_episode(
                    video_url, episode_guid
                )

                if transcript:
                    # Reset consecutive failures on success
                    consecutive_failures = 0

                    # Save transcript file
                    transcript_path = self.content_processor._save_transcript(
                        episode_guid, transcript
                    )

                    # Update episode to 'transcribed' status (skip 'downloaded' for YouTube)
                    cursor.execute(
                        """
                        UPDATE episodes
                        SET transcript_path = ?, status = 'transcribed',
                            priority_score = 0.8, content_type = 'discussion'
                        WHERE id = ?
                    """,
                        (transcript_path, episode_id),
                    )

                    # Score the transcript for topic relevance (OpenAI)
                    try:
                        from openai_scorer import OpenAITopicScorer

                        scorer = OpenAITopicScorer(self.youtube_db_path)
                        if getattr(scorer, "api_available", True) and transcript:
                            scores = scorer.score_transcript(
                                transcript, episode_guid or str(episode_id)
                            )
                            if scores and not scores.get("error"):
                                cursor.execute(
                                    """
                                    UPDATE episodes
                                    SET topic_relevance_json = ?, scores_version = ?
                                    WHERE id = ?
                                """,
                                    (
                                        json.dumps(scores),
                                        scores.get("version", "1.0"),
                                        episode_id,
                                    ),
                                )
                                logger.info(
                                    f"✅ Saved topic_relevance_json for YouTube episode {episode_id}"
                                )
                            else:
                                logger.warning(
                                    f"⚠️ YouTube episode {episode_id} scoring returned error: {scores}"
                                )
                        else:
                            logger.warning(
                                f"⚠️ OpenAI scorer unavailable or empty transcript for YouTube episode {episode_id}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"⚠️ YouTube episode {episode_id} topic scoring failed: {e}"
                        )

                    processed_count += 1
                    logger.info(f"✅ Transcribed YouTube episode: {title}")

                    # Commit after each successful episode
                    conn.commit()
                    return True

                else:
                    # Track throttling failures
                    consecutive_failures += 1
                    logger.warning(
                        f"❌ Failed to get transcript: {title} (failure #{consecutive_failures})"
                    )

                    # Don't mark as failed yet - might retry
                    failed_episodes.append(episode_data)
                    return False

            except Exception as e:
                consecutive_failures += 1
                logger.error(
                    f"Error processing YouTube episode {episode_id}: {e} (failure #{consecutive_failures})"
                )
                failed_episodes.append(episode_data)
                return False

        # Process episodes with smart throttling
        for i, episode_data in enumerate(pending_episodes):
            success = process_episode(episode_data)

            if not success:
                # After 5th consecutive failure, wait 60 seconds and retry failed episodes
                if consecutive_failures >= 5:
                    logger.warning(
                        f"🚨 {consecutive_failures} consecutive failures - entering retry mode"
                    )
                    logger.info(
                        "⏳ Waiting 60 seconds for YouTube API rate limit reset..."
                    )
                    time.sleep(60)

                    # Retry failed episodes with longer delays
                    retry_count = 0
                    logger.info(
                        f"🔄 Retrying {len(failed_episodes)} failed episodes..."
                    )

                    for retry_episode in failed_episodes[
                        :
                    ]:  # Copy list to allow modification
                        logger.info(
                            f"🔄 Retry {retry_count + 1}/{len(failed_episodes)}: {retry_episode[1]}"
                        )

                        if process_episode(retry_episode):
                            failed_episodes.remove(retry_episode)
                            retry_count += 1
                        else:
                            # Mark permanently failed episodes
                            cursor.execute(
                                "UPDATE episodes SET status = ? WHERE id = ?",
                                ("failed", retry_episode[0]),
                            )

                        # 5-second delay between retries
                        time.sleep(5)

                    # Reset for remaining episodes
                    consecutive_failures = 0
                    logger.info(f"✅ Retry complete: {retry_count} episodes recovered")

            # Regular 5-second delay between episodes (already handled in content_processor)

        # Mark any remaining failed episodes
        for episode_data in failed_episodes:
            cursor.execute(
                "UPDATE episodes SET status = ? WHERE id = ?",
                ("failed", episode_data[0]),
            )

        conn.commit()
        conn.close()

        logger.info(
            f"✅ YouTube Transcript API: {processed_count}/{len(pending_episodes)} episodes transcribed"
        )
        return processed_count

    def get_youtube_stats(self) -> Dict:
        """Get YouTube processing statistics"""
        conn = get_connection(self.youtube_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT status, COUNT(*) as count
            FROM episodes
            GROUP BY status
            ORDER BY count DESC
        """
        )

        status_counts = dict(cursor.fetchall())

        cursor.execute("SELECT COUNT(*) FROM episodes")
        total_episodes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM feeds WHERE active = 1")
        active_feeds = cursor.fetchone()[0]

        conn.close()

        return {
            "status_counts": status_counts,
            "total_episodes": total_episodes,
            "active_feeds": active_feeds,
        }

    def cleanup_old_episodes(self, days_old: int = 7):
        """Clean up old failed/processed YouTube episodes"""
        conn = get_connection(self.youtube_db_path)
        cursor = conn.cursor()

        cutoff_date = now_utc() - timedelta(days=days_old)

        cursor.execute(
            """
            DELETE FROM episodes
            WHERE status IN ('failed', 'digested')
            AND (failure_timestamp < ? OR published_date < ?)
        """,
            (cutoff_date.strftime("%Y-%m-%d"), cutoff_date.strftime("%Y-%m-%d")),
        )

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"🧹 Cleaned up {deleted_count} old YouTube episodes")
        return deleted_count

    def pull_digest_status_updates(self):
        """Pull digest status updates from GitHub (episodes marked as digested)"""
        try:
            import subprocess

            logger.info("🔄 Pulling digest status updates from GitHub...")

            # Pull only to get digest status updates, not for any processing logic
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info("✅ Pulled latest digest statuses from GitHub")
                return True
            else:
                logger.warning(f"⚠️ Git pull warning: {result.stderr}")
                # Don't fail the whole process if git pull fails
                return False

        except Exception as e:
            logger.warning(f"⚠️ Could not pull from GitHub: {e}")
            # Continue processing even if pull fails
            return False

    def commit_and_push_transcripts(self):
        """Commit and push YouTube transcripts to GitHub"""
        try:
            import subprocess

            logger.info("📤 Committing and pushing YouTube transcripts to GitHub...")

            # Check if there are changes to commit
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if not result.stdout.strip():
                logger.info("📭 No new transcripts to commit")
                return True

            # Add all changes (transcripts and database)
            subprocess.run(["git", "add", "."], timeout=10)

            # Get count of new transcripts
            transcript_count = len(
                [
                    line
                    for line in result.stdout.split("\n")
                    if line.strip().endswith(".txt")
                ]
            )

            # Commit with informative message
            commit_msg = (
                f"Add YouTube transcripts from automated processing\n\n"
                f"- Processed {transcript_count} YouTube episodes using YouTube Transcript API\n"
                f"- Updated youtube_transcripts.db with transcribed status\n"
                f"- Ready for GitHub Actions digest generation\n\n"
                f"🤖 Generated with [Claude Code](https://claude.ai/code)\n\n"
                f"Co-Authored-By: Claude <noreply@anthropic.com>"
            )

            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if commit_result.returncode != 0:
                logger.warning(f"⚠️ Git commit issue: {commit_result.stderr}")
                return False

            # Push to GitHub
            push_result = subprocess.run(
                ["git", "push", "origin", "main"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if push_result.returncode == 0:
                logger.info("✅ Successfully pushed YouTube transcripts to GitHub")
                return True
            else:
                logger.error(f"❌ Git push failed: {push_result.stderr}")
                return False

        except Exception as e:
            logger.error(f"❌ Could not commit/push to GitHub: {e}")
            return False

    def run_youtube_workflow(self, hours_back: int = 168):
        """LOCAL ONLY: Download and transcribe YouTube episodes (default: 7 days back)"""
        logger.info("🎬 Starting LOCAL YouTube Transcription Workflow")
        logger.info(
            "📝 LOCAL SCOPE: YouTube Transcript API → Mark 'transcribed' → Push to GitHub"
        )
        logger.info(
            "🚀 RESULT: GitHub repo will have YouTube transcripts ready for GitHub Actions"
        )
        logger.info("=" * 75)

        try:
            # Step 0: Pull digest status updates (optional, doesn't affect processing)
            self.pull_digest_status_updates()

            # Step 1: Sync YouTube feeds from config
            self.sync_youtube_feeds()

            # Step 2: Check for NEW YouTube episodes only
            new_episodes = self.check_new_youtube_episodes(hours_back)

            # Step 3: Use YouTube Transcript API → mark as 'transcribed'
            processed_count = self.process_pending_youtube_episodes()

            # Step 4: Show what we accomplished locally
            stats = self.get_youtube_stats()
            logger.info(f"📊 Local YouTube Stats: {stats['status_counts']}")

            # Step 5: Commit and push any new transcripts to GitHub
            if processed_count > 0:
                push_success = self.commit_and_push_transcripts()
                if push_success:
                    logger.info(
                        f"📤 Pushed {processed_count} new YouTube transcripts to GitHub"
                    )
                else:
                    logger.warning(
                        "⚠️ Failed to push transcripts to GitHub - manual push may be needed"
                    )

            # Step 6: Cleanup only old failed episodes (keep transcribed for GitHub)
            self.cleanup_old_episodes()

            logger.info("✅ LOCAL YouTube transcription completed")
            logger.info(
                f"🤖 GitHub Actions will process transcripts in next digest run"
            )
            return True

        except Exception as e:
            logger.error(f"❌ LOCAL YouTube workflow failed: {e}")
            return False


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Local YouTube Processor")
    parser.add_argument(
        "--process-new", action="store_true", help="Process new YouTube episodes"
    )
    parser.add_argument(
        "--hours-back",
        type=int,
        default=168,
        help="Hours back to check for new episodes (default: 168 = 7 days)",
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show YouTube processing statistics"
    )
    parser.add_argument(
        "--cleanup", action="store_true", help="Cleanup old episodes only"
    )
    parser.add_argument(
        "--sync-feeds", action="store_true", help="Sync YouTube feeds from config"
    )

    args = parser.parse_args()

    processor = YouTubeProcessor()

    if args.stats:
        stats = processor.get_youtube_stats()
        print(f"\n📊 YouTube Processing Statistics:")
        print(f"Active feeds: {stats['active_feeds']}")
        print(f"Total episodes: {stats['total_episodes']}")
        print(f"Status breakdown: {stats['status_counts']}")
        return

    if args.cleanup:
        processor.cleanup_old_episodes()
        return

    if args.sync_feeds:
        processor.sync_youtube_feeds()
        return

    if args.process_new:
        success = processor.run_youtube_workflow(args.hours_back)
        exit(0 if success else 1)

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
