#!/usr/bin/env python3
"""
Cleanup script to delete audio files that have already been successfully processed
"""

import os
import sqlite3
import hashlib
from pathlib import Path

def get_transcribed_episodes(db_path="podcast_monitor.db"):
    """Get list of episodes that have been successfully transcribed"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT episode_id, transcript_path 
            FROM episodes 
            WHERE status IN ('transcribed', 'digested') 
            AND transcript_path IS NOT NULL
        """)
        
        episodes = cursor.fetchall()
        conn.close()
        
        return episodes
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return []

def check_transcript_exists(transcript_path):
    """Check if transcript file actually exists"""
    return Path(transcript_path).exists() and Path(transcript_path).stat().st_size > 100

def find_audio_file_for_episode(episode_id, audio_dir="audio_cache"):
    """Find the corresponding audio file for an episode"""
    audio_hash = hashlib.md5(episode_id.encode()).hexdigest()[:8]
    audio_dir_path = Path(audio_dir)
    
    # Check for various audio formats
    for ext in ['.wav', '.mp3', '.m4a']:
        audio_file = audio_dir_path / f"{audio_hash}{ext}"
        if audio_file.exists():
            return audio_file
    
    return None

def cleanup_transcribed_audio():
    """Main cleanup function"""
    print("🧹 Starting cleanup of transcribed audio files...")
    print("=" * 60)
    
    # Get processed episodes
    transcribed_episodes = get_transcribed_episodes()
    print(f"📊 Found {len(transcribed_episodes)} transcribed episodes in database")
    
    if not transcribed_episodes:
        print("ℹ️ No transcribed episodes found - nothing to clean up")
        return
    
    total_freed = 0
    deleted_count = 0
    
    for episode_id, transcript_path in transcribed_episodes:
        print(f"\n🔍 Checking episode: {episode_id[:20]}...")
        
        # Check if transcript exists
        if not check_transcript_exists(transcript_path):
            print(f"⚠️ Transcript missing or too small: {transcript_path}")
            continue
        
        # Find corresponding audio file
        audio_file = find_audio_file_for_episode(episode_id)
        if not audio_file:
            print(f"ℹ️ No audio file found (already cleaned up)")
            continue
        
        # Get file size before deletion
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        
        # Verify transcript is substantial
        transcript_size = Path(transcript_path).stat().st_size
        if transcript_size < 1000:  # Less than 1KB transcript seems suspicious
            print(f"⚠️ Transcript too small ({transcript_size} bytes) - skipping audio deletion")
            continue
        
        # Delete audio file
        try:
            os.remove(audio_file)
            total_freed += file_size_mb
            deleted_count += 1
            print(f"✅ Deleted: {audio_file.name} ({file_size_mb:.1f}MB)")
            print(f"   Transcript: {transcript_size:,} characters at {transcript_path}")
        except Exception as e:
            print(f"❌ Could not delete {audio_file.name}: {e}")
    
    print("\n" + "=" * 60)
    print(f"🎉 Cleanup complete!")
    print(f"   • Files deleted: {deleted_count}")
    print(f"   • Disk space freed: {total_freed:.1f}MB ({total_freed/1024:.2f}GB)")
    
    if deleted_count == 0:
        print("ℹ️ No audio files needed cleanup - system is already clean!")

def dry_run():
    """Show what would be deleted without actually deleting"""
    print("🔍 DRY RUN - Showing what would be deleted...")
    print("=" * 60)
    
    transcribed_episodes = get_transcribed_episodes()
    print(f"📊 Found {len(transcribed_episodes)} transcribed episodes")
    
    total_size = 0
    file_count = 0
    
    for episode_id, transcript_path in transcribed_episodes:
        if not check_transcript_exists(transcript_path):
            continue
            
        audio_file = find_audio_file_for_episode(episode_id)
        if not audio_file:
            continue
        
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        total_size += file_size_mb
        file_count += 1
        
        print(f"📄 Would delete: {audio_file.name} ({file_size_mb:.1f}MB)")
        print(f"   Episode: {episode_id[:50]}...")
        print(f"   Transcript: {transcript_path}")
        print()
    
    print(f"📊 Summary: {file_count} files totaling {total_size:.1f}MB ({total_size/1024:.2f}GB)")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        dry_run()
    else:
        cleanup_transcribed_audio()