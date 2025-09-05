#!/usr/bin/env python3
"""
Multi-Topic RSS Feed Generator for Daily Podcast Digest
Generates podcatcher-compatible RSS XML supporting multiple topic-specific episodes per day
"""

import os
import json
import sqlite3
import re
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from utils.datetime_utils import now_utc
from xml.dom import minidom
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from episode_summary_generator import EpisodeSummaryGenerator
from utils.sanitization import sanitize_xml_content, safe_log_message, create_topic_pattern, create_topic_mp3_patterns

class MultiTopicRSSGenerator:
    def __init__(self, db_path="podcast_monitor.db", base_url="https://paulrbrown.org"):
        self.db_path = db_path
        self.base_url = base_url
        self.audio_base_url = f"{base_url}/audio"
        
        # Initialize AI summary generator
        self.summary_generator = EpisodeSummaryGenerator()
        
        # Topic configuration for RSS metadata
        self.topic_config = {
            "ai_news": {
                "display_name": "AI News & Developments",
                "description": "Latest artificial intelligence news, breakthroughs, and industry developments",
                "category": "Technology/AI"
            },
            "tech_product_releases": {
                "display_name": "Tech Product Releases",
                "description": "New product launches, updates, and technology announcements",
                "category": "Technology/Products"
            },
            "tech_news_and_tech_culture": {
                "display_name": "Tech News & Culture",
                "description": "Technology industry news, trends, and cultural developments",
                "category": "Technology/News"
            },
            "community_organizing": {
                "display_name": "Community Organizing",
                "description": "Grassroots organizing, community building, and civic engagement",
                "category": "Society/Community"
            },
            "social_justice": {
                "display_name": "Social Justice",
                "description": "Social justice issues, advocacy, and systemic change initiatives",
                "category": "Society/Justice"
            },
            "societal_culture_change": {
                "display_name": "Societal Culture Change",
                "description": "Cultural shifts, social movements, and societal transformation",
                "category": "Society/Culture"
            },
            "daily": {
                "display_name": "Daily Tech Digest",
                "description": "Comprehensive daily technology and society digest",
                "category": "Technology/General"
            },
            "general": {
                "display_name": "Daily Tech Digest",
                "description": "Comprehensive daily technology and society digest", 
                "category": "Technology/General"
            }
        }
        
        self.podcast_info = {
            "title": "Daily Tech & Society Digest",
            "description": "AI-generated daily digest covering technology, society, and culture from leading podcasts and creators, organized by topic",
            "author": "Paul Brown",
            "email": "podcast@paulrbrown.org",
            "language": "en-US",
            "category": "Technology",
            "subcategory": "News",
            "artwork_url": f"{base_url}/podcast-artwork.jpg",
            "website": f"{base_url}/daily-digest",
            "copyright": f"© {now_utc().year} Paul Brown"
        }
    
    def find_digest_files(self, days=7) -> List[Dict]:
        """Find all topic-specific digest files from the last N days"""
        # First try to load from deployment metadata (GitHub releases)
        deployment_metadata = self._load_deployment_metadata()
        if deployment_metadata:
            return self._process_deployment_metadata(deployment_metadata, days)
        
        # Fallback to file system discovery
        print("⚠️ No deployment metadata found, falling back to file system discovery")
        return self._find_digest_files_fallback(days)
    
    def _load_deployment_metadata(self) -> Optional[Dict]:
        """Load deployment metadata from deploy script"""
        metadata_file = Path("deployment_metadata.json")
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Could not load deployment metadata: {e}")
            return None
    
    def _process_deployment_metadata(self, metadata: Dict, days: int) -> List[Dict]:
        """Process deployment metadata into digest files format"""
        cutoff_date = now_utc()
        cutoff_date = cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_timestamp = cutoff_date.timestamp() - (days * 24 * 3600)
        
        digest_files = []
        
        for episode in metadata.get('episodes', []):
            try:
                file_date = datetime.fromisoformat(episode['date'])
                if file_date.timestamp() < cutoff_timestamp:
                    continue
                
                # Use deployment metadata for accurate URLs and file info
                digest_files.append({
                    'topic': episode['topic'],
                    'timestamp': episode['timestamp'],
                    'date': file_date,
                    'md_file': Path(episode['local_path']).with_suffix('.md') if Path(episode['local_path']).exists() else None,
                    'mp3_file': Path(episode['local_path']),
                    'public_url': episode['public_url'],  # GitHub release URL
                    'file_size': episode['file_size'],
                    'content': '',
                    'description': self._generate_episode_description(episode['topic'], file_date),
                    'title': self._generate_episode_title(episode['topic'], file_date),
                    'is_enhanced': episode.get('is_enhanced', False)
                })
            except Exception as e:
                print(f"⚠️ Error processing episode {episode.get('file_key', 'unknown')}: {e}")
        
        # Sort by date (newest first)  
        digest_files.sort(key=lambda x: x['date'], reverse=True)
        return digest_files
    
    def _find_digest_files_fallback(self, days=7) -> List[Dict]:
        """Fallback file system discovery method"""
        digest_files = []
        digest_dir = Path("daily_digests")
        
        if not digest_dir.exists():
            return []
        
        cutoff_date = now_utc()
        cutoff_date = cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_timestamp = cutoff_date.timestamp() - (days * 24 * 3600)
        
        # Track processed files to avoid duplicates
        processed_timestamps = set()
        
        # First pass: Process MD files with corresponding MP3s
        topic_pattern = create_topic_pattern()
        
        for md_file in digest_dir.glob("*_digest_*.md"):
            match = topic_pattern.match(md_file.name)
            if not match:
                continue
                
            topic, timestamp_str = match.groups()
            
            # Check if we have a corresponding MP3 file (prefer enhanced version)
            mp3_file = digest_dir / f"{topic}_digest_{timestamp_str}_enhanced.mp3"
            if not mp3_file.exists():
                mp3_file = digest_dir / f"{topic}_digest_{timestamp_str}.mp3"
                if not mp3_file.exists():
                    # Also check for old naming convention
                    mp3_file = digest_dir / f"complete_topic_digest_{timestamp_str}_enhanced.mp3"
                    if not mp3_file.exists():
                        mp3_file = digest_dir / f"complete_topic_digest_{timestamp_str}.mp3"
                        if not mp3_file.exists():
                            continue
            
            # Parse timestamp and filter by date
            try:
                file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                if file_date.timestamp() < cutoff_timestamp:
                    continue
            except ValueError:
                continue
            
            # Read content for AI-powered description
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Generate AI-powered summary
                    fallback_desc = self._extract_fallback_description(content, topic)
                    description = self.summary_generator.generate_summary(
                        content=content,
                        topic=topic,
                        timestamp=timestamp_str,
                        fallback_desc=fallback_desc
                    )
            except Exception as e:
                print(f"⚠️ Error reading content for {md_file.name}: {e}")
                description = f"Daily digest for {self.topic_config.get(topic, {}).get('display_name', topic)}"
            
            digest_files.append({
                'topic': topic,
                'timestamp': timestamp_str,
                'date': file_date,
                'md_file': md_file,
                'mp3_file': mp3_file,
                'content': content if 'content' in locals() else '',
                'description': description,
                'title': self._generate_episode_title(topic, file_date)
            })
            processed_timestamps.add(timestamp_str)
        
        # Second pass: Process MP3-only files (without MD files)
        topic_mp3_pattern, legacy_mp3_pattern = create_topic_mp3_patterns()
        mp3_patterns = [topic_mp3_pattern, legacy_mp3_pattern]
        
        for mp3_file in digest_dir.glob("*.mp3"):
            # Prioritize enhanced versions (skip non-enhanced if enhanced exists)
            if "_enhanced" not in mp3_file.name:
                # Check if enhanced version exists
                enhanced_path = mp3_file.parent / (mp3_file.stem + "_enhanced" + mp3_file.suffix)
                if enhanced_path.exists():
                    continue  # Skip non-enhanced if enhanced version exists
                
            timestamp_str = None
            topic = "general"  # default topic for complete_topic_digest files
            
            # Try to match patterns
            for i, pattern in enumerate(mp3_patterns):
                match = pattern.match(mp3_file.name)
                if match:
                    if i == 0:  # topic_digest pattern
                        topic, timestamp_str = match.groups()[:2]  # Ignore _enhanced group
                    else:  # complete_topic_digest pattern
                        timestamp_str = match.groups()[0]
                        topic = "general"
                    break
            
            if not timestamp_str or timestamp_str in processed_timestamps:
                continue
            
            # Parse timestamp and filter by date
            try:
                file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                if file_date.timestamp() < cutoff_timestamp:
                    continue
            except ValueError:
                continue
            
            # Generate enhanced description for MP3-only files
            topic_info = self.topic_config.get(topic, {})
            topic_display = topic_info.get('display_name', topic.replace('_', ' ').title())
            date_formatted = file_date.strftime('%B %d, %Y')
            description = f"{topic_display} digest from {date_formatted}. {topic_info.get('description', 'Covering the latest developments and insights.')}"
            
            digest_files.append({
                'topic': topic,
                'timestamp': timestamp_str,
                'date': file_date,
                'md_file': None,
                'mp3_file': mp3_file,
                'content': '',
                'description': description,
                'title': self._generate_episode_title(topic, file_date)
            })
            processed_timestamps.add(timestamp_str)
        
        # Sort by date (newest first)
        digest_files.sort(key=lambda x: x['date'], reverse=True)
        return digest_files
    
    def _extract_fallback_description(self, content: str, topic: str) -> str:
        """Extract a meaningful fallback description from digest content (used when AI generation fails)"""
        # Get first meaningful sentence, limit to ~200 chars
        sentences = content.replace('\n', ' ').replace('\r', ' ').split('. ')
        
        # Find the first substantial sentence (skip headers and short fragments)
        description = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 30 and not sentence.startswith('#'):
                description = sentence
                break
        
        # If no good sentence found, use first non-empty line
        if not description:
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            for line in lines:
                if len(line) > 20 and not line.startswith('#'):
                    description = line
                    break
        
        # Ensure reasonable length
        if len(description) > 200:
            description = description[:197] + "..."
        
        # Final fallback to topic-based description
        if len(description) < 20:
            topic_info = self.topic_config.get(topic, {})
            topic_display = topic_info.get('display_name', topic.replace('_', ' ').title())
            description = f"Daily {topic_display} digest covering the latest developments and insights"
        
        return description
    
    def _generate_episode_title(self, topic: str, date: datetime) -> str:
        """Generate episode title from topic and date with Weekly/Catch-up labels"""
        topic_info = self.topic_config.get(topic, {})
        display_name = topic_info.get('display_name', topic.replace('_', ' ').title())
        date_str = date.strftime('%B %d, %Y')
        
        # Add special labels based on publication day
        weekday = date.strftime('%A')
        if weekday == 'Friday':
            return f"{display_name} Weekly Digest - {date_str}"
        elif weekday == 'Monday':
            return f"{display_name} Catch-up Digest - {date_str}"
        else:
            return f"{display_name} - {date_str}"
    
    def _generate_episode_description(self, topic: str, date: datetime) -> str:
        """Generate episode description from topic and date with Weekly/Catch-up context"""
        topic_info = self.topic_config.get(topic, {})
        topic_display = topic_info.get('display_name', topic.replace('_', ' ').title())
        date_formatted = date.strftime('%B %d, %Y')
        base_description = topic_info.get('description', 'Covering the latest developments and insights.')
        
        # Add context based on publication day
        weekday = date.strftime('%A')
        if weekday == 'Friday':
            return f"Weekly {topic_display.lower()} digest from {date_formatted}. Comprehensive weekly overview of the most important developments. {base_description}"
        elif weekday == 'Monday':
            return f"Monday catch-up {topic_display.lower()} digest from {date_formatted}. Covering weekend and recent developments you may have missed. {base_description}"
        else:
            return f"{topic_display} digest from {date_formatted}. {base_description}"
    
    def _get_file_size(self, file_path: Path) -> int:
        """Get file size safely"""
        try:
            return file_path.stat().st_size
        except:
            return 0
    
    def _generate_stable_guid(self, topic: str, timestamp: str, date: datetime) -> str:
        """
        Generate stable GUID that doesn't change across regenerations for the same digest
        Format: {date}-{topic}-{hash(episode_ids)}
        """
        # Create a consistent identifier based on topic, date, and timestamp
        date_str = date.strftime('%Y-%m-%d')
        
        # Create a hash from the topic and timestamp for uniqueness
        # This ensures the same digest always gets the same GUID
        content_hash = hashlib.md5(f"{topic}_{timestamp}".encode()).hexdigest()[:8]
        
        # Create stable GUID in format: domain/date/topic/hash
        stable_guid = f"{self.base_url}/digest/{date_str}/{topic.lower().replace(' ', '-')}/{content_hash}"
        
        return stable_guid
    
    def _estimate_duration(self, file_size: int) -> int:
        """Estimate audio duration in seconds from file size (rough approximation)"""
        # Rough estimate: 1MB ≈ 1 minute for speech MP3
        duration_minutes = max(1, file_size // (1024 * 1024))
        return duration_minutes * 60
    
    def _validate_mp3_file(self, digest_info: Dict) -> bool:
        """Validate that MP3 file exists and has correct length"""
        try:
            # If using public URL (GitHub releases), assume it's valid
            if digest_info.get('public_url'):
                return True
            
            # Check local file exists
            mp3_file = digest_info.get('mp3_file')
            if not mp3_file or not Path(mp3_file).exists():
                print(f"⚠️ SKIP missing MP3: {mp3_file}")
                return False
            
            # Check file size is reasonable (> 100KB)
            file_size = Path(mp3_file).stat().st_size
            if file_size < 100 * 1024:  # 100KB minimum
                print(f"⚠️ SKIP small MP3: {mp3_file} ({file_size} bytes)")
                return False
            
            # Check if expected file_size matches (if available)
            expected_size = digest_info.get('file_size')
            if expected_size and abs(file_size - expected_size) > 1024:  # Allow 1KB difference
                print(f"⚠️ SKIP size mismatch: {mp3_file} (expected {expected_size}, got {file_size})")
                return False
            
            return True
        except Exception as e:
            print(f"⚠️ Error validating MP3 {digest_info.get('mp3_file', 'unknown')}: {e}")
            return False
    
    def generate_rss(self, output_file="daily-digest.xml", max_items=100) -> bool:
        """Generate complete RSS feed with all recent topic-specific episodes"""
        try:
            digest_files = self.find_digest_files()
            
            if not digest_files:
                print("⚠️  No digest files found for RSS generation")
                return False
            
            # Guardrail: Check if we have MP3s for today
            today = now_utc().date()
            today_mp3s = [d for d in digest_files if d['date'].date() == today and self._validate_mp3_file(d)]
            
            if not today_mp3s:
                print(f"RSS not updated: no new MP3s for {today}")
                return False
            
            print(f"✅ Found {len(today_mp3s)} valid MP3s for today: {today}")
            
            # Apply item cap (newest first, so we keep the most recent)
            if len(digest_files) > max_items:
                digest_files = digest_files[:max_items]
                print(f"📡 Applied RSS item cap: showing {max_items} of {len(digest_files)} available episodes")
            
            print(f"📡 Generating RSS feed with {len(digest_files)} episodes")
            
            # Create RSS root
            rss = Element('rss', version='2.0')
            rss.set('xmlns:itunes', 'http://www.itunes.com/dtds/podcast-1.0.dtd')
            rss.set('xmlns:content', 'http://purl.org/rss/1.0/modules/content/')
            
            # Channel element
            channel = SubElement(rss, 'channel')
            
            # Podcast metadata
            SubElement(channel, 'title').text = sanitize_xml_content(self.podcast_info['title'])
            SubElement(channel, 'description').text = sanitize_xml_content(self.podcast_info['description'])
            SubElement(channel, 'link').text = self.podcast_info['website']
            SubElement(channel, 'language').text = self.podcast_info['language']
            SubElement(channel, 'copyright').text = self.podcast_info['copyright']
            SubElement(channel, 'managingEditor').text = f"{self.podcast_info['email']} ({self.podcast_info['author']})"
            SubElement(channel, 'webMaster').text = f"{self.podcast_info['email']} ({self.podcast_info['author']})"
            SubElement(channel, 'lastBuildDate').text = now_utc().strftime('%a, %d %b %Y %H:%M:%S %z')
            
            # iTunes-specific tags
            SubElement(channel, 'itunes:author').text = sanitize_xml_content(self.podcast_info['author'])
            SubElement(channel, 'itunes:summary').text = sanitize_xml_content(self.podcast_info['description'])
            SubElement(channel, 'itunes:owner').text = self.podcast_info['author']
            SubElement(channel, 'itunes:image', href=self.podcast_info['artwork_url'])
            SubElement(channel, 'itunes:category', text=self.podcast_info['category'])
            SubElement(channel, 'itunes:explicit').text = 'no'
            
            # Add items for each digest file (with validation)
            items_added = 0
            for digest_info in digest_files:
                # Skip items with invalid MP3s
                if not self._validate_mp3_file(digest_info):
                    continue
                
                item = SubElement(channel, 'item')
                
                # Basic item info
                SubElement(item, 'title').text = sanitize_xml_content(digest_info['title'])
                SubElement(item, 'description').text = sanitize_xml_content(digest_info['description'])
                
                # Generate permalink and stable GUID
                permalink = f"{self.podcast_info['website']}/{digest_info['timestamp']}"
                stable_guid = self._generate_stable_guid(digest_info['topic'], digest_info['timestamp'], digest_info['date'])
                
                SubElement(item, 'link').text = permalink
                SubElement(item, 'guid').text = stable_guid
                
                # Publication date
                pub_date = digest_info['date'].replace(tzinfo=timezone.utc)
                SubElement(item, 'pubDate').text = pub_date.strftime('%a, %d %b %Y %H:%M:%S %z')
                
                # Audio enclosure - use deployment metadata URL if available
                if 'public_url' in digest_info and digest_info['public_url']:
                    # Use GitHub release URL from deployment metadata
                    audio_url = digest_info['public_url']
                    file_size = digest_info.get('file_size', 0)
                else:
                    # Fallback to audio base URL construction
                    file_size = self._get_file_size(digest_info['mp3_file'])
                    audio_url = f"{self.audio_base_url}/{digest_info['mp3_file'].name}"
                
                enclosure = SubElement(item, 'enclosure')
                enclosure.set('url', audio_url)
                enclosure.set('length', str(file_size))
                enclosure.set('type', 'audio/mpeg')
                
                items_added += 1
                
                # iTunes episode info
                SubElement(item, 'itunes:title').text = sanitize_xml_content(digest_info['title'])
                SubElement(item, 'itunes:summary').text = sanitize_xml_content(digest_info['description'])
                SubElement(item, 'itunes:duration').text = str(self._estimate_duration(file_size))
                
                # Topic-specific category
                topic_info = self.topic_config.get(digest_info['topic'], {})
                if 'category' in topic_info:
                    SubElement(item, 'itunes:keywords').text = topic_info['category']
            
            # Pretty-print XML
            rough_string = tostring(rss, 'utf-8')
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="  ")
            
            # Remove extra blank lines
            pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
            
            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
            
            print(f"✅ RSS feed generated: {output_file} with {items_added} valid items")
            
            # Show summary generation statistics
            try:
                stats = self.summary_generator.get_summary_stats()
                if stats.get('total_summaries', 0) > 0:
                    print(f"📊 Episode summaries: {stats['total_summaries']} cached, {stats['unique_topics']} topics")
                    if stats.get('topic_distribution'):
                        top_topics = list(stats['topic_distribution'].items())[:3]
                        topic_list = ", ".join([f"{topic} ({count})" for topic, count in top_topics])
                        print(f"🏷️  Top topics: {topic_list}")
            except Exception as e:
                print(f"⚠️ Could not retrieve summary stats: {e}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error generating RSS feed: {e}")
            return False


def main():
    """Generate RSS feed for multi-topic digests"""
    # Set up quiet logging for external libraries
    try:
        from utils.logging_setup import set_all_quiet
        set_all_quiet()
    except ImportError:
        pass
    
    generator = MultiTopicRSSGenerator()
    
    success = generator.generate_rss()
    if success:
        print("🎙️  Multi-topic RSS feed generation complete!")
    else:
        print("❌ RSS feed generation failed")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())