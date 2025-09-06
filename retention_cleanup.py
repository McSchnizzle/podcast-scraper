#!/usr/bin/env python3
"""
14-Day Retention Cleanup System
Removes transcript files and cleans database fields older than 14 days
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from utils.datetime_utils import now_utc
from utils.db import get_connection
from utils.logging_setup import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


class RetentionCleanup:
    def __init__(self, retention_days: int = 14):
        self.retention_days = retention_days
        self.cutoff_date = now_utc() - timedelta(days=retention_days)
        self.cutoff_timestamp = self.cutoff_date.timestamp()

        logger.info(
            f"🗑️  Initializing retention cleanup (keep last {retention_days} days)"
        )
        logger.info(f"🗓️  Cutoff date: {self.cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")

    def cleanup_transcript_files(self) -> Tuple[int, int]:
        """Remove transcript files older than retention period"""
        removed_count = 0
        total_size = 0

        transcript_dirs = [Path("transcripts"), Path("transcripts/digested")]

        for transcript_dir in transcript_dirs:
            if not transcript_dir.exists():
                continue

            logger.info(f"🔍 Checking {transcript_dir} for old files...")

            for transcript_file in transcript_dir.glob("*.txt"):
                try:
                    file_stat = transcript_file.stat()
                    file_age = file_stat.st_mtime

                    if file_age < self.cutoff_timestamp:
                        file_size = file_stat.st_size
                        total_size += file_size

                        logger.info(
                            f"  🗑️  Removing old transcript: {transcript_file.name} ({file_size:,} bytes)"
                        )
                        transcript_file.unlink()
                        removed_count += 1

                except Exception as e:
                    logger.warning(
                        f"  ⚠️  Could not process {transcript_file.name}: {e}"
                    )

        logger.info(
            f"✅ Removed {removed_count} transcript files ({total_size:,} bytes freed)"
        )
        return removed_count, total_size

    def cleanup_digest_files(self) -> Tuple[int, int]:
        """Remove old digest files but keep recent ones"""
        removed_count = 0
        total_size = 0

        digest_dir = Path("daily_digests")
        if not digest_dir.exists():
            logger.info("📁 No daily_digests directory found")
            return 0, 0

        logger.info(f"🔍 Checking {digest_dir} for old digest files...")

        # Remove old digest files (but keep MP3s for longer)
        old_extensions = [".md", ".txt"]  # Keep .mp3 and .json longer

        for ext in old_extensions:
            for digest_file in digest_dir.glob(f"*{ext}"):
                try:
                    file_stat = digest_file.stat()
                    file_age = file_stat.st_mtime

                    if file_age < self.cutoff_timestamp:
                        file_size = file_stat.st_size
                        total_size += file_size

                        logger.info(
                            f"  🗑️  Removing old digest file: {digest_file.name} ({file_size:,} bytes)"
                        )
                        digest_file.unlink()
                        removed_count += 1

                except Exception as e:
                    logger.warning(f"  ⚠️  Could not process {digest_file.name}: {e}")

        logger.info(
            f"✅ Removed {removed_count} digest files ({total_size:,} bytes freed)"
        )
        return removed_count, total_size

    def cleanup_database_heavy_fields(self, db_path: str) -> Tuple[int, int]:
        """Clean heavy database fields for old episodes while keeping metadata"""
        updated_count = 0
        bytes_freed = 0

        if not Path(db_path).exists():
            logger.warning(f"⚠️  Database not found: {db_path}")
            return 0, 0

        logger.info(f"🗄️  Cleaning heavy fields in {db_path}")

        try:
            conn = get_connection(db_path)
            cursor = conn.cursor()

            # Find episodes older than retention period with heavy fields
            cutoff_timestamp_str = self.cutoff_date.isoformat()

            cursor.execute(
                """
                SELECT episode_id,
                       LENGTH(COALESCE(topic_relevance_json, '')) as json_size,
                       LENGTH(COALESCE(failure_reason, '')) as failure_size
                FROM episodes
                WHERE (created_at < ? OR published_date < ?)
                AND status = 'digested'
                AND (topic_relevance_json IS NOT NULL OR failure_reason IS NOT NULL)
            """,
                (cutoff_timestamp_str, cutoff_timestamp_str),
            )

            old_episodes = cursor.fetchall()

            if old_episodes:
                # Calculate bytes that will be freed
                for episode_id, json_size, failure_size in old_episodes:
                    bytes_freed += json_size + failure_size

                # NULL out heavy fields for old episodes
                cursor.execute(
                    """
                    UPDATE episodes
                    SET topic_relevance_json = NULL,
                        failure_reason = NULL
                    WHERE (created_at < ? OR published_date < ?)
                    AND status = 'digested'
                    AND (topic_relevance_json IS NOT NULL OR failure_reason IS NOT NULL)
                """,
                    (cutoff_timestamp_str, cutoff_timestamp_str),
                )

                updated_count = cursor.rowcount
                conn.commit()

                logger.info(
                    f"  🗄️  Cleaned heavy fields from {updated_count} episodes ({bytes_freed:,} chars freed)"
                )
            else:
                logger.info("  ✅ No old episodes with heavy fields found")

            conn.close()

        except Exception as e:
            logger.error(f"❌ Error cleaning database {db_path}: {e}")
            return 0, 0

        return updated_count, bytes_freed

    def vacuum_databases(self, db_paths: List[str]) -> bool:
        """Run VACUUM on databases to reclaim space"""
        success = True

        for db_path in db_paths:
            if not Path(db_path).exists():
                continue

            logger.info(f"🧹 Running VACUUM on {db_path}")

            try:
                conn = get_connection(db_path)

                # Check database size before vacuum
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();"
                )
                size_before = cursor.fetchone()[0]

                # Run vacuum
                conn.execute("VACUUM;")

                # Check size after vacuum
                cursor.execute(
                    "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();"
                )
                size_after = cursor.fetchone()[0]

                bytes_freed = size_before - size_after
                logger.info(f"  ✅ VACUUM completed: {bytes_freed:,} bytes freed")

                conn.close()

            except Exception as e:
                logger.error(f"❌ Error running VACUUM on {db_path}: {e}")
                success = False

        return success

    def run_full_cleanup(self) -> dict:
        """Run complete retention cleanup process"""
        logger.info("🚀 Starting 14-day retention cleanup process")

        results = {
            "transcript_files_removed": 0,
            "transcript_bytes_freed": 0,
            "digest_files_removed": 0,
            "digest_bytes_freed": 0,
            "rss_episodes_cleaned": 0,
            "rss_bytes_freed": 0,
            "youtube_episodes_cleaned": 0,
            "youtube_bytes_freed": 0,
            "vacuum_success": False,
        }

        # 1. Clean transcript files
        files_removed, bytes_freed = self.cleanup_transcript_files()
        results["transcript_files_removed"] = files_removed
        results["transcript_bytes_freed"] = bytes_freed

        # 2. Clean digest files
        files_removed, bytes_freed = self.cleanup_digest_files()
        results["digest_files_removed"] = files_removed
        results["digest_bytes_freed"] = bytes_freed

        # 3. Clean RSS database heavy fields
        episodes_cleaned, bytes_freed = self.cleanup_database_heavy_fields(
            "podcast_monitor.db"
        )
        results["rss_episodes_cleaned"] = episodes_cleaned
        results["rss_bytes_freed"] = bytes_freed

        # 4. Clean YouTube database heavy fields
        episodes_cleaned, bytes_freed = self.cleanup_database_heavy_fields(
            "youtube_transcripts.db"
        )
        results["youtube_episodes_cleaned"] = episodes_cleaned
        results["youtube_bytes_freed"] = bytes_freed

        # 5. Vacuum databases to reclaim space
        vacuum_success = self.vacuum_databases(
            ["podcast_monitor.db", "youtube_transcripts.db"]
        )
        results["vacuum_success"] = vacuum_success

        # Summary
        total_files = (
            results["transcript_files_removed"] + results["digest_files_removed"]
        )
        total_bytes = (
            results["transcript_bytes_freed"]
            + results["digest_bytes_freed"]
            + results["rss_bytes_freed"]
            + results["youtube_bytes_freed"]
        )
        total_episodes = (
            results["rss_episodes_cleaned"] + results["youtube_episodes_cleaned"]
        )

        logger.info("📊 Retention cleanup summary:")
        logger.info(f"  📁 Files removed: {total_files}")
        logger.info(f"  💾 Bytes freed: {total_bytes:,}")
        logger.info(f"  🗄️  Episodes cleaned: {total_episodes}")
        logger.info(
            f"  🧹 Database vacuum: {'✅ Success' if vacuum_success else '❌ Failed'}"
        )

        return results


def main():
    """Run retention cleanup"""
    import argparse

    parser = argparse.ArgumentParser(description="Run 14-day retention cleanup")
    parser.add_argument(
        "--days", type=int, default=14, help="Retention period in days (default: 14)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned without actually doing it",
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("🧪 DRY RUN MODE - No files will actually be removed")
        # TODO: Implement dry run mode
        return 0

    cleanup = RetentionCleanup(retention_days=args.days)
    results = cleanup.run_full_cleanup()

    total_files = results["transcript_files_removed"] + results["digest_files_removed"]
    if (
        total_files > 0
        or results["rss_episodes_cleaned"] > 0
        or results["youtube_episodes_cleaned"] > 0
    ):
        print(
            f"🗑️  Retention cleanup completed: {total_files} files removed, {results['rss_episodes_cleaned'] + results['youtube_episodes_cleaned']} episodes cleaned"
        )
        return 0
    else:
        print("✅ No cleanup needed - all files within retention period")
        return 0


if __name__ == "__main__":
    exit(main())
