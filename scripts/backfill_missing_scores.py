#!/usr/bin/env python3
"""
Backfill Missing Topic Scores
Self-healing script to calculate missing topic relevance scores for episodes
"""

import os
import logging
import sqlite3
import sys
from pathlib import Path
from utils.logging_setup import configure_logging

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the topic scorer
from openai_scorer import OpenAITopicScorer

configure_logging()
logger = logging.getLogger(__name__)

def main():
    """Main function to backfill missing topic scores"""
    logger.info("🔄 Starting backfill of missing topic scores")
    
    # Initialize scorer
    scorer = OpenAITopicScorer()
    
    if not scorer.api_available:
        logger.error("❌ OpenAI API not available - cannot score episodes")
        return
    
    total_scored = 0
    
    # Score RSS episodes (podcast_monitor.db)
    rss_db = "podcast_monitor.db"
    if Path(rss_db).exists():
        logger.info(f"📊 Processing RSS episodes in {rss_db}")
        scored = scorer.score_episodes_in_database(rss_db, status_filter='transcribed')
        total_scored += scored
        logger.info(f"✅ Scored {scored} RSS episodes")
    else:
        logger.warning(f"RSS database not found: {rss_db}")
    
    # Score YouTube episodes (youtube_transcripts.db) 
    youtube_db = "youtube_transcripts.db"
    if Path(youtube_db).exists():
        logger.info(f"📊 Processing YouTube episodes in {youtube_db}")
        scored = scorer.score_episodes_in_database(youtube_db, status_filter='transcribed')
        total_scored += scored
        logger.info(f"✅ Scored {scored} YouTube episodes")
    else:
        logger.warning(f"YouTube database not found: {youtube_db}")
    
    logger.info(f"🎯 Backfill complete - scored {total_scored} total episodes")
    
    # If no episodes were scored, check what's available
    if total_scored == 0:
        logger.info("📋 Checking episode status in both databases...")
        
        # Check RSS database
        if Path(rss_db).exists():
            conn = sqlite3.connect(rss_db)
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) FROM episodes GROUP BY status")
            rss_status = cursor.fetchall()
            conn.close()
            logger.info(f"RSS Episodes: {dict(rss_status)}")
        
        # Check YouTube database
        if Path(youtube_db).exists():
            conn = sqlite3.connect(youtube_db)
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) FROM episodes GROUP BY status")
            youtube_status = cursor.fetchall()
            conn.close()
            logger.info(f"YouTube Episodes: {dict(youtube_status)}")

if __name__ == "__main__":
    main()