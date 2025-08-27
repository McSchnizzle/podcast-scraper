#!/usr/bin/env python3
"""
Episode Status Report
Provides detailed status breakdown including failures vs skips
"""

import sqlite3
from pathlib import Path

def get_detailed_status(db_path="podcast_monitor.db"):
    """Get comprehensive episode status breakdown"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("📊 DETAILED EPISODE STATUS REPORT")
        print("=" * 60)
        
        # Overall summary
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped
            FROM episodes
        """)
        
        total, completed, pending, failed, skipped = cursor.fetchone()
        
        print(f"📈 OVERALL SUMMARY:")
        print(f"   • Total Episodes: {total}")
        print(f"   • ✅ Completed: {completed} ({completed/total*100:.1f}%)")
        print(f"   • ⏳ Pending: {pending} ({pending/total*100:.1f}%)")
        print(f"   • ❌ Failed: {failed} ({failed/total*100:.1f}%)")  
        print(f"   • ⏸️ Skipped: {skipped} ({skipped/total*100:.1f}%)")
        
        # Breakdown by source
        print(f"\n📍 BREAKDOWN BY SOURCE:")
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN episode_id LIKE 'yt:video:%' THEN 'YouTube'
                    ELSE 'RSS'
                END as source,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped
            FROM episodes
            GROUP BY source
            ORDER BY source
        """)
        
        for source, src_total, src_completed, src_pending, src_failed, src_skipped in cursor.fetchall():
            print(f"   {source}:")
            print(f"     Total: {src_total} | ✅ {src_completed} | ⏳ {src_pending} | ❌ {src_failed} | ⏸️ {src_skipped}")
        
        # Failed episodes details
        if failed > 0:
            print(f"\n❌ FAILURE DETAILS:")
            cursor.execute("""
                SELECT episode_id, title, failure_reason, retry_count
                FROM episodes 
                WHERE status = 'failed'
                ORDER BY failure_timestamp DESC
                LIMIT 10
            """)
            
            failures = cursor.fetchall()
            for episode_id, title, reason, retries in failures:
                print(f"   • {title[:50]}...")
                print(f"     Reason: {reason}")
                print(f"     Retries: {retries}")
                print()
        
        # Skipped episodes details  
        if skipped > 0:
            print(f"\n⏸️ SKIP DETAILS:")
            cursor.execute("""
                SELECT episode_id, title, failure_reason
                FROM episodes 
                WHERE status = 'skipped'
                ORDER BY failure_timestamp DESC
                LIMIT 10
            """)
            
            skips = cursor.fetchall()
            for episode_id, title, reason in skips:
                print(f"   • {title[:50]}...")
                print(f"     Reason: {reason}")
                print()
        
        # Ready to process
        print(f"\n🚀 READY TO PROCESS:")
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN episode_id LIKE 'yt:video:%' THEN 'YouTube'
                    ELSE 'RSS'
                END as source,
                COUNT(*) as count
            FROM episodes 
            WHERE status = 'pending'
            GROUP BY source
        """)
        
        pending_breakdown = cursor.fetchall()
        for source, count in pending_breakdown:
            print(f"   • {source}: {count} episodes")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Status report error: {e}")

def get_processing_recommendations(db_path="podcast_monitor.db"):
    """Provide recommendations for what to process next"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"\n💡 PROCESSING RECOMMENDATIONS:")
        print("=" * 40)
        
        # Check for retry candidates
        cursor.execute("""
            SELECT COUNT(*) 
            FROM episodes 
            WHERE status = 'failed' 
            AND failure_reason NOT LIKE 'Skipped:%'
            AND retry_count < 3
        """)
        
        retry_candidates = cursor.fetchone()[0]
        if retry_candidates > 0:
            print(f"🔄 {retry_candidates} failed episodes could be retried")
        
        # Check pending YouTube vs RSS
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN episode_id LIKE 'yt:video:%' THEN 1 ELSE 0 END) as youtube,
                SUM(CASE WHEN episode_id NOT LIKE 'yt:video:%' THEN 1 ELSE 0 END) as rss
            FROM episodes 
            WHERE status = 'pending'
        """)
        
        youtube_pending, rss_pending = cursor.fetchone()
        
        if youtube_pending > 0:
            print(f"📺 {youtube_pending} YouTube episodes (fast processing)")
        if rss_pending > 0:
            print(f"🎵 {rss_pending} RSS episodes (slower, requires audio transcription)")
            
        # Estimate processing time
        if rss_pending > 0:
            avg_time = 2  # minutes per episode (conservative estimate)
            total_time = rss_pending * avg_time
            print(f"⏱️ Estimated RSS processing time: {total_time/60:.1f} hours")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Recommendations error: {e}")

def main():
    """Main status report function"""
    get_detailed_status()
    get_processing_recommendations()

if __name__ == "__main__":
    main()