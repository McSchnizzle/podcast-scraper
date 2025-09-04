#!/usr/bin/env python3
"""
Database Bootstrap Script for Multi-Topic Podcast Digest System
Initializes both RSS (podcast_monitor.db) and YouTube (youtube_transcripts.db) databases
"""

import os
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
import logging
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseBootstrap:
    def __init__(self):
        self.config = Config(require_claude=False)
        self.rss_db_path = "podcast_monitor.db"
        self.youtube_db_path = "youtube_transcripts.db"
        
    def bootstrap_rss_database(self) -> bool:
        """Initialize RSS database with complete schema"""
        logger.info(f"🚀 Bootstrapping RSS database: {self.rss_db_path}")
        
        try:
            conn = sqlite3.connect(self.rss_db_path)
            cursor = conn.cursor()
            
            # Create feeds table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feeds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    type TEXT NOT NULL, -- 'rss' or 'youtube'
                    topic_category TEXT NOT NULL,
                    active INTEGER DEFAULT 1,
                    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create episodes table  
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feed_id INTEGER,
                    episode_id TEXT UNIQUE, -- RSS guid or YouTube video ID
                    title TEXT NOT NULL,
                    published_date TIMESTAMP,
                    audio_url TEXT,
                    transcript_path TEXT,
                    status TEXT DEFAULT 'pre-download',
                    priority_score REAL DEFAULT 0.0,
                    content_type TEXT DEFAULT 'unknown', -- 'discussion', 'interview', 'news', etc.
                    duration_minutes INTEGER DEFAULT 0,
                    file_size_bytes INTEGER DEFAULT 0,
                    digest_date TIMESTAMP NULL, -- When episode was included in a digest
                    topic_scores TEXT NULL, -- JSON string of topic scores
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (feed_id) REFERENCES feeds (id) ON DELETE CASCADE
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_episode_id ON episodes (episode_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_published_date ON episodes (published_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_digest_date ON episodes (digest_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feeds_active ON feeds (active)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feeds_type ON feeds (type)')
            
            # Add database metadata
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS database_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                INSERT OR REPLACE INTO database_metadata (key, value) 
                VALUES ('schema_version', '1.0'), ('database_type', 'rss'), ('bootstrapped_at', ?)
            ''', (datetime.now().isoformat(),))
            
            conn.commit()
            
            # Get counts for reporting
            cursor.execute("SELECT COUNT(*) FROM feeds")
            feeds_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM episodes")
            episodes_count = cursor.fetchone()[0]
            
            conn.close()
            
            logger.info(f"✅ RSS database initialized: {feeds_count} feeds, {episodes_count} episodes")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to bootstrap RSS database: {e}")
            return False
    
    def bootstrap_youtube_database(self) -> bool:
        """Initialize YouTube database with complete schema"""
        logger.info(f"🚀 Bootstrapping YouTube database: {self.youtube_db_path}")
        
        try:
            conn = sqlite3.connect(self.youtube_db_path)
            cursor = conn.cursor()
            
            # Create feeds table - YouTube feeds only
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feeds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    type TEXT NOT NULL CHECK(type = 'youtube'),
                    topic_category TEXT NOT NULL,
                    active INTEGER DEFAULT 1,
                    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create episodes table - YouTube episodes only
            cursor.execute('''
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
                    content_type TEXT DEFAULT 'unknown',
                    duration_minutes INTEGER DEFAULT 0,
                    file_size_bytes INTEGER DEFAULT 0,
                    digest_date TIMESTAMP NULL,
                    topic_scores TEXT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (feed_id) REFERENCES feeds (id) ON DELETE CASCADE
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_episode_id ON episodes (episode_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_published_date ON episodes (published_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_digest_date ON episodes (digest_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feeds_active ON feeds (active)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feeds_type ON feeds (type)')
            
            # Add database metadata
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS database_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                INSERT OR REPLACE INTO database_metadata (key, value) 
                VALUES ('schema_version', '1.0'), ('database_type', 'youtube'), ('bootstrapped_at', ?)
            ''', (datetime.now().isoformat(),))
            
            conn.commit()
            
            # Get counts for reporting
            cursor.execute("SELECT COUNT(*) FROM feeds")
            feeds_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM episodes")
            episodes_count = cursor.fetchone()[0]
            
            conn.close()
            
            logger.info(f"✅ YouTube database initialized: {feeds_count} feeds, {episodes_count} episodes")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to bootstrap YouTube database: {e}")
            return False
    
    def seed_rss_feeds(self) -> bool:
        """Populate RSS database with initial feed configuration"""
        logger.info("🌱 Seeding RSS feeds from configuration...")
        
        try:
            # Get RSS feeds from config
            all_feeds = self.config.get_feed_config()
            rss_feeds = [feed for feed in all_feeds if feed['type'] == 'rss']
            
            if not rss_feeds:
                logger.info("No RSS feeds found in configuration")
                return True
            
            conn = sqlite3.connect(self.rss_db_path)
            cursor = conn.cursor()
            
            added_count = 0
            for feed in rss_feeds:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO feeds (url, title, type, topic_category, active)
                        VALUES (?, ?, ?, ?, 1)
                    ''', (feed['url'], feed['title'], feed['type'], feed['topic_category']))
                    
                    if cursor.rowcount > 0:
                        added_count += 1
                        logger.info(f"  ➕ Added RSS feed: {feed['title']}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Could not add RSS feed {feed['title']}: {e}")
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Seeded {added_count} RSS feeds")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to seed RSS feeds: {e}")
            return False
    
    def seed_youtube_feeds(self) -> bool:
        """Populate YouTube database with initial feed configuration"""
        logger.info("🌱 Seeding YouTube feeds from configuration...")
        
        try:
            # Get YouTube feeds from config
            all_feeds = self.config.get_feed_config()
            youtube_feeds = [feed for feed in all_feeds if feed['type'] == 'youtube']
            
            if not youtube_feeds:
                logger.info("No YouTube feeds found in configuration")
                return True
            
            conn = sqlite3.connect(self.youtube_db_path)
            cursor = conn.cursor()
            
            added_count = 0
            for feed in youtube_feeds:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO feeds (url, title, type, topic_category, active)
                        VALUES (?, ?, ?, ?, 1)
                    ''', (feed['url'], feed['title'], feed['type'], feed['topic_category']))
                    
                    if cursor.rowcount > 0:
                        added_count += 1
                        logger.info(f"  ➕ Added YouTube feed: {feed['title']}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Could not add YouTube feed {feed['title']}: {e}")
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Seeded {added_count} YouTube feeds")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to seed YouTube feeds: {e}")
            return False
    
    def verify_database_integrity(self, db_path: str) -> bool:
        """Verify database schema and integrity"""
        logger.info(f"🔍 Verifying database integrity: {db_path}")
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check required tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['feeds', 'episodes', 'database_metadata']
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                logger.error(f"❌ Missing required tables: {missing_tables}")
                conn.close()
                return False
            
            # Check feeds table structure
            cursor.execute("PRAGMA table_info(feeds)")
            feeds_columns = [col[1] for col in cursor.fetchall()]
            required_feeds_columns = ['id', 'url', 'title', 'type', 'topic_category', 'active']
            missing_feeds_columns = [col for col in required_feeds_columns if col not in feeds_columns]
            
            if missing_feeds_columns:
                logger.error(f"❌ Missing required feeds columns: {missing_feeds_columns}")
                conn.close()
                return False
            
            # Check episodes table structure
            cursor.execute("PRAGMA table_info(episodes)")
            episodes_columns = [col[1] for col in cursor.fetchall()]
            required_episodes_columns = ['id', 'episode_id', 'title', 'status', 'transcript_path']
            missing_episodes_columns = [col for col in required_episodes_columns if col not in episodes_columns]
            
            if missing_episodes_columns:
                logger.error(f"❌ Missing required episodes columns: {missing_episodes_columns}")
                conn.close()
                return False
            
            # Check database metadata
            cursor.execute("SELECT key, value FROM database_metadata")
            metadata = dict(cursor.fetchall())
            
            logger.info(f"📊 Database info: {metadata.get('database_type', 'unknown')} schema v{metadata.get('schema_version', 'unknown')}")
            logger.info(f"📊 Bootstrapped: {metadata.get('bootstrapped_at', 'unknown')}")
            
            # Get table counts
            cursor.execute("SELECT COUNT(*) FROM feeds")
            feeds_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM episodes")
            episodes_count = cursor.fetchone()[0]
            
            logger.info(f"📊 Table counts: {feeds_count} feeds, {episodes_count} episodes")
            
            conn.close()
            logger.info("✅ Database integrity verified")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database integrity check failed: {e}")
            return False
    
    def run_full_bootstrap(self, skip_existing: bool = True) -> bool:
        """Run complete bootstrap process for both databases"""
        logger.info("🚀 Starting full database bootstrap...")
        logger.info("=" * 60)
        
        success = True
        
        # Check if databases already exist
        rss_exists = Path(self.rss_db_path).exists()
        youtube_exists = Path(self.youtube_db_path).exists()
        
        if skip_existing and rss_exists and youtube_exists:
            logger.info("📋 Both databases already exist")
            logger.info(f"RSS database: {self.rss_db_path} (exists)")
            logger.info(f"YouTube database: {self.youtube_db_path} (exists)")
            
            # Verify existing databases
            rss_valid = self.verify_database_integrity(self.rss_db_path)
            youtube_valid = self.verify_database_integrity(self.youtube_db_path)
            
            if rss_valid and youtube_valid:
                logger.info("✅ Existing databases are valid - bootstrap not needed")
                return True
            else:
                logger.warning("⚠️ Existing databases have issues - continuing with bootstrap")
        
        # Bootstrap RSS database
        if not self.bootstrap_rss_database():
            success = False
        else:
            # Seed RSS feeds
            if not self.seed_rss_feeds():
                logger.warning("⚠️ RSS feed seeding failed")
        
        # Bootstrap YouTube database  
        if not self.bootstrap_youtube_database():
            success = False
        else:
            # Seed YouTube feeds
            if not self.seed_youtube_feeds():
                logger.warning("⚠️ YouTube feed seeding failed")
        
        # Final verification
        if success:
            logger.info("🔍 Running final verification...")
            rss_valid = self.verify_database_integrity(self.rss_db_path)
            youtube_valid = self.verify_database_integrity(self.youtube_db_path)
            
            if rss_valid and youtube_valid:
                logger.info("🎉 Full database bootstrap completed successfully!")
                logger.info("=" * 60)
                logger.info(f"✅ RSS Database: {self.rss_db_path}")
                logger.info(f"✅ YouTube Database: {self.youtube_db_path}")
                logger.info("🔄 Ready for podcast processing pipeline")
                return True
            else:
                logger.error("❌ Bootstrap completed but verification failed")
                return False
        else:
            logger.error("❌ Bootstrap failed")
            return False


def main():
    """Bootstrap database command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Bootstrap podcast scraper databases")
    parser.add_argument('--force', action='store_true', help='Force bootstrap even if databases exist')
    parser.add_argument('--verify-only', action='store_true', help='Only verify existing databases')
    parser.add_argument('--rss-only', action='store_true', help='Bootstrap RSS database only')
    parser.add_argument('--youtube-only', action='store_true', help='Bootstrap YouTube database only')
    
    args = parser.parse_args()
    
    bootstrap = DatabaseBootstrap()
    
    if args.verify_only:
        logger.info("🔍 Verification mode - checking existing databases")
        rss_valid = bootstrap.verify_database_integrity(bootstrap.rss_db_path)
        youtube_valid = bootstrap.verify_database_integrity(bootstrap.youtube_db_path)
        
        if rss_valid and youtube_valid:
            logger.info("✅ All databases verified successfully")
            return 0
        else:
            logger.error("❌ Database verification failed")
            return 1
    
    if args.rss_only:
        logger.info("🚀 RSS database bootstrap only")
        success = bootstrap.bootstrap_rss_database() and bootstrap.seed_rss_feeds()
        if success:
            success = bootstrap.verify_database_integrity(bootstrap.rss_db_path)
    elif args.youtube_only:
        logger.info("🚀 YouTube database bootstrap only")
        success = bootstrap.bootstrap_youtube_database() and bootstrap.seed_youtube_feeds()
        if success:
            success = bootstrap.verify_database_integrity(bootstrap.youtube_db_path)
    else:
        # Full bootstrap
        success = bootstrap.run_full_bootstrap(skip_existing=not args.force)
    
    if success:
        logger.info("🎉 Bootstrap completed successfully!")
        return 0
    else:
        logger.error("❌ Bootstrap failed")
        return 1


if __name__ == "__main__":
    exit(main())