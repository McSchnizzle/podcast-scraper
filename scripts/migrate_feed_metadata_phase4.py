#!/usr/bin/env python3
"""
Phase 4 Database Migration: Feed Metadata and Item Tracking
Creates feed_metadata and item_seen tables for enhanced feed ingestion robustness
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logging_setup import configure_logging
from utils.datetime_utils import now_utc

configure_logging()
logger = logging.getLogger(__name__)

class FeedMetadataMigration:
    """Phase 4 migration for feed robustness features"""
    
    def __init__(self, db_path: str = "podcast_monitor.db"):
        self.db_path = db_path
        self.youtube_db_path = "youtube_transcripts.db"
    
    def run_migration(self, dry_run: bool = False) -> bool:
        """Run the complete migration for both databases"""
        logger.info("🚀 Starting Phase 4: Feed Metadata Migration")
        
        try:
            # Migrate main RSS database
            if self._migrate_database(self.db_path, dry_run):
                logger.info("✅ RSS database migration completed")
            else:
                logger.error("❌ RSS database migration failed")
                return False
            
            # Migrate YouTube database if it exists
            if Path(self.youtube_db_path).exists():
                if self._migrate_database(self.youtube_db_path, dry_run):
                    logger.info("✅ YouTube database migration completed")
                else:
                    logger.error("❌ YouTube database migration failed")
                    return False
            else:
                logger.info("ℹ️ YouTube database not found, skipping")
            
            if not dry_run:
                logger.info("✅ Phase 4 migration completed successfully")
            else:
                logger.info("🧪 Dry run completed - no changes made")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            return False
    
    def _migrate_database(self, db_path: str, dry_run: bool = False) -> bool:
        """Migrate a single database"""
        logger.info(f"📊 Migrating database: {db_path}")
        
        if not Path(db_path).exists():
            logger.error(f"Database not found: {db_path}")
            return False
        
        conn = sqlite3.connect(db_path)
        # Disable foreign key checking during migration
        conn.execute("PRAGMA foreign_keys = OFF")
        cursor = conn.cursor()
        
        try:
            # Check existing schema
            self._analyze_existing_schema(cursor, db_path)
            
            if dry_run:
                logger.info(f"🧪 Dry run: Would create tables in {db_path}")
                conn.close()
                return True
            
            # Create new tables
            self._create_feed_metadata_table(cursor)
            self._create_item_seen_table(cursor)
            
            # Populate feed_metadata with defaults for existing feeds
            self._populate_feed_metadata(cursor)
            
            # Create indexes
            self._create_indexes(cursor)
            
            # Verify migration
            self._verify_migration(cursor)
            
            conn.commit()
            logger.info(f"✅ Database {db_path} migrated successfully")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Error migrating {db_path}: {e}")
            return False
        finally:
            conn.close()
        
        return True
    
    def _analyze_existing_schema(self, cursor: sqlite3.Cursor, db_path: str):
        """Analyze existing database schema"""
        # Check feeds table
        cursor.execute("SELECT count(*) FROM feeds")
        feed_count = cursor.fetchone()[0]
        logger.info(f"📈 Found {feed_count} existing feeds in {db_path}")
        
        # Check if tables already exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('feed_metadata', 'item_seen')")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        if existing_tables:
            logger.info(f"ℹ️ Tables already exist: {existing_tables}")
            
            # Check feed_metadata population
            if 'feed_metadata' in existing_tables:
                cursor.execute("SELECT count(*) FROM feed_metadata")
                metadata_count = cursor.fetchone()[0]
                logger.info(f"📊 Existing feed_metadata records: {metadata_count}")
            
            # Check item_seen records
            if 'item_seen' in existing_tables:
                cursor.execute("SELECT count(*) FROM item_seen")
                seen_count = cursor.fetchone()[0]
                logger.info(f"📊 Existing item_seen records: {seen_count}")
    
    def _create_feed_metadata_table(self, cursor: sqlite3.Cursor):
        """Create feed_metadata table with enhanced features"""
        logger.info("🔧 Creating feed_metadata table")
        
        # Create without foreign key constraint since existing feeds table may not have proper primary key
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feed_metadata (
                feed_id INTEGER PRIMARY KEY,
                has_dates BOOLEAN DEFAULT 1,
                typical_order TEXT CHECK(typical_order IN ('reverse_chronological','chronological','unknown')) DEFAULT 'reverse_chronological',
                last_no_date_warning TIMESTAMP NULL,
                lookback_hours_override INTEGER NULL,
                etag TEXT NULL,
                last_modified_http TEXT NULL,
                notes TEXT NULL,
                created_at TIMESTAMP DEFAULT (datetime('now', 'UTC')),
                updated_at TIMESTAMP DEFAULT (datetime('now', 'UTC'))
            )
        ''')
        
        # Add trigger to update updated_at timestamp
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS feed_metadata_updated_at 
            AFTER UPDATE ON feed_metadata
            BEGIN
                UPDATE feed_metadata SET updated_at = datetime('now', 'UTC') WHERE feed_id = NEW.feed_id;
            END
        ''')
        
        logger.info("✅ feed_metadata table created")
    
    def _create_item_seen_table(self, cursor: sqlite3.Cursor):
        """Create item_seen table for deduplication and date-less handling"""
        logger.info("🔧 Creating item_seen table")
        
        # Create without foreign key constraint since existing feeds table may not have proper primary key
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS item_seen (
                feed_id INTEGER NOT NULL,
                item_id_hash TEXT NOT NULL,
                first_seen_utc TIMESTAMP NOT NULL,
                last_seen_utc TIMESTAMP NOT NULL,
                content_hash TEXT NULL,
                guid TEXT NULL,
                link TEXT NULL,
                title TEXT NULL,
                enclosure_url TEXT NULL,
                created_at TIMESTAMP DEFAULT (datetime('now', 'UTC')),
                PRIMARY KEY (feed_id, item_id_hash)
            )
        ''')
        
        logger.info("✅ item_seen table created")
    
    def _create_indexes(self, cursor: sqlite3.Cursor):
        """Create performance indexes"""
        logger.info("🔧 Creating indexes")
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_item_seen_feed_last_seen ON item_seen(feed_id, last_seen_utc)",
            "CREATE INDEX IF NOT EXISTS ix_item_seen_first_seen ON item_seen(first_seen_utc)",
            "CREATE INDEX IF NOT EXISTS ix_item_seen_content_hash ON item_seen(feed_id, content_hash)",
            "CREATE INDEX IF NOT EXISTS ix_feed_metadata_lookback ON feed_metadata(lookback_hours_override)",
            "CREATE INDEX IF NOT EXISTS ix_feed_metadata_etag ON feed_metadata(etag)",
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        logger.info("✅ Indexes created")
    
    def _populate_feed_metadata(self, cursor: sqlite3.Cursor):
        """Populate feed_metadata with defaults for existing feeds"""
        logger.info("📊 Populating feed_metadata with defaults")
        
        # Get all existing feeds
        cursor.execute("SELECT id, type FROM feeds")
        feeds = cursor.fetchall()
        
        populated_count = 0
        for feed_id, feed_type in feeds:
            # Check if metadata already exists
            cursor.execute("SELECT 1 FROM feed_metadata WHERE feed_id = ?", (feed_id,))
            if cursor.fetchone():
                continue
                
            # Insert default metadata
            cursor.execute('''
                INSERT INTO feed_metadata (
                    feed_id, 
                    has_dates, 
                    typical_order, 
                    notes
                ) VALUES (?, ?, ?, ?)
            ''', (
                feed_id, 
                True,  # Assume feeds have dates until proven otherwise
                'reverse_chronological',  # Most RSS feeds are reverse chronological
                f'Auto-created during Phase 4 migration for {feed_type} feed'
            ))
            populated_count += 1
        
        logger.info(f"✅ Populated {populated_count} feed_metadata records")
    
    def _verify_migration(self, cursor: sqlite3.Cursor):
        """Verify migration was successful"""
        logger.info("🔍 Verifying migration")
        
        # Check table creation
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('feed_metadata', 'item_seen')
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        if 'feed_metadata' not in tables:
            raise Exception("feed_metadata table was not created")
        if 'item_seen' not in tables:
            raise Exception("item_seen table was not created")
        
        # Check feed_metadata population
        cursor.execute("SELECT count(*) FROM feeds")
        feed_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT count(*) FROM feed_metadata")
        metadata_count = cursor.fetchone()[0]
        
        if feed_count > 0 and metadata_count == 0:
            raise Exception("feed_metadata was not populated")
        
        # Check constraints
        cursor.execute("PRAGMA table_info(feed_metadata)")
        columns = [row[1] for row in cursor.fetchall()]
        expected_columns = [
            'feed_id', 'has_dates', 'typical_order', 'last_no_date_warning',
            'lookback_hours_override', 'etag', 'last_modified_http', 'notes',
            'created_at', 'updated_at'
        ]
        
        for col in expected_columns:
            if col not in columns:
                raise Exception(f"Missing column in feed_metadata: {col}")
        
        # Check indexes
        cursor.execute("PRAGMA index_list(item_seen)")
        indexes = [row[1] for row in cursor.fetchall()]
        
        if 'ix_item_seen_feed_last_seen' not in indexes:
            logger.warning("⚠️ ix_item_seen_feed_last_seen index not found")
        
        logger.info("✅ Migration verification passed")
    
    def rollback_migration(self, db_path: str = None) -> bool:
        """Rollback migration (drop created tables)"""
        if db_path is None:
            db_path = self.db_path
            
        logger.warning(f"🔄 Rolling back migration for {db_path}")
        
        if not Path(db_path).exists():
            logger.error(f"Database not found: {db_path}")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Drop tables in reverse dependency order
            cursor.execute("DROP TABLE IF EXISTS item_seen")
            cursor.execute("DROP TABLE IF EXISTS feed_metadata")
            cursor.execute("DROP TRIGGER IF EXISTS feed_metadata_updated_at")
            
            conn.commit()
            logger.info("✅ Rollback completed")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Rollback failed: {e}")
            return False
        finally:
            conn.close()
        
        return True

def main():
    """CLI interface for Phase 4 migration"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 4: Feed Metadata Migration")
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')
    parser.add_argument('--db', default='podcast_monitor.db', help='Database path')
    
    args = parser.parse_args()
    
    migration = FeedMetadataMigration(args.db)
    
    if args.rollback:
        success = migration.rollback_migration(args.db)
    else:
        success = migration.run_migration(args.dry_run)
    
    if success:
        logger.info("🎉 Migration operation completed successfully")
        exit(0)
    else:
        logger.error("💥 Migration operation failed")
        exit(1)

if __name__ == "__main__":
    main()