#!/usr/bin/env python3
"""
Cleanup Old GitHub Releases
Remove releases older than 7 days to maintain feed freshness
"""

import subprocess
import json
from datetime import datetime, timedelta, timezone

def get_old_releases():
    """Get releases older than 7 days"""
    try:
        # Get all releases
        cmd = ["gh", "release", "list", "--json", "tagName,publishedAt,name"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        releases = json.loads(result.stdout)
        
        # Filter releases older than 7 days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        old_releases = []
        
        for release in releases:
            if not release['tagName'].startswith('daily-'):
                continue  # Skip non-daily releases
                
            published_at = datetime.fromisoformat(release['publishedAt'].replace('Z', '+00:00'))
            
            if published_at < cutoff_date:
                old_releases.append(release)
        
        return old_releases
        
    except Exception as e:
        print(f"❌ Error fetching releases: {e}")
        return []

def delete_release(tag_name):
    """Delete a specific release"""
    try:
        cmd = ["gh", "release", "delete", tag_name, "--yes"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✅ Deleted release: {tag_name}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to delete {tag_name}: {e.stderr}")
        return False

def main():
    """Main cleanup workflow"""
    print("🧹 GitHub Releases Cleanup (7-day retention)")
    print("=" * 50)
    
    old_releases = get_old_releases()
    
    if not old_releases:
        print("✅ No old releases found - system is clean!")
        return
    
    print(f"📋 Found {len(old_releases)} releases older than 7 days")
    
    deleted_count = 0
    for release in old_releases:
        tag_name = release['tagName']
        published_at = release['publishedAt']
        
        print(f"🗑️ Deleting: {tag_name} (published {published_at})")
        
        if delete_release(tag_name):
            deleted_count += 1
    
    print(f"\n🎉 Cleanup complete!")
    print(f"   • Releases deleted: {deleted_count}")
    print(f"   • RSS feed automatically updated")

if __name__ == "__main__":
    main()