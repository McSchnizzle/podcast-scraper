#!/usr/bin/env python3
"""
Re-score Existing Episodes with New Topic Structure
Updates all existing episodes with new 4-topic scoring
"""

import logging
import sqlite3
import sys
from pathlib import Path
from utils.logging_setup import configure_logging
from utils.db import get_connection

# Import the topic scorer
from openai_scorer import OpenAITopicScorer

configure_logging()
logger = logging.getLogger(__name__)

def rescore_database_episodes(db_path: str, scorer: OpenAITopicScorer) -> int:
    """Re-score all episodes in a database regardless of status"""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        
        # Get all episodes with transcripts
        cursor.execute("""
            SELECT episode_id, transcript_path 
            FROM episodes 
            WHERE transcript_path IS NOT NULL 
            AND transcript_path != ''
            AND (status = 'digested' OR status = 'transcribed')
        """)
        
        episodes = cursor.fetchall()
        logger.info(f"Found {len(episodes)} episodes to re-score in {db_path}")
        
        scored_count = 0
        for episode_id, transcript_path in episodes:
            # Check if transcript file exists
            if not Path(transcript_path).exists():
                logger.warning(f"Transcript not found for {episode_id}: {transcript_path}")
                continue
                
            # Read transcript
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    transcript_text = f.read().strip()
                    
                if not transcript_text:
                    logger.warning(f"Empty transcript for {episode_id}")
                    continue
                    
                # Score with new topics
                logger.info(f"Re-scoring episode {episode_id}...")
                scores = scorer.score_transcript(transcript_text, episode_id)
                
                if scores:
                    # The score_transcript method returns the scores directly, formatted for DB
                    scores_json = scorer._format_scores_for_db(scores)
                    
                    # Update database with new scores
                    cursor.execute("""
                        UPDATE episodes 
                        SET topic_relevance_json = ?
                        WHERE episode_id = ?
                    """, (scores_json, episode_id))
                    
                    scored_count += 1
                    logger.info(f"✅ Re-scored {episode_id} with new topics")
                else:
                    logger.warning(f"Failed to get scores for {episode_id}")
                    
            except Exception as e:
                logger.error(f"Error processing {episode_id}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Successfully re-scored {scored_count} episodes in {db_path}")
        return scored_count
        
    except Exception as e:
        logger.error(f"Error processing database {db_path}: {e}")
        return 0

def main():
    """Main function to re-score existing episodes"""
    logger.info("🔄 Starting re-scoring of existing episodes with new 4-topic structure")
    
    # Initialize scorer
    scorer = OpenAITopicScorer()
    
    if not scorer.api_available:
        logger.error("❌ OpenAI API not available - cannot score episodes")
        return
    
    total_scored = 0
    
    # Re-score RSS episodes
    rss_db = "podcast_monitor.db"
    if Path(rss_db).exists():
        logger.info(f"📊 Re-scoring RSS episodes in {rss_db}")
        scored = rescore_database_episodes(rss_db, scorer)
        total_scored += scored
    
    # Re-score YouTube episodes
    youtube_db = "youtube_transcripts.db"
    if Path(youtube_db).exists():
        logger.info(f"📊 Re-scoring YouTube episodes in {youtube_db}")
        scored = rescore_database_episodes(youtube_db, scorer)
        total_scored += scored
    
    logger.info(f"🎯 Re-scoring complete - updated {total_scored} total episodes with new 4-topic structure")
    
    # Show topic breakdown
    logger.info("📋 Checking updated episode scores...")
    for db_name in [rss_db, youtube_db]:
        if Path(db_name).exists():
            try:
                conn = get_connection(db_name)
                cursor = conn.cursor()
                cursor.execute("SELECT status, COUNT(*) FROM episodes GROUP BY status")
                results = cursor.fetchall()
                db_type = "RSS" if "podcast" in db_name else "YouTube"
                logger.info(f"{db_type} Episodes: {dict(results)}")
                conn.close()
            except Exception as e:
                logger.error(f"Error checking {db_name}: {e}")

if __name__ == "__main__":
    main()