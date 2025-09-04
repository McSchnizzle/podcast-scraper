#!/usr/bin/env python3
"""
Multi-Topic Episode Deployment to GitHub Releases
Creates GitHub releases with all new topic-specific digest MP3s
"""

import os
import subprocess
import glob
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

class MultiTopicDeployer:
    def __init__(self, base_url=None):
        # Use environment variable or fallback to default
        self.base_url = base_url or os.getenv('PODCAST_BASE_URL', 'https://podcast.paulrbrown.org')
        self.digests_dir = Path("daily_digests")
        self.deployed_marker_file = "deployed_episodes.json"
        
        # Validate base URL is set
        if not self.base_url:
            raise ValueError("PODCAST_BASE_URL environment variable must be set")
        
        print(f"📡 Podcast base URL: {self.base_url}")
        
        # Load previously deployed episodes
        self.deployed_episodes = self._load_deployed_episodes()
    
    def _load_deployed_episodes(self) -> Dict[str, str]:
        """Load record of previously deployed episodes"""
        marker_file = Path(self.deployed_marker_file)
        if marker_file.exists():
            try:
                with open(marker_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Could not load deployed episodes marker: {e}")
        return {}
    
    def _save_deployed_episodes(self):
        """Save record of deployed episodes"""
        try:
            with open(self.deployed_marker_file, 'w') as f:
                json.dump(self.deployed_episodes, f, indent=2)
        except Exception as e:
            print(f"⚠️  Could not save deployed episodes marker: {e}")
    
    def _save_deployment_metadata(self, digests: List[Dict], release_tag: str):
        """Save deployment metadata for RSS generator consumption"""
        metadata = {
            'deployment_timestamp': datetime.now().isoformat(),
            'release_tag': release_tag,
            'github_release_url': f"https://github.com/McSchnizzle/podcast-scraper/releases/tag/{release_tag}",
            'episodes': []
        }
        
        for digest in digests:
            file_size, duration = self._get_file_info(digest['mp3_file'])
            
            # Construct GitHub release asset URL  
            asset_url = f"https://github.com/McSchnizzle/podcast-scraper/releases/download/{release_tag}/{digest['mp3_file'].name}"
            
            metadata['episodes'].append({
                'topic': digest['topic'],
                'timestamp': digest['timestamp'],
                'date': digest['date'].isoformat(),
                'local_path': str(digest['mp3_file']),
                'public_url': asset_url,
                'file_size': file_size,
                'duration_estimate': duration,
                'is_enhanced': '_enhanced' in digest['mp3_file'].name,
                'file_key': digest['file_key']
            })
        
        # Save metadata for RSS generator
        metadata_file = "deployment_metadata.json"
        try:
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            print(f"✅ Saved deployment metadata: {metadata_file}")
        except Exception as e:
            print(f"⚠️ Could not save deployment metadata: {e}")
    
    def find_new_digest_files(self) -> List[Dict]:
        """Find new digest files that haven't been deployed"""
        new_digests = []
        
        if not self.digests_dir.exists():
            return []
        
        # Pattern for topic-specific digests: {topic}_digest_{timestamp}.md
        topic_pattern = re.compile(r'^([a-zA-Z_]+)_digest_(\d{8}_\d{6})\.md$')
        
        for md_file in self.digests_dir.glob("*_digest_*.md"):
            match = topic_pattern.match(md_file.name)
            if not match:
                continue
            
            topic, timestamp_str = match.groups()
            
            # Check if already deployed
            file_key = f"{topic}_{timestamp_str}"
            if file_key in self.deployed_episodes:
                continue
            
            # Check if we have a corresponding MP3 file (prioritize enhanced versions)
            mp3_candidates = [
                self.digests_dir / f"{topic}_digest_{timestamp_str}_enhanced.mp3",  # Preferred with music
                self.digests_dir / f"{topic}_digest_{timestamp_str}.mp3",           # Standard TTS  
                self.digests_dir / f"complete_topic_digest_{timestamp_str}.mp3"     # Legacy naming
            ]
            
            mp3_file = None
            for candidate in mp3_candidates:
                if candidate.exists():
                    mp3_file = candidate
                    break
            
            if not mp3_file:
                print(f"⚠️  No MP3 file found for {md_file.name}")
                continue
            
            # Parse timestamp
            try:
                file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except ValueError:
                print(f"⚠️  Invalid timestamp format in {md_file.name}")
                continue
            
            new_digests.append({
                'topic': topic,
                'timestamp': timestamp_str,
                'date': file_date,
                'md_file': md_file,
                'mp3_file': mp3_file,
                'file_key': file_key
            })
        
        # Sort by date (oldest first for deployment order)
        new_digests.sort(key=lambda x: x['date'])
        return new_digests
    
    def _get_file_info(self, file_path: Path) -> Tuple[int, str]:
        """Get file size and duration estimate"""
        try:
            file_size = file_path.stat().st_size
            # Rough estimate: 1MB ≈ 1 minute for speech MP3
            duration_minutes = max(1, file_size // (1024 * 1024))
            duration_str = f"~{duration_minutes} minutes"
            return file_size, duration_str
        except:
            return 0, "Unknown duration"
    
    def _generate_release_info(self, digests: List[Dict]) -> Tuple[str, str, str]:
        """Generate release tag, title, and description from digest list"""
        if not digests:
            today = datetime.now()
            return (
                f"daily-{today.strftime('%Y-%m-%d')}",
                f"Daily Digest - {today.strftime('%B %d, %Y')}",
                "Daily tech and society digest episodes"
            )
        
        # Use the date from the first (oldest) digest for consistency
        first_date = digests[0]['date']
        release_date = first_date.strftime('%Y-%m-%d')
        release_tag = f"multi-topic-{release_date}"
        release_title = f"Multi-Topic Daily Digest - {first_date.strftime('%B %d, %Y')}"
        
        # Generate description with topic summary
        topic_counts = {}
        total_duration = 0
        
        for digest in digests:
            topic = digest['topic'].replace('_', ' ').title()
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
            file_size, _ = self._get_file_info(digest['mp3_file'])
            total_duration += max(1, file_size // (1024 * 1024))  # rough minutes
        
        topic_summary = ", ".join([f"{topic} ({count})" for topic, count in topic_counts.items()])
        
        description = f"""Daily digest episodes covering multiple topics:

**Topics**: {topic_summary}
**Total Duration**: ~{total_duration} minutes
**Episodes**: {len(digests)}

AI-generated digest from leading podcasts and creators, organized by topic for focused listening."""
        
        return release_tag, release_title, description
    
    def create_github_release(self, digests: List[Dict]) -> bool:
        """Create GitHub release with all new digest MP3 files"""
        if not digests:
            print("📦 No new digests to deploy")
            return True
        
        print(f"🚀 Deploying {len(digests)} new digest episodes")
        
        # Generate release information
        release_tag, release_title, description = self._generate_release_info(digests)
        
        # Save deployment metadata for RSS generator
        self._save_deployment_metadata(digests, release_tag)
        
        try:
            # Create release
            cmd = [
                'gh', 'release', 'create', release_tag,
                '--title', release_title,
                '--notes', description,
                '--target', 'main'
            ]
            
            # Add all MP3 files to the command
            for digest in digests:
                cmd.append(str(digest['mp3_file']))
                print(f"  📎 Adding: {digest['mp3_file'].name}")
            
            print(f"📡 Creating release: {release_tag}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print(f"✅ Release created successfully: {release_tag}")
                
                # Mark episodes as deployed
                for digest in digests:
                    self.deployed_episodes[digest['file_key']] = release_tag
                    print(f"  ✓ Marked as deployed: {digest['file_key']}")
                
                self._save_deployed_episodes()
                return True
            else:
                print(f"❌ Failed to create release: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ GitHub release creation timed out")
            return False
        except Exception as e:
            print(f"❌ Error creating GitHub release: {e}")
            return False
    
    def deploy_new_episodes(self, dry_run: bool = False) -> bool:
        """Main deployment method - find and deploy all new episodes"""
        print("🔍 Checking for new digest episodes to deploy...")
        
        new_digests = self.find_new_digest_files()
        
        if not new_digests:
            print("✅ No new episodes found - deployment up to date")
            return True
        
        print(f"📦 Found {len(new_digests)} new episodes:")
        for digest in new_digests:
            file_size, duration = self._get_file_info(digest['mp3_file'])
            enhanced_marker = " (enhanced)" if '_enhanced' in digest['mp3_file'].name else ""
            print(f"  • {digest['topic']} ({digest['timestamp']}) - {duration}{enhanced_marker}")
        
        if dry_run:
            print("🧪 DRY RUN MODE - Would deploy but not actually creating release")
            return True
        
        # Deploy all new episodes in a single release
        return self.create_github_release(new_digests)
    
    def force_redeploy_recent(self, days=1) -> bool:
        """Force redeployment of recent episodes (for testing)"""
        print(f"🔄 Force redeploying episodes from last {days} day(s)...")
        
        cutoff_date = datetime.now().timestamp() - (days * 24 * 3600)
        
        # Clear deployed status for recent episodes
        keys_to_remove = []
        for key in self.deployed_episodes.keys():
            try:
                parts = key.split('_')
                if len(parts) >= 3:
                    timestamp_str = '_'.join(parts[-2:])  # Get last two parts (YYYYMMDD_HHMMSS)
                    file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    if file_date.timestamp() > cutoff_date:
                        keys_to_remove.append(key)
            except:
                continue
        
        for key in keys_to_remove:
            del self.deployed_episodes[key]
            print(f"  🗑️  Cleared deployment status: {key}")
        
        self._save_deployed_episodes()
        
        # Now deploy as new episodes
        return self.deploy_new_episodes()


def main():
    """Deploy new multi-topic digest episodes"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy multi-topic digest episodes to GitHub releases')
    parser.add_argument('--force-redeploy', type=int, metavar='DAYS', 
                        help='Force redeploy episodes from last N days')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be deployed without actually deploying')
    
    args = parser.parse_args()
    
    deployer = MultiTopicDeployer()
    
    try:
        if args.force_redeploy:
            if args.dry_run:
                print("🧪 DRY RUN: Force redeploy mode (no actual deployment)")
            success = deployer.force_redeploy_recent(args.force_redeploy)
        else:
            success = deployer.deploy_new_episodes(dry_run=args.dry_run)
        
        if success:
            if args.dry_run:
                print("🧪 DRY RUN: Multi-topic episode deployment preview complete!")
            else:
                print("🎙️  Multi-topic episode deployment complete!")
            return 0
        else:
            print("❌ Deployment failed")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️  Deployment cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error during deployment: {e}")
        return 1


if __name__ == "__main__":
    exit(main())