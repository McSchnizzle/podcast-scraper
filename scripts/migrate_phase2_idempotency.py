#!/usr/bin/env python3
"""
Phase 2 Database Migration - Add Idempotency Tables
Creates tables for storing OpenAI API results with proper constraints
"""

import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from utils.datetime_utils import now_utc
from utils.db import get_connection

# Add parent directory to path for config import
sys.path.append(str(Path(__file__).parent.parent))
from config import config

logger = logging.getLogger(__name__)

# Migration SQL for both databases
MIGRATION_SQL = """
-- Episode summaries table with idempotency
CREATE TABLE IF NOT EXISTS episode_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    summary TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    model TEXT NOT NULL,
    run_id TEXT,
    idempotency_key TEXT NOT NULL,
    request_headers TEXT,  -- JSON
    response_data TEXT,    -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(episode_id, chunk_index, prompt_version, model)
);

-- Digest operations table with idempotency
CREATE TABLE IF NOT EXISTS digest_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    digest_content TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    model TEXT NOT NULL,
    run_id TEXT,
    idempotency_key TEXT NOT NULL,
    request_headers TEXT,  -- JSON
    response_data TEXT,    -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(episode_id, topic, prompt_version, model)
);

-- Validation operations table with idempotency
CREATE TABLE IF NOT EXISTS validation_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash TEXT NOT NULL,  -- Hash of input content
    is_valid BOOLEAN NOT NULL,
    error_codes TEXT,  -- JSON array
    corrected_text TEXT,
    reasoning TEXT,
    prompt_version TEXT NOT NULL,
    model TEXT NOT NULL,
    run_id TEXT,
    idempotency_key TEXT NOT NULL,
    request_headers TEXT,  -- JSON
    response_data TEXT,    -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_hash, prompt_version, model)
);

-- Run headers table for observability
CREATE TABLE IF NOT EXISTS run_headers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    component TEXT NOT NULL,
    model TEXT NOT NULL,
    request_tokens INTEGER,
    response_tokens INTEGER,
    total_tokens INTEGER,
    duration_ms INTEGER,
    status TEXT NOT NULL,  -- 'success', 'error', 'timeout'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API call logs for debugging and monitoring
CREATE TABLE IF NOT EXISTS api_call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    component TEXT NOT NULL,
    model TEXT NOT NULL,
    idempotency_key TEXT,
    request_size INTEGER,
    response_size INTEGER,
    duration_ms INTEGER,
    retry_count INTEGER DEFAULT 0,
    final_status TEXT,  -- 'success', 'error', 'timeout'
    error_details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES run_headers(run_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_episode_summaries_episode ON episode_summaries(episode_id);
CREATE INDEX IF NOT EXISTS idx_episode_summaries_model ON episode_summaries(model);
CREATE INDEX IF NOT EXISTS idx_episode_summaries_idempotency ON episode_summaries(idempotency_key);

CREATE INDEX IF NOT EXISTS idx_digest_operations_episode ON digest_operations(episode_id);
CREATE INDEX IF NOT EXISTS idx_digest_operations_topic ON digest_operations(topic);
CREATE INDEX IF NOT EXISTS idx_digest_operations_model ON digest_operations(model);
CREATE INDEX IF NOT EXISTS idx_digest_operations_idempotency ON digest_operations(idempotency_key);

CREATE INDEX IF NOT EXISTS idx_validation_operations_hash ON validation_operations(content_hash);
CREATE INDEX IF NOT EXISTS idx_validation_operations_model ON validation_operations(model);
CREATE INDEX IF NOT EXISTS idx_validation_operations_idempotency ON validation_operations(idempotency_key);

CREATE INDEX IF NOT EXISTS idx_run_headers_component ON run_headers(component);
CREATE INDEX IF NOT EXISTS idx_run_headers_created ON run_headers(created_at);

CREATE INDEX IF NOT EXISTS idx_api_call_logs_run_id ON api_call_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_api_call_logs_component ON api_call_logs(component);
CREATE INDEX IF NOT EXISTS idx_api_call_logs_created ON api_call_logs(created_at);
"""


def migrate_database(db_path: str, db_name: str):
    """Migrate a single database with Phase 2 idempotency tables"""
    logger.info(f"🔄 Migrating {db_name} database: {db_path}")

    try:
        with get_connection(db_path) as conn:
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")

            # Execute migration SQL
            conn.executescript(MIGRATION_SQL)

            # Verify tables were created
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%summaries' OR name LIKE '%operations' OR name LIKE '%headers' OR name LIKE '%logs'"
            )
            new_tables = [row[0] for row in cursor.fetchall()]

            logger.info(
                f"✅ Created tables in {db_name}: {', '.join(sorted(new_tables))}"
            )

            # Show table counts
            for table in new_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                logger.info(f"   {table}: {count} rows")

    except Exception as e:
        logger.error(f"❌ Failed to migrate {db_name}: {e}")
        raise


