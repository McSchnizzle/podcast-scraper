#!/usr/bin/env python3
"""
Phase 4 Schema Integrity Migration Script

Implements Option A: Fix episode_failures FK to reference episodes.id (INTEGER PRIMARY KEY)
- Idempotent and transactional migration
- Handles both podcast_monitor.db and youtube_transcripts.db
- Adds missing indexes and unique constraints
- Bumps schema version for tracking
"""

import sqlite3
import shutil
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Add utils to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from utils.datetime_utils import now_utc

# Schema version after this migration
TARGET_SCHEMA_VERSION = 2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Phase4SchemaMigrator:
    """
    Handles the complete schema integrity migration for Phase 4.
    
    Key changes:
    1. Fix episode_failures FK: episode_id (TEXT) → episode_pk (INTEGER) references episodes.id
    2. Add missing indexes on all FK columns
    3. Add unique constraints for deduplication
    4. Ensure proper CASCADE behaviors
    5. Bump schema version for tracking
    """
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.backup_path = None
        
    def migrate(self, dry_run: bool = False) -> bool:
        """
        Execute the complete migration.
        
        Args:
            dry_run: If True, only validate and log changes without applying
            
        Returns:
            True if migration successful, False otherwise
        """
        try:
            logger.info(f"=== Starting Phase 4 Schema Migration ===")
            logger.info(f"Database: {self.db_path}")
            logger.info(f"Dry run: {dry_run}")
            
            # Step 1: Backup
            if not dry_run:
                self._create_backup()
            
            # Step 2: Pre-migration validation and data quality checks
            self._validate_preconditions()
            
            # Step 3: Check if migration is needed
            if self._is_migration_complete():
                logger.info("Migration already complete - schema version is up to date")
                return True
            
            # Step 4: Execute migration
            if not dry_run:
                success = self._execute_migration()
                if success:
                    logger.info("✅ Migration completed successfully")
                    return True
                else:
                    logger.error("❌ Migration failed")
                    return False
            else:
                logger.info("Dry run completed - would apply migration")
                return True
                
        except Exception as e:
            logger.error(f"Migration failed with exception: {e}")
            if not dry_run and self.backup_path:
                logger.info(f"Restore from backup: cp {self.backup_path} {self.db_path}")
            return False
    
    def _create_backup(self) -> None:
        """Create timestamped backup of database file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path = self.db_path.parent / f"{self.db_path.stem}.backup_pre_migration_{timestamp}"
        
        shutil.copy2(self.db_path, self.backup_path)
        logger.info(f"Backup created: {self.backup_path}")
    
    def _validate_preconditions(self) -> None:
        """Validate database state and data quality before migration"""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if required tables exist
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('episodes', 'episode_failures', 'feeds')
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['episodes', 'feeds']
            missing_tables = [t for t in required_tables if t not in tables]
            if missing_tables:
                raise RuntimeError(f"Required tables missing: {missing_tables}")
            
            # Data quality checks
            self._check_data_quality(cursor)
            
            logger.info("✅ Pre-migration validation passed")
    
    def _check_data_quality(self, cursor: sqlite3.Cursor) -> None:
        """Check for data quality issues that could break migration"""
        
        issues = []
        
        # Check for NULL episode IDs in episodes table
        cursor.execute("SELECT COUNT(*) FROM episodes WHERE episode_id IS NULL OR episode_id = ''")
        null_episodes = cursor.fetchone()[0]
        if null_episodes > 0:
            issues.append(f"{null_episodes} episodes have NULL/empty episode_id")
        
        # Check for duplicate episode_id values
        cursor.execute("""
            SELECT episode_id, COUNT(*) 
            FROM episodes 
            WHERE episode_id IS NOT NULL 
            GROUP BY episode_id 
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        if duplicates:
            issues.append(f"{len(duplicates)} duplicate episode_id values found")
        
        # Check episode_failures table if it exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episode_failures'")
        if cursor.fetchone():
            # Check orphaned episode_failures
            cursor.execute("""
                SELECT COUNT(*) 
                FROM episode_failures ef 
                WHERE NOT EXISTS (
                    SELECT 1 FROM episodes e WHERE e.episode_id = ef.episode_id
                )
            """)
            orphaned = cursor.fetchone()[0]
            if orphaned > 0:
                issues.append(f"{orphaned} orphaned episode_failures records")
        
        # Log data quality report
        logger.info(f"Data quality check:")
        cursor.execute("SELECT COUNT(*) FROM episodes")
        episode_count = cursor.fetchone()[0]
        logger.info(f"  Episodes: {episode_count}")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episode_failures'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM episode_failures")
            failure_count = cursor.fetchone()[0]
            logger.info(f"  Episode failures: {failure_count}")
        
        if issues:
            logger.warning("Data quality issues found:")
            for issue in issues:
                logger.warning(f"  - {issue}")
            
            # For now, proceed with migration but log issues
            # In production, you might want to fix these first
            logger.warning("Proceeding with migration despite data quality issues")
        else:
            logger.info("  No data quality issues found")
    
    def _is_migration_complete(self) -> bool:
        """Check if migration has already been applied"""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check schema version
            cursor.execute("PRAGMA user_version")
            current_version = cursor.fetchone()[0]
            
            if current_version >= TARGET_SCHEMA_VERSION:
                return True
            
            # Check if episode_failures has been migrated (episode_pk column exists)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episode_failures'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(episode_failures)")
                columns = [row[1] for row in cursor.fetchall()]
                
                if 'episode_pk' in columns and 'episode_id' not in columns:
                    # Migration already applied but version not updated
                    logger.info("Migration appears complete but schema version not updated")
                    cursor.execute(f"PRAGMA user_version = {TARGET_SCHEMA_VERSION}")
                    conn.commit()
                    return True
            
            return False
    
    def _execute_migration(self) -> bool:
        """Execute the actual migration in a transaction"""
        
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.cursor()
                
                # Start transaction
                cursor.execute("BEGIN TRANSACTION")
                
                # Temporarily disable foreign keys for table rebuilds
                cursor.execute("PRAGMA foreign_keys = OFF")
                
                logger.info("Starting schema migration...")
                
                # Step 1: Migrate episode_failures table if it exists
                self._migrate_episode_failures(cursor)
                
                # Step 2: Add missing indexes
                self._add_missing_indexes(cursor)
                
                # Step 3: Add unique constraints for deduplication
                self._add_unique_constraints(cursor)
                
                # Step 4: Re-enable foreign keys and validate
                cursor.execute("PRAGMA foreign_keys = ON")
                
                # Step 5: Validate foreign key integrity
                cursor.execute("PRAGMA foreign_key_check")
                violations = cursor.fetchall()
                if violations:
                    raise RuntimeError(f"Foreign key violations after migration: {violations}")
                
                # Step 6: Update schema version
                cursor.execute(f"PRAGMA user_version = {TARGET_SCHEMA_VERSION}")
                
                # Commit transaction
                conn.commit()
                
                logger.info("Migration transaction committed successfully")
                return True
                
            except Exception as e:
                logger.error(f"Migration failed, rolling back: {e}")
                conn.rollback()
                return False
    
    def _migrate_episode_failures(self, cursor: sqlite3.Cursor) -> None:
        """Migrate episode_failures table to use INTEGER FK"""
        
        # Check if episode_failures table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episode_failures'")
        if not cursor.fetchone():
            logger.info("episode_failures table doesn't exist, skipping migration")
            return
        
        logger.info("Migrating episode_failures table...")
        
        # Check if already migrated (has episode_pk column)
        cursor.execute("PRAGMA table_info(episode_failures)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'episode_pk' in columns:
            logger.info("episode_failures already has episode_pk column, skipping")
            return
        
        # Step 1: Create new table with correct schema
        cursor.execute("""
            CREATE TABLE episode_failures_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_pk INTEGER NOT NULL,
                failure_reason TEXT NOT NULL,
                failure_category TEXT NOT NULL,
                traceback_info TEXT,
                failure_timestamp TIMESTAMP NOT NULL,
                resolved BOOLEAN DEFAULT 0,
                resolution_notes TEXT,
                FOREIGN KEY (episode_pk) REFERENCES episodes (id) ON DELETE CASCADE
            )
        """)
        
        # Step 2: Migrate data with episode_id → episode_pk mapping
        cursor.execute("""
            INSERT INTO episode_failures_new (
                id, episode_pk, failure_reason, failure_category, 
                traceback_info, failure_timestamp, resolved, resolution_notes
            )
            SELECT 
                ef.id,
                e.id as episode_pk,  -- Map TEXT episode_id to INTEGER id
                ef.failure_reason,
                ef.failure_category,
                ef.traceback_info,
                ef.failure_timestamp,
                ef.resolved,
                ef.resolution_notes
            FROM episode_failures ef
            INNER JOIN episodes e ON e.episode_id = ef.episode_id
        """)
        
        # Log how many records were migrated vs dropped
        old_count = cursor.execute("SELECT COUNT(*) FROM episode_failures").fetchone()[0]
        new_count = cursor.execute("SELECT COUNT(*) FROM episode_failures_new").fetchone()[0]
        dropped = old_count - new_count
        
        if dropped > 0:
            logger.warning(f"Dropped {dropped} orphaned episode_failures records during migration")
        
        logger.info(f"Migrated {new_count} episode_failures records")
        
        # Step 3: Replace old table
        cursor.execute("DROP TABLE episode_failures")
        cursor.execute("ALTER TABLE episode_failures_new RENAME TO episode_failures")
        
        # Step 4: Add indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_episode_failures_episode_pk 
            ON episode_failures(episode_pk)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_episode_failures_category 
            ON episode_failures(failure_category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_episode_failures_timestamp 
            ON episode_failures(failure_timestamp)
        """)
        
        logger.info("✅ episode_failures migration complete")
    
    def _add_missing_indexes(self, cursor: sqlite3.Cursor) -> None:
        """Add missing indexes for performance"""
        
        logger.info("Adding missing indexes...")
        
        indexes_to_create = [
            # Ensure all FK columns are indexed
            ("idx_episodes_feed_id", "episodes", "feed_id"),
            ("idx_feed_metadata_feed_id", "feed_metadata", "feed_id"),  # If table exists
            ("idx_item_seen_feed_id", "item_seen", "feed_id"),  # If table exists
            ("idx_item_seen_first_seen", "item_seen", "first_seen_utc"),  # For retention cleanup
            
            # Performance indexes for common queries
            ("idx_episodes_status", "episodes", "status"),
            ("idx_episodes_episode_type", "episodes", "episode_type"),
            ("idx_episodes_published_date", "episodes", "published_date"),
        ]
        
        for index_name, table_name, column_name in indexes_to_create:
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                continue
            
            # Check if column exists
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            if column_name not in columns:
                continue
            
            # Create index if not exists
            try:
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS {index_name} 
                    ON {table_name}({column_name})
                """)
                logger.info(f"  Created index: {index_name}")
            except sqlite3.Error as e:
                logger.warning(f"  Failed to create index {index_name}: {e}")
        
        logger.info("✅ Index creation complete")
    
    def _add_unique_constraints(self, cursor: sqlite3.Cursor) -> None:
        """Add unique constraints for deduplication"""
        
        logger.info("Adding unique constraints...")
        
        # Add UNIQUE(episode_id) to episodes table temporarily (tech debt)
        # This allows existing code to still work during transition
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episodes'")
        if cursor.fetchone():
            try:
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_episodes_episode_id ON episodes(episode_id)")
                logger.info("  Added unique constraint: episodes.episode_id")
            except sqlite3.Error as e:
                logger.warning(f"  Failed to create unique constraint on episodes.episode_id: {e}")
        
        # Add unique constraint to item_seen for deduplication if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='item_seen'")
        if cursor.fetchone():
            # Check what columns exist for deduplication
            cursor.execute("PRAGMA table_info(item_seen)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Try different deduplication strategies based on available columns
            if 'item_id_hash' in columns:
                try:
                    cursor.execute("""
                        CREATE UNIQUE INDEX IF NOT EXISTS ux_item_seen_feed_hash 
                        ON item_seen(feed_id, item_id_hash)
                    """)
                    logger.info("  Added unique constraint: item_seen(feed_id, item_id_hash)")
                except sqlite3.Error as e:
                    logger.warning(f"  Failed to create unique constraint on item_seen: {e}")
        
        logger.info("✅ Unique constraints complete")

def main():
    """Main entry point for migration script"""
    
    if len(sys.argv) < 2:
        print("Usage: python migrate_phase4_schema_integrity.py <database_path> [--dry-run]")
        print("       python migrate_phase4_schema_integrity.py --all [--dry-run]")
        sys.exit(1)
    
    dry_run = '--dry-run' in sys.argv
    
    if '--all' in sys.argv:
        # Migrate both databases
        databases = ['podcast_monitor.db', 'youtube_transcripts.db']
    else:
        databases = [sys.argv[1]]
    
    success_count = 0
    
    for db_path in databases:
        if not Path(db_path).exists():
            logger.warning(f"Database not found: {db_path}, skipping")
            continue
        
        logger.info(f"\n{'='*60}")
        migrator = Phase4SchemaMigrator(db_path)
        
        if migrator.migrate(dry_run=dry_run):
            success_count += 1
            logger.info(f"✅ Migration successful: {db_path}")
        else:
            logger.error(f"❌ Migration failed: {db_path}")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Migration summary: {success_count}/{len(databases)} databases migrated successfully")
    
    if success_count == len(databases):
        logger.info("🎉 All migrations completed successfully!")
        sys.exit(0)
    else:
        logger.error("Some migrations failed. Check logs above.")
        sys.exit(1)

if __name__ == "__main__":
    main()