#!/usr/bin/env python3
"""
7-Day Retention Management
Removes audio files and transcripts older than 7 days
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

def cleanup_old_files(directory, pattern, max_age_days=7):
    """Remove files older than max_age_days"""
    if not Path(directory).exists():
        return []
    
    cutoff_date = datetime.now() - timedelta(days=max_age_days)
    removed_files = []
    
    for file_path in Path(directory).glob(pattern):
        # Extract timestamp from filename
        timestamp_str = file_path.stem.replace("complete_topic_digest_", "")
        
        try:
            if "complete_topic_digest_" in file_path.name:
                file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            else:
                # Use file modification time for other files
                file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
            
            if file_date < cutoff_date:
                file_size = file_path.stat().st_size
                file_path.unlink()
                removed_files.append({
                    "path": str(file_path),
                    "size": file_size,
                    "age_days": (datetime.now() - file_date).days
                })
                
        except (ValueError, OSError) as e:
            print(f"Error processing {file_path}: {e}")
            continue
    
    return removed_files

def main():
    """Run cleanup for 7-day retention"""
    print("Starting 7-day retention cleanup...")
    
    # Cleanup audio digest files
    removed_audio = cleanup_old_files("daily_digests", "complete_topic_digest_*.mp3", 7)
    
    # Cleanup other audio assets 
    removed_assets = cleanup_old_files("daily_digests", "*.mp3", 7)
    
    # Cleanup old transcripts (keep longer - 30 days)
    removed_transcripts = cleanup_old_files("transcripts", "*.txt", 30)
    
    # Summary
    total_removed = len(removed_audio) + len(removed_assets) + len(removed_transcripts)
    total_size = sum(f["size"] for f in removed_audio + removed_assets + removed_transcripts)
    
    print(f"Cleanup complete:")
    print(f"  Audio digests: {len(removed_audio)} files")
    print(f"  Audio assets: {len(removed_assets)} files")  
    print(f"  Old transcripts: {len(removed_transcripts)} files")
    print(f"  Total: {total_removed} files, {total_size/1024/1024:.1f}MB freed")
    
    # Log details for recent removals
    for file_info in removed_audio:
        print(f"  Removed: {Path(file_info['path']).name} ({file_info['age_days']} days old)")

if __name__ == "__main__":
    main()