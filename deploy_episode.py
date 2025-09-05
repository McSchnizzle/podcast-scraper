#!/usr/bin/env python3
"""
Deploy Episode to GitHub Releases
Creates GitHub release with latest complete digest MP3
"""

import os
import subprocess
import glob
from datetime import datetime
from utils.datetime_utils import now_utc
from pathlib import Path

def get_latest_complete_digest():
    """Find the latest complete_topic_digest MP3 file"""
    pattern = "daily_digests/complete_topic_digest_*.mp3"
    files = glob.glob(pattern)
    
    if not files:
        print("❌ No complete digest files found")
        return None
    
    # Sort by modification time (newest first)
    files.sort(key=os.path.getmtime, reverse=True)
    latest_file = files[0]
    
    print(f"📦 Found latest episode: {os.path.basename(latest_file)}")
    return latest_file

def create_github_release(mp3_file):
    """Create GitHub release with MP3 file"""
    if not mp3_file or not os.path.exists(mp3_file):
        print("❌ MP3 file not found")
        return False
    
    filename = os.path.basename(mp3_file)
    date_str = filename.split('_')[-2]  # Extract YYYYMMDD
    
    try:
        episode_date = datetime.strptime(date_str, '%Y%m%d')
        release_tag = f"daily-{episode_date.strftime('%Y-%m-%d')}"
        release_title = f"Daily Tech Digest - {episode_date.strftime('%B %d, %Y')}"
    except:
        # Fallback to today's date
        today = now_utc()
        release_tag = f"daily-{today.strftime('%Y-%m-%d')}"
        release_title = f"Daily Tech Digest - {today.strftime('%B %d, %Y')}"
    
    file_size = os.path.getsize(mp3_file)
    duration_min = file_size // (15000 * 60)  # Estimate minutes
    
    release_notes = f"""Daily Tech Digest episode featuring AI-generated content from leading podcasts and creators.

**Episode Details:**
- Duration: ~{duration_min} minutes
- Size: {file_size / 1024 / 1024:.1f}MB
- Generated: {now_utc().strftime('%Y-%m-%d %H:%M')}
- Topics: AI Tools, Creative Applications, Social Commentary

**RSS Feed**: Available at https://podcast-scraper-kxxvl6bnx-paul-browns-projects-cf5d21b4.vercel.app/daily-digest.xml

Generated automatically from podcast monitoring and AI synthesis."""

    try:
        # Try to create release, if it exists, upload to existing release
        try:
            cmd = [
                "gh", "release", "create", release_tag,
                mp3_file,
                "--title", release_title,
                "--notes", release_notes,
                "--latest"
            ]
            
            print(f"🚀 Creating GitHub release: {release_tag}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            if "already exists" in e.stderr:
                print(f"📦 Release {release_tag} exists, uploading to existing release...")
                cmd = [
                    "gh", "release", "upload", release_tag,
                    mp3_file,
                    "--clobber"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            else:
                raise
        
        print(f"✅ Release created successfully: {release_tag}")
        print(f"🔗 Release URL: https://github.com/McSchnizzle/podcast-scraper/releases/tag/{release_tag}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create release: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main deployment workflow"""
    print("📡 Daily Digest Episode Deployment")
    print("=" * 40)
    
    # Find latest episode
    mp3_file = get_latest_complete_digest()
    if not mp3_file:
        return False
    
    # Create GitHub release
    success = create_github_release(mp3_file)
    
    if success:
        print("\n🎉 Episode deployed successfully!")
        print("📱 RSS feed will update automatically")
        print("🔄 Podcast apps will see new episode within minutes")
        return True
    else:
        print("\n❌ Deployment failed")
        return False

if __name__ == "__main__":
    main()