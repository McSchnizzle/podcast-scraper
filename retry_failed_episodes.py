#!/usr/bin/env python3
"""
Retry Failed Episodes Script
Attempts to reprocess episodes that previously failed, now that issues are fixed
"""

import sqlite3
from pathlib import Path
from content_processor import ContentProcessor

def get_failed_episodes(db_path="podcast_monitor.db", limit=None):
    """Get episodes that failed and might be worth retrying"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get failed episodes, prioritizing those with fewer retries
        query = """
            SELECT episode_id, title, audio_url, failure_reason, retry_count
            FROM episodes 
            WHERE processed = -1
            AND (
                failure_reason LIKE '%API error%' OR 
                failure_reason LIKE '%timeout%' OR
                failure_reason LIKE '%connection%' OR
                retry_count < 3
            )
            ORDER BY retry_count ASC, published_date DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
            
        cursor.execute(query)
        episodes = cursor.fetchall()
        conn.close()
        
        return episodes
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return []

def retry_episode(processor, episode_id, title, audio_url, failure_reason, retry_count):
    """Retry processing a single failed episode"""
    print(f"\n🔄 Retrying: {title[:60]}...")
    print(f"   Previous failure: {failure_reason}")
    print(f"   Retry attempt: {retry_count + 1}")
    
    try:
        # Determine episode type and process accordingly
        if episode_id.startswith('yt:video:'):
            # YouTube episode
            transcript = processor._process_youtube_episode(audio_url, episode_id)
        else:
            # RSS episode  
            transcript = processor._process_rss_episode(audio_url, episode_id)
        
        if transcript:
            print(f"✅ Retry successful! Transcript length: {len(transcript):,} characters")
            
            # Update database to mark as processed
            conn = sqlite3.connect(processor.db_path)
            cursor = conn.cursor()
            
            # Save transcript to file
            transcripts_dir = Path("transcripts")
            transcripts_dir.mkdir(exist_ok=True)
            
            # Create transcript filename from episode hash
            episode_hash = episode_id.split('/')[-1] if '/' in episode_id else episode_id[:8]
            if episode_id.startswith('yt:video:'):
                episode_hash = episode_id.replace('yt:video:', '')[:8]
            transcript_filename = f"{episode_hash}.txt"
            transcript_path = transcripts_dir / transcript_filename
            
            # Write transcript to file
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(transcript)
            
            # Update episode as successfully processed
            cursor.execute("""
                UPDATE episodes 
                SET processed = 1,
                    transcript_path = ?,
                    failure_reason = NULL,
                    failure_timestamp = NULL
                WHERE episode_id = ?
            """, (str(transcript_path), episode_id))
            
            conn.commit()
            conn.close()
            
            print(f"📁 Transcript saved to: {transcript_path}")
            return True
        else:
            print(f"❌ Retry failed - no transcript generated")
            return False
            
    except Exception as e:
        print(f"❌ Retry failed with error: {e}")
        # The _log_episode_failure method will be called by the processor
        return False

def main():
    """Main retry function"""
    print("🔄 RETRYING FAILED EPISODES")
    print("=" * 60)
    
    # Get failed episodes to retry
    failed_episodes = get_failed_episodes(limit=10)  # Limit to 10 for testing
    
    if not failed_episodes:
        print("✅ No episodes need retrying!")
        return
    
    print(f"📋 Found {len(failed_episodes)} episodes to retry")
    
    # Initialize content processor
    processor = ContentProcessor(min_youtube_minutes=0.5)  # Lower threshold for YouTube videos
    
    success_count = 0
    total_count = len(failed_episodes)
    
    for episode_id, title, audio_url, failure_reason, retry_count in failed_episodes:
        success = retry_episode(processor, episode_id, title, audio_url, failure_reason, retry_count)
        if success:
            success_count += 1
    
    print("\n" + "=" * 60)
    print("🎉 RETRY SUMMARY")
    print("=" * 60)
    print(f"Total retried: {total_count}")
    print(f"Successful: {success_count}")
    print(f"Still failed: {total_count - success_count}")
    print(f"Success rate: {(success_count/total_count)*100:.1f}%")

if __name__ == "__main__":
    main()