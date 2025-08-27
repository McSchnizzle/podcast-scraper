#!/usr/bin/env python3
"""
Sync Transcripts to Database
Links orphaned transcript files to existing database episodes and updates status
"""

import sqlite3
import os
import hashlib
from pathlib import Path
from datetime import datetime

def find_transcript_files(transcript_dir="transcripts"):
    """Find all transcript files"""
    transcript_path = Path(transcript_dir)
    if not transcript_path.exists():
        return {}
    
    transcripts = {}
    for file in transcript_path.glob("*.txt"):
        if file.stat().st_size > 100:  # Only substantial transcripts
            transcript_hash = file.stem  # filename without .txt
            transcripts[transcript_hash] = str(file)
    
    return transcripts

def get_all_episodes(db_path="podcast_monitor.db"):
    """Get all episodes from database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, episode_id, title, status, transcript_path
            FROM episodes
            ORDER BY id
        """)
        
        episodes = []
        for row in cursor.fetchall():
            episodes.append({
                'db_id': row[0],
                'episode_id': row[1], 
                'title': row[2],
                'status': row[3],
                'transcript_path': row[4]
            })
        
        conn.close()
        return episodes
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return []

def generate_episode_hash(episode_id):
    """Generate hash for episode ID (8 characters)"""
    return hashlib.md5(episode_id.encode()).hexdigest()[:8]

def sync_transcripts_to_database():
    """Main sync function"""
    print("🔄 TRANSCRIPT-DATABASE SYNC")
    print("=" * 40)
    
    # Get all transcript files
    transcript_files = find_transcript_files()
    print(f"📄 Found {len(transcript_files)} transcript files")
    
    # Get all database episodes  
    episodes = get_all_episodes()
    print(f"📊 Found {len(episodes)} database episodes")
    print()
    
    # Track updates
    updates_made = 0
    matched_files = set()
    
    # Method 1: Direct transcript_path matching (already linked)
    print("🔗 Method 1: Checking existing transcript_path links...")
    for episode in episodes:
        if episode['transcript_path']:
            transcript_file = Path(episode['transcript_path'])
            if transcript_file.exists():
                matched_files.add(transcript_file.stem)
                print(f"✅ Already linked: {episode['title'][:50]}... → {transcript_file.name}")
    
    print(f"   Found {len(matched_files)} pre-linked episodes")
    print()
    
    # Method 2: Hash matching for unlinked episodes
    print("🔍 Method 2: Hash matching for unlinked episodes...")
    
    for episode in episodes:
        if not episode['transcript_path']:  # No transcript linked yet
            episode_hash = generate_episode_hash(episode['episode_id'])
            
            if episode_hash in transcript_files and episode_hash not in matched_files:
                transcript_path = transcript_files[episode_hash]
                
                try:
                    # Update database
                    conn = sqlite3.connect("podcast_monitor.db")
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        UPDATE episodes 
                        SET transcript_path = ?, status = 'transcribed'
                        WHERE id = ?
                    """, (transcript_path, episode['db_id']))
                    
                    conn.commit()
                    conn.close()
                    
                    print(f"✅ Linked: {episode['title'][:50]}... → {Path(transcript_path).name}")
                    updates_made += 1
                    matched_files.add(episode_hash)
                    
                except Exception as e:
                    print(f"❌ Database update failed for episode {episode['db_id']}: {e}")
    
    print(f"   Linked {updates_made} new episodes")
    print()
    
    # Method 3: Find orphaned transcripts
    print("🔍 Method 3: Identifying orphaned transcripts...")
    orphaned_transcripts = []
    
    for transcript_hash, transcript_path in transcript_files.items():
        if transcript_hash not in matched_files:
            file_size = Path(transcript_path).stat().st_size
            orphaned_transcripts.append({
                'hash': transcript_hash,
                'path': transcript_path,
                'size': file_size
            })
    
    if orphaned_transcripts:
        print(f"⚠️ Found {len(orphaned_transcripts)} orphaned transcripts:")
        for orphan in orphaned_transcripts[:10]:  # Show first 10
            size_kb = orphan['size'] / 1024
            print(f"   📄 {Path(orphan['path']).name} ({size_kb:.1f}KB)")
        
        if len(orphaned_transcripts) > 10:
            print(f"   ... and {len(orphaned_transcripts) - 10} more")
    else:
        print("✅ No orphaned transcripts found")
    
    print()
    print("📊 SYNC SUMMARY")
    print("-" * 20)
    print(f"Total transcript files: {len(transcript_files)}")
    print(f"Pre-linked episodes: {len(matched_files) - updates_made}")
    print(f"Newly linked episodes: {updates_made}")
    print(f"Orphaned transcripts: {len(orphaned_transcripts)}")
    
    return updates_made, len(orphaned_transcripts)

def check_final_status():
    """Check final database status after sync"""
    print("\n📊 FINAL DATABASE STATUS")
    print("=" * 30)
    
    try:
        conn = sqlite3.connect("podcast_monitor.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'transcribing' THEN 1 ELSE 0 END) as transcribing,
                SUM(CASE WHEN status = 'transcribed' THEN 1 ELSE 0 END) as transcribed,
                SUM(CASE WHEN status = 'digested' THEN 1 ELSE 0 END) as digested,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM episodes
        """)
        
        result = cursor.fetchone()
        total, pending, transcribing, transcribed, digested, failed = result
        
        print(f"Total episodes: {total}")
        print(f"Pending: {pending}")
        print(f"Transcribing: {transcribing}")
        print(f"Transcribed: {transcribed}")
        print(f"Digested: {digested}")
        print(f"Failed: {failed}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking status: {e}")

def main():
    """CLI entry point"""
    print("Database-Transcript Synchronization Tool")
    print("=" * 45)
    
    updates, orphaned = sync_transcripts_to_database()
    check_final_status()
    
    if updates > 0:
        print(f"\n✅ Sync complete: {updates} episodes newly linked")
        print("🎯 Ready to run: python3 cleanup_processed_audio.py")
    
    if orphaned > 0:
        print(f"\n⚠️ {orphaned} orphaned transcripts need manual review")
    
    return 0

if __name__ == "__main__":
    exit(main())