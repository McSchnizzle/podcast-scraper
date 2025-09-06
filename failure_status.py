#!/usr/bin/env python3
"""
Standalone failure status checker
Shows failure statistics and retry candidates without dependencies
"""

import sqlite3
from pathlib import Path
from utils.episode_failures import FailureManager
from utils.db import get_connection

def show_failure_status():
    """Show comprehensive failure status for both databases"""
    print("\n📊 Failed Episode Lifecycle Management Status:")
    print("=" * 60)
    
    # Check both databases
    for db_name, db_path in [("RSS", "podcast_monitor.db"), ("YouTube", "youtube_transcripts.db")]:
        if not Path(db_path).exists():
            print(f"\n⚠️ {db_name} Database: Not found ({db_path})")
            continue
            
        try:
            # Get basic episode counts
            conn = get_connection(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM episodes
                GROUP BY status
                ORDER BY count DESC
            """)
            status_counts = dict(cursor.fetchall())
            
            cursor.execute("SELECT COUNT(*) FROM episodes")
            total_episodes = cursor.fetchone()[0]
            
            conn.close()
            
            # Get failure statistics
            failure_manager = FailureManager(db_path)
            failure_stats = failure_manager.get_failure_statistics(days_back=7)
            retry_candidates = failure_manager.get_retry_candidates()
            
            print(f"\n📊 {db_name} Database:")
            print(f"  Episodes by status: {status_counts}")
            print(f"  Total episodes: {total_episodes}")
            print(f"  Episodes eligible for retry: {len(retry_candidates)}")
            
            # Show failure statistics if available
            if failure_stats.get('total_failed_episodes', 0) > 0:
                print(f"  Failed episodes (last 7 days): {failure_stats['total_failed_episodes']}")
                
                # Show top failure reasons
                top_failures = list(failure_stats.get('failure_reasons', {}).items())[:3]
                if top_failures:
                    print("  Top failure reasons:")
                    for reason, count in top_failures:
                        print(f"    - {reason}: {count}")
                
                # Show retry distribution
                if failure_stats.get('retry_distribution'):
                    print(f"  Retry attempts distribution: {failure_stats['retry_distribution']}")
            
            # Show retry candidates
            if retry_candidates:
                print("  Retry candidates:")
                for candidate in retry_candidates[:3]:  # Show first 3
                    print(f"    - {candidate['episode_id']}: {candidate['title']} (category: {candidate['failure_category']}, attempt #{candidate['retry_count'] + 1})")
            
        except Exception as e:
            print(f"\n❌ Error checking {db_name} database: {e}")
    
    # Show system information
    audio_cache = Path("audio_cache")
    audio_files = len(list(audio_cache.glob("*.mp3"))) if audio_cache.exists() else 0
    
    print(f"\n🗂️ System:")
    print(f"  Audio cache files: {audio_files}")

if __name__ == "__main__":
    show_failure_status()