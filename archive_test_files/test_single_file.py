#!/usr/bin/env python3
"""
Test script to process a single audio file with the robust transcription workflow
and update the database accordingly
"""

import os
import sqlite3
import sys
from pathlib import Path
from content_processor import ContentProcessor

def get_episode_for_audio_file(audio_file_hash, db_path="podcast_monitor.db"):
    """Find episode ID associated with an audio file hash"""
    try:
        import hashlib
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all unprocessed episodes and check their hashes
        cursor.execute("""
            SELECT e.episode_id, e.title, f.title as podcast_title, e.audio_url
            FROM episodes e
            LEFT JOIN feeds f ON e.feed_id = f.id
            WHERE e.processed = 0
            AND e.audio_url IS NOT NULL
            ORDER BY e.published_date DESC
        """)
        
        episodes = cursor.fetchall()
        conn.close()
        
        # Find episode with matching hash
        for episode in episodes:
            episode_id = episode[0]
            generated_hash = hashlib.md5(episode_id.encode()).hexdigest()[:8]
            
            if generated_hash == audio_file_hash:
                return {
                    'episode_id': episode[0],
                    'title': episode[1], 
                    'podcast_title': episode[2] if episode[2] else 'Unknown Podcast',
                    'audio_url': episode[3]
                }
        
        return None
        
    except Exception as e:
        print(f"❌ Database query error: {e}")
        return None

def update_episode_with_transcript(episode_id, transcript, db_path="podcast_monitor.db"):
    """Update episode in database with transcript and mark as processed"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Save transcript to file in transcripts directory
        transcripts_dir = Path("transcripts")
        transcripts_dir.mkdir(exist_ok=True)
        
        # Create transcript filename from episode hash
        episode_hash = episode_id.split('/')[-1] if '/' in episode_id else episode_id[:8]
        transcript_filename = f"{episode_hash}.txt"
        transcript_path = transcripts_dir / transcript_filename
        
        # Write transcript to file
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcript)
        
        # Update episode with transcript path and mark as processed
        cursor.execute("""
            UPDATE episodes 
            SET transcript_path = ?, 
                processed = 1
            WHERE episode_id = ?
        """, (str(transcript_path), episode_id))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        if rows_affected > 0:
            print(f"✅ Database updated: Episode {episode_id} marked as processed")
            print(f"   Transcript saved to: {transcript_path}")
            print(f"   Transcript length: {len(transcript):,} characters")
            return True
        else:
            print(f"⚠️ No database rows updated for episode {episode_id}")
            return False
            
    except Exception as e:
        print(f"❌ Database update error: {e}")
        return False

def process_single_file(audio_file_path):
    """Process a single audio file through the complete workflow"""
    try:
        print(f"🎬 Processing single audio file: {Path(audio_file_path).name}")
        print("=" * 80)
        
        # Extract audio file hash from filename
        audio_filename = Path(audio_file_path).stem
        print(f"📄 Audio file hash: {audio_filename}")
        
        # Find corresponding episode in database
        print(f"🔍 Looking up episode in database...")
        episode_info = get_episode_for_audio_file(audio_filename)
        
        if not episode_info:
            print(f"⚠️ No episode found in database for audio file {audio_filename}")
            print("   Proceeding with transcription anyway...")
            episode_id = audio_filename
        else:
            episode_id = episode_info['episode_id']
            print(f"✅ Found episode: {episode_info['title']}")
            print(f"   Podcast: {episode_info['podcast_title']}")
            print(f"   Episode ID: {episode_id}")
        
        # Initialize content processor
        print(f"\n🚀 Initializing content processor...")
        processor = ContentProcessor()
        
        if not processor.asr_model:
            print("❌ Parakeet MLX model not available")
            return False
        
        print("✅ Content processor ready")
        
        # Perform transcription
        print(f"\n🎯 Starting transcription workflow...")
        print("-" * 60)
        
        transcript = processor._audio_to_transcript(audio_file_path)
        
        if not transcript:
            print("❌ Transcription failed")
            return False
        
        print("-" * 60)
        print(f"✅ Transcription completed successfully")
        print(f"   Final transcript length: {len(transcript):,} characters")
        
        # Show preview
        print(f"\n📄 Transcript Preview:")
        print("=" * 60)
        preview = transcript[:500] + "..." if len(transcript) > 500 else transcript
        print(preview)
        print("=" * 60)
        
        # Update database if episode was found
        if episode_info:
            print(f"\n💾 Updating database...")
            success = update_episode_with_transcript(episode_id, transcript)
            if success:
                print("✅ Database update successful")
                
                # Delete audio file after successful transcription and database update
                print(f"\n🗑️ Cleaning up audio file...")
                try:
                    audio_size_mb = Path(audio_file_path).stat().st_size / (1024 * 1024)
                    os.remove(audio_file_path)
                    print(f"✅ Deleted audio file: {Path(audio_file_path).name} ({audio_size_mb:.1f}MB freed)")
                except Exception as e:
                    print(f"⚠️ Could not delete audio file: {e}")
            else:
                print("❌ Database update failed - keeping audio file")
        else:
            print(f"\n💾 Skipping database update (episode not found in DB)")
            print("ℹ️ Audio file retained (not linked to database episode)")
            
            # Save transcript to transcripts directory instead
            transcripts_dir = Path("transcripts")
            transcripts_dir.mkdir(exist_ok=True)
            transcript_file = transcripts_dir / f"{audio_filename}.txt"
            try:
                with open(transcript_file, 'w', encoding='utf-8') as f:
                    f.write(transcript)
                print(f"✅ Transcript saved to: {transcript_file}")
            except Exception as e:
                print(f"❌ Could not save transcript file: {e}")
        
        print(f"\n🎉 Single file processing complete!")
        return True
        
    except Exception as e:
        print(f"❌ Single file processing failed: {e}")
        return False

def main():
    """Main function to test with database-linked audio file"""
    # Use files that are linked to database episodes  
    test_files = [
        "/Users/paulbrown/Desktop/podcast-scraper/audio_cache/6d1d6514.wav",  # Smallest file (35MB)
        "/Users/paulbrown/Desktop/podcast-scraper/audio_cache/50e08aaa.wav",  # Medium file for testing
        "/Users/paulbrown/Desktop/podcast-scraper/audio_cache/be40f5f0.wav",  # Larger file
    ]
    
    # Find the first available file
    test_file = None
    for file_path in test_files:
        if os.path.exists(file_path):
            test_file = file_path
            break
    
    if not test_file:
        print("❌ No test audio files found")
        print("Available files:")
        audio_dir = Path("/Users/paulbrown/Desktop/podcast-scraper/audio_cache")
        for wav_file in audio_dir.glob("*.wav"):
            size_mb = wav_file.stat().st_size / (1024 * 1024)
            print(f"   {wav_file.name}: {size_mb:.1f}MB")
        return
    
    size_mb = Path(test_file).stat().st_size / (1024 * 1024)
    print(f"🎯 Testing with: {Path(test_file).name} ({size_mb:.1f}MB)")
    
    success = process_single_file(test_file)
    
    if success:
        print(f"\n✅ Test completed successfully!")
    else:
        print(f"\n❌ Test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()