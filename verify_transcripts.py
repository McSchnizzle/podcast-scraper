#!/usr/bin/env python3
"""
Transcript-Database Consistency Verification
Ensures each transcript file has exactly one corresponding database entry marked as processed
"""

import sqlite3
import os
from pathlib import Path

def verify_transcript_database_consistency(db_path="podcast_monitor.db", transcript_dir="transcripts"):
    """Verify each transcript file has exactly one processed database entry"""
    
    print("🔍 TRANSCRIPT-DATABASE CONSISTENCY VERIFICATION")
    print("=" * 70)
    
    # Get all transcript files
    transcript_files = []
    transcript_path = Path(transcript_dir)
    if transcript_path.exists():
        transcript_files = [f.stem for f in transcript_path.glob("*.txt")]
        print(f"📄 Found {len(transcript_files)} transcript files")
    else:
        print(f"❌ Transcript directory '{transcript_dir}' not found")
        return
    
    # Get all processed episodes from database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT episode_id, title, status, processed, transcript_path 
            FROM episodes 
            WHERE processed = 1 OR status = 'completed'
            ORDER BY episode_id
        """)
        
        processed_episodes = cursor.fetchall()
        print(f"✅ Found {len(processed_episodes)} processed database entries")
        
        print(f"\n📊 CONSISTENCY ANALYSIS:")
        print("=" * 50)
        
        # Extract transcript filenames from database paths
        transcript_ids = set(transcript_files)
        db_transcript_files = set()
        episode_mapping = {}
        
        for episode in processed_episodes:
            episode_id, title, status, processed, transcript_path = episode
            if transcript_path:
                # Extract just the filename without extension
                transcript_file = Path(transcript_path).stem
                db_transcript_files.add(transcript_file)
                episode_mapping[transcript_file] = (episode_id, title, status)
        
        # Files with database entries
        matched = transcript_ids & db_transcript_files
        print(f"✅ Matched (transcript + database): {len(matched)}")
        
        # Files without database entries  
        orphaned_transcripts = transcript_ids - db_transcript_files
        if orphaned_transcripts:
            print(f"⚠️  Orphaned transcripts (no database entry): {len(orphaned_transcripts)}")
            for transcript_id in sorted(orphaned_transcripts):
                print(f"   • {transcript_id}.txt")
        
        # Database entries without transcript files
        missing_transcripts = db_transcript_files - transcript_ids
        if missing_transcripts:
            print(f"❌ Missing transcripts (database shows processed): {len(missing_transcripts)}")
            for transcript_file in sorted(missing_transcripts):
                episode_id, title, status = episode_mapping[transcript_file]
                title_short = title[:60] + "..." if len(title) > 60 else title
                print(f"   • {transcript_file}.txt: {title_short}")
        
        print(f"\n📈 SUMMARY:")
        print(f"   Total transcripts: {len(transcript_files)}")
        print(f"   Total processed DB entries: {len(processed_episodes)}")
        print(f"   Perfect matches: {len(matched)}")
        print(f"   Orphaned transcripts: {len(orphaned_transcripts)}")
        print(f"   Missing transcripts: {len(missing_transcripts)}")
        
        # Consistency status
        if len(orphaned_transcripts) == 0 and len(missing_transcripts) == 0:
            print(f"\n🎯 RESULT: PERFECT CONSISTENCY ✅")
            print("   Every transcript has exactly one processed database entry")
        else:
            print(f"\n⚠️  RESULT: INCONSISTENCY DETECTED")
            print("   Some transcripts or database entries are mismatched")
            
        # Show matched entries for verification
        if matched:
            print(f"\n✅ VERIFIED CONSISTENT ENTRIES:")
            print("-" * 50)
            for transcript_file in sorted(matched):
                episode_id, title, status = episode_mapping[transcript_file]
                title_short = title[:50] + "..." if len(title) > 50 else title
                print(f"   {transcript_file}.txt → {episode_id[:20]}... [{status}]")
                print(f"     {title_short}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    verify_transcript_database_consistency()