def verify_migration(db_path: str, db_name: str):
    """Verify the migration was successful"""
    logger.info(f"🔍 Verifying {db_name} migration...")

    expected_tables = [
        "episode_summaries",
        "digest_operations",
        "validation_operations",
        "run_headers",
        "api_call_logs",
    ]

    expected_indexes = [
        "idx_episode_summaries_episode",
        "idx_episode_summaries_model",
        "idx_episode_summaries_idempotency",
        "idx_digest_operations_episode",
        "idx_digest_operations_topic",
        "idx_digest_operations_model",
        "idx_digest_operations_idempotency",
        "idx_validation_operations_hash",
        "idx_validation_operations_model",
        "idx_validation_operations_idempotency",
        "idx_run_headers_component",
        "idx_run_headers_created",
        "idx_api_call_logs_run_id",
        "idx_api_call_logs_component",
        "idx_api_call_logs_created",
    ]

    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()

            # Verify tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            actual_tables = [row[0] for row in cursor.fetchall()]

            missing_tables = [t for t in expected_tables if t not in actual_tables]
            if missing_tables:
                logger.error(f"❌ Missing tables in {db_name}: {missing_tables}")
                return False

            # Verify indexes
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            )
            actual_indexes = [row[0] for row in cursor.fetchall()]

            missing_indexes = [i for i in expected_indexes if i not in actual_indexes]
            if missing_indexes:
                logger.error(f"❌ Missing indexes in {db_name}: {missing_indexes}")
                return False

            # Test unique constraints by trying to insert duplicates
            test_episode_id = "test_episode_12345678"

            # Test episode_summaries unique constraint
            try:
                conn.execute(
                    """
                    INSERT INTO episode_summaries
                    (episode_id, chunk_index, char_start, char_end, summary, prompt_version, model, idempotency_key)
                    VALUES (?, 0, 0, 100, 'Test summary', 'v1.0', 'gpt-5-mini', 'test_key_1')
                """,
                    (test_episode_id,),
                )

                # This should fail due to unique constraint
                conn.execute(
                    """
                    INSERT INTO episode_summaries
                    (episode_id, chunk_index, char_start, char_end, summary, prompt_version, model, idempotency_key)
                    VALUES (?, 0, 100, 200, 'Different summary', 'v1.0', 'gpt-5-mini', 'test_key_2')
                """,
                    (test_episode_id,),
                )

                logger.error(
                    f"❌ Unique constraint not working in {db_name} episode_summaries"
                )
                return False

            except sqlite3.IntegrityError:
                logger.info(
                    f"✅ Unique constraint working in {db_name} episode_summaries"
                )

            # Clean up test data
            conn.execute(
                "DELETE FROM episode_summaries WHERE episode_id = ?", (test_episode_id,)
            )

            logger.info(f"✅ {db_name} migration verification passed")
            return True

    except Exception as e:
        logger.error(f"❌ Failed to verify {db_name}: {e}")
        return False


def main():
    """Run Phase 2 database migration"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    logger.info("🚀 Starting Phase 2 Database Migration")

    databases = [
        ("podcast_monitor.db", "RSS Episodes"),
        ("youtube_transcripts.db", "YouTube Episodes"),
    ]

    success = True

    for db_path, db_name in databases:
        if not Path(db_path).exists():
            logger.warning(f"⚠️  Database not found: {db_path}")
            continue

        try:
            # Create backup
            backup_path = f"{db_path}.backup.{now_utc().strftime('%Y%m%d_%H%M%S')}"
            import shutil

            shutil.copy2(db_path, backup_path)
            logger.info(f"📦 Created backup: {backup_path}")

            # Run migration
            migrate_database(db_path, db_name)

            # Verify migration
            if not verify_migration(db_path, db_name):
                success = False

        except Exception as e:
            logger.error(f"❌ Migration failed for {db_name}: {e}")
            success = False

    if success:
        logger.info("✅ Phase 2 database migration completed successfully")

        # Show summary
        logger.info("\n📊 Migration Summary:")
        logger.info("   - Added episode_summaries table with idempotency")
        logger.info("   - Added digest_operations table with idempotency")
        logger.info("   - Added validation_operations table with idempotency")
        logger.info("   - Added run_headers table for observability")
        logger.info("   - Added api_call_logs table for debugging")
        logger.info("   - Created performance indexes on all tables")
        logger.info("   - Verified unique constraints are working")

    else:
        logger.error("❌ Phase 2 database migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
