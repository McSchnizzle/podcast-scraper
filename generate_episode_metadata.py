#!/usr/bin/env python3
"""
Episode Metadata Generator for Vercel RSS Function
Scans daily_digests directory and creates metadata JSON for RSS feed
"""

import os
import json
from datetime import datetime
from pathlib import Path
import hashlib

def estimate_duration_from_size(size_bytes):
    """Estimate audio duration from MP3 file size (128kbps)"""
    # 128kbps = 16KB/s average
    estimated_seconds = size_bytes / (16 * 1024)
    return int(estimated_seconds)

def generate_guid(filename, base_url):
    """Generate unique GUID for episode"""
    return hashlib.md5(f"{base_url}/{filename}".encode()).hexdigest()

def scan_digest_files(days=7):
    """Scan daily_digests directory for recent MP3 files"""
    digest_dir = Path("daily_digests")
    base_url = "https://paulrbrown.org"
    episodes = []
    
    if not digest_dir.exists():
        print("No daily_digests directory found")
        return episodes
    
    for file in digest_dir.glob("complete_topic_digest_*.mp3"):
        # Extract timestamp from filename
        timestamp_str = file.stem.replace("complete_topic_digest_", "")
        
        try:
            episode_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            
            # Check if within retention period
            age_days = (datetime.now() - episode_date).days
            if age_days <= days:
                file_size = file.stat().st_size
                duration = estimate_duration_from_size(file_size)
                
                episode_data = {
                    "filename": file.name,
                    "title": f"Daily Tech Digest - {episode_date.strftime('%B %d, %Y')}",
                    "description": f"AI-generated daily digest covering tech news, product launches, and industry insights from {episode_date.strftime('%B %d, %Y')}. Features cross-episode synthesis with topic-based organization and actionable insights.",
                    "date": episode_date.isoformat(),
                    "size": file_size,
                    "duration": duration,
                    "guid": generate_guid(file.name, base_url),
                    "url": f"{base_url}/audio/{file.name}",
                    "storage_url": f"{base_url}/api/audio/{file.name}",
                    "local_path": str(file.absolute())
                }
                
                episodes.append(episode_data)
                
        except ValueError as e:
            print(f"Could not parse timestamp from {file.name}: {e}")
            continue
    
    # Sort by date descending (newest first)
    episodes.sort(key=lambda x: x["date"], reverse=True)
    return episodes

def main():
    """Generate episode metadata JSON file"""
    episodes = scan_digest_files()
    
    metadata = {
        "generated_at": datetime.now().isoformat(),
        "episode_count": len(episodes),
        "episodes": episodes
    }
    
    # Write to output file for Vercel function
    output_file = "episode_metadata.json"
    with open(output_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Generated metadata for {len(episodes)} episodes")
    print(f"Metadata saved to: {output_file}")
    
    # Display summary
    for episode in episodes[:3]:  # Show first 3
        print(f"  {episode['title']} - {episode['size']/1024/1024:.1f}MB - {episode['duration']//60}min")

if __name__ == "__main__":
    main()