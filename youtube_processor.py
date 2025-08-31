#!/usr/bin/env python3
"""
Local YouTube Processor - Handles YouTube feeds separately from GitHub Actions
Designed to run locally via cron/launchctl to avoid GitHub Actions IP blocking
"""

import os
import sqlite3
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
from config import Config
from content_processor import ContentProcessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class YouTubeProcessor:
    def __init__(self, youtube_db_path: str = "youtube_transcripts.db"):
        self.youtube_db_path = youtube_db_path
        self.config = Config()
        
        # Initialize YouTube-specific database
        self._init_youtube_database()
        
        # Content processor for transcription
        self.content_processor = ContentProcessor(
            db_path=youtube_db_path,  # Use YouTube-specific database
            audio_dir="audio_cache"
        )
    
    def _init_youtube_database(self):
        """Initialize YouTube-specific database with same schema"""
        conn = sqlite3.connect(self.youtube_db_path)
        cursor = conn.cursor()
        
        # Feeds table - YouTube feeds only
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                type TEXT NOT NULL CHECK(type = 'youtube'),
                topic_category TEXT NOT NULL,
                last_checked TIMESTAMP,
                active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Episodes table - YouTube episodes only
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
                content_type TEXT,
                failure_reason TEXT,
                failure_timestamp TIMESTAMP,
                retry_count INTEGER DEFAULT 0,
                FOREIGN KEY (feed_id) REFERENCES feeds (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"✅ YouTube database initialized: {self.youtube_db_path}")
    
    def sync_youtube_feeds(self):
        """Sync YouTube feeds from config to YouTube database"""
        conn = sqlite3.connect(self.youtube_db_path)
        cursor = conn.cursor()
        
        # Get YouTube feeds from config
        youtube_feeds = [feed for feed in self.config.get_feed_config() if feed['type'] == 'youtube']
        
        logger.info(f"Syncing {len(youtube_feeds)} YouTube feeds to database...")
        
        for feed in youtube_feeds:
            cursor.execute('''
                INSERT OR REPLACE INTO feeds (url, title, type, topic_category, active, last_checked)
                VALUES (?, ?, ?, ?, 1, datetime('now'))
            ''', (feed['url'], feed['title'], feed['type'], feed['topic_category']))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Synced {len(youtube_feeds)} YouTube feeds")
    
    def check_new_youtube_episodes(self, hours_back: int = 6) -> List[Dict]:
        """Check for new YouTube episodes (similar to feed_monitor but YouTube-only)"""
        from feed_monitor import FeedMonitor
        
        # Create temporary feed monitor with YouTube database
        feed_monitor = FeedMonitor(db_path=self.youtube_db_path)
        
        # Check for new episodes
        new_episodes = feed_monitor.check_new_episodes(hours_back=hours_back)
        
        logger.info(f"Found {len(new_episodes)} new YouTube episodes")
        return new_episodes
    
    def process_pending_youtube_episodes(self) -> int:
        """Process pending YouTube episodes using YouTube Transcript API (no download needed)"""
        conn = sqlite3.connect(self.youtube_db_path)
        cursor = conn.cursor()
        
        # Get pending YouTube episodes (only 'pre-download' status)
        cursor.execute('''
            SELECT id, title, audio_url, episode_id FROM episodes 
            WHERE status = 'pre-download' 
            AND audio_url IS NOT NULL
            ORDER BY published_date DESC
        ''')
        
        pending_episodes = cursor.fetchall()
        
        if not pending_episodes:
            logger.info("No pending YouTube episodes to process")
            conn.close()
            return 0
        
        logger.info(f"🎬 Processing {len(pending_episodes)} YouTube episodes with Transcript API...")
        
        processed_count = 0
        for episode_id, title, video_url, episode_guid in pending_episodes:
            try:
                logger.info(f"📺 Processing: {title}")
                
                # Use YouTube Transcript API directly (no video download)
                transcript = self.content_processor._process_youtube_episode(video_url, episode_guid)
                
                if transcript:
                    # Save transcript file
                    transcript_path = self.content_processor._save_transcript(episode_guid, transcript)
                    
                    # Update episode to 'transcribed' status (skip 'downloaded' for YouTube)
                    cursor.execute('''
                        UPDATE episodes 
                        SET transcript_path = ?, status = 'transcribed',
                            priority_score = 0.8, content_type = 'discussion'
                        WHERE id = ?
                    ''', (transcript_path, episode_id))
                    
                    processed_count += 1
                    logger.info(f"✅ Transcribed YouTube episode: {title}")
                    
                else:
                    # Mark as failed
                    cursor.execute('UPDATE episodes SET status = ? WHERE id = ?', ('failed', episode_id))
                    logger.warning(f"❌ Failed to get transcript: {title}")
                    
            except Exception as e:
                logger.error(f"Error processing YouTube episode {episode_id}: {e}")
                cursor.execute('UPDATE episodes SET status = ? WHERE id = ?', ('failed', episode_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ YouTube Transcript API: {processed_count}/{len(pending_episodes)} episodes transcribed")
        return processed_count
    
    def get_youtube_stats(self) -> Dict:
        """Get YouTube processing statistics"""
        conn = sqlite3.connect(self.youtube_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM episodes
            GROUP BY status
            ORDER BY count DESC
        ''')
        
        status_counts = dict(cursor.fetchall())
        
        cursor.execute('SELECT COUNT(*) FROM episodes')
        total_episodes = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM feeds WHERE active = 1')
        active_feeds = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'status_counts': status_counts,
            'total_episodes': total_episodes,
            'active_feeds': active_feeds
        }
    
    def cleanup_old_episodes(self, days_old: int = 7):
        """Clean up old failed/processed YouTube episodes"""
        conn = sqlite3.connect(self.youtube_db_path)
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        cursor.execute('''
            DELETE FROM episodes 
            WHERE status IN ('failed', 'digested') 
            AND (failure_timestamp < ? OR published_date < ?)
        ''', (cutoff_date.strftime('%Y-%m-%d'), cutoff_date.strftime('%Y-%m-%d')))
        
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
            result = subprocess.run(['git', 'pull', 'origin', 'main'], 
                                  capture_output=True, text=True, timeout=30)
            
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
    
    def run_youtube_workflow(self, hours_back: int = 6):
        """LOCAL ONLY: Download and transcribe YouTube episodes"""
        logger.info("🎬 Starting LOCAL YouTube Transcription Workflow") 
        logger.info("📝 LOCAL SCOPE: YouTube Transcript API → Mark 'transcribed' → Push to GitHub")
        logger.info("🚀 RESULT: GitHub repo will have YouTube transcripts ready for GitHub Actions")
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
            
            # Step 5: Cleanup only old failed episodes (keep transcribed for GitHub)
            self.cleanup_old_episodes()
            
            logger.info("✅ LOCAL YouTube transcription completed")
            logger.info(f"📤 NEXT: Push transcripts to GitHub repo for GitHub Actions")
            logger.info(f"🤖 GitHub Actions will find YouTube transcripts already in repo")
            return True
            
        except Exception as e:
            logger.error(f"❌ LOCAL YouTube workflow failed: {e}")
            return False

def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Local YouTube Processor")
    parser.add_argument('--process-new', action='store_true', 
                       help='Process new YouTube episodes')
    parser.add_argument('--hours-back', type=int, default=6,
                       help='Hours back to check for new episodes (default: 6)')
    parser.add_argument('--stats', action='store_true',
                       help='Show YouTube processing statistics')
    parser.add_argument('--cleanup', action='store_true',
                       help='Cleanup old episodes only')
    parser.add_argument('--sync-feeds', action='store_true',
                       help='Sync YouTube feeds from config')
    
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