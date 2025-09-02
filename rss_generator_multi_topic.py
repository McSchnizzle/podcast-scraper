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
from xml.dom import minidom
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Optional

class MultiTopicRSSGenerator:
    def __init__(self, db_path="podcast_monitor.db", base_url="https://paulrbrown.org"):
        self.db_path = db_path
        self.base_url = base_url
        self.audio_base_url = f"{base_url}/audio"
        
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
            "copyright": f"© {datetime.now().year} Paul Brown"
        }
    
    def find_digest_files(self, days=7) -> List[Dict]:
        """Find all topic-specific digest files from the last N days"""
        digest_files = []
        digest_dir = Path("daily_digests")
        
        if not digest_dir.exists():
            return []
        
        # Pattern for topic-specific digests: {topic}_digest_{timestamp}.md
        topic_pattern = re.compile(r'^([a-zA-Z_]+)_digest_(\d{8}_\d{6})\.md$')
        
        cutoff_date = datetime.now()
        cutoff_date = cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_timestamp = cutoff_date.timestamp() - (days * 24 * 3600)
        
        for md_file in digest_dir.glob("*_digest_*.md"):
            match = topic_pattern.match(md_file.name)
            if not match:
                continue
                
            topic, timestamp_str = match.groups()
            
            # Check if we have a corresponding MP3 file
            mp3_file = digest_dir / f"{topic}_digest_{timestamp_str}.mp3"
            if not mp3_file.exists():
                # Also check for old naming convention
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
            
            # Read content for description
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    description = self._extract_description(content, topic)
            except Exception:
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
        
        # Sort by date (newest first)
        digest_files.sort(key=lambda x: x['date'], reverse=True)
        return digest_files
    
    def _extract_description(self, content: str, topic: str) -> str:
        """Extract a meaningful description from digest content"""
        # Get first few sentences, limit to ~200 chars
        sentences = content.replace('\n', ' ').split('. ')
        description = sentences[0] if sentences else ""
        
        if len(description) > 200:
            description = description[:197] + "..."
        
        # Fallback to topic-based description
        if len(description) < 20:
            topic_info = self.topic_config.get(topic, {})
            description = topic_info.get('description', f"Daily digest covering {topic}")
        
        return description
    
    def _generate_episode_title(self, topic: str, date: datetime) -> str:
        """Generate episode title from topic and date"""
        topic_info = self.topic_config.get(topic, {})
        display_name = topic_info.get('display_name', topic.replace('_', ' ').title())
        date_str = date.strftime('%B %d, %Y')
        return f"{display_name} - {date_str}"
    
    def _get_file_size(self, file_path: Path) -> int:
        """Get file size safely"""
        try:
            return file_path.stat().st_size
        except:
            return 0
    
    def _estimate_duration(self, file_size: int) -> int:
        """Estimate audio duration in seconds from file size (rough approximation)"""
        # Rough estimate: 1MB ≈ 1 minute for speech MP3
        duration_minutes = max(1, file_size // (1024 * 1024))
        return duration_minutes * 60
    
    def generate_rss(self, output_file="daily-digest.xml") -> bool:
        """Generate complete RSS feed with all recent topic-specific episodes"""
        try:
            digest_files = self.find_digest_files()
            
            if not digest_files:
                print("⚠️  No digest files found for RSS generation")
                return False
            
            print(f"📡 Generating RSS feed with {len(digest_files)} episodes")
            
            # Create RSS root
            rss = Element('rss', version='2.0')
            rss.set('xmlns:itunes', 'http://www.itunes.com/dtds/podcast-1.0.dtd')
            rss.set('xmlns:content', 'http://purl.org/rss/1.0/modules/content/')
            
            # Channel element
            channel = SubElement(rss, 'channel')
            
            # Podcast metadata
            SubElement(channel, 'title').text = self.podcast_info['title']
            SubElement(channel, 'description').text = self.podcast_info['description']
            SubElement(channel, 'link').text = self.podcast_info['website']
            SubElement(channel, 'language').text = self.podcast_info['language']
            SubElement(channel, 'copyright').text = self.podcast_info['copyright']
            SubElement(channel, 'managingEditor').text = f"{self.podcast_info['email']} ({self.podcast_info['author']})"
            SubElement(channel, 'webMaster').text = f"{self.podcast_info['email']} ({self.podcast_info['author']})"
            SubElement(channel, 'lastBuildDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')
            
            # iTunes-specific tags
            SubElement(channel, 'itunes:author').text = self.podcast_info['author']
            SubElement(channel, 'itunes:summary').text = self.podcast_info['description']
            SubElement(channel, 'itunes:owner').text = self.podcast_info['author']
            SubElement(channel, 'itunes:image', href=self.podcast_info['artwork_url'])
            SubElement(channel, 'itunes:category', text=self.podcast_info['category'])
            SubElement(channel, 'itunes:explicit').text = 'no'
            
            # Add items for each digest file
            for digest_info in digest_files:
                item = SubElement(channel, 'item')
                
                # Basic item info
                SubElement(item, 'title').text = digest_info['title']
                SubElement(item, 'description').text = digest_info['description']
                
                # Generate permalink
                permalink = f"{self.podcast_info['website']}/{digest_info['timestamp']}"
                SubElement(item, 'link').text = permalink
                SubElement(item, 'guid').text = permalink
                
                # Publication date
                pub_date = digest_info['date'].replace(tzinfo=timezone.utc)
                SubElement(item, 'pubDate').text = pub_date.strftime('%a, %d %b %Y %H:%M:%S %z')
                
                # Audio enclosure
                file_size = self._get_file_size(digest_info['mp3_file'])
                audio_url = f"{self.audio_base_url}/{digest_info['mp3_file'].name}"
                
                enclosure = SubElement(item, 'enclosure')
                enclosure.set('url', audio_url)
                enclosure.set('length', str(file_size))
                enclosure.set('type', 'audio/mpeg')
                
                # iTunes episode info
                SubElement(item, 'itunes:title').text = digest_info['title']
                SubElement(item, 'itunes:summary').text = digest_info['description']
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
            
            print(f"✅ RSS feed generated: {output_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error generating RSS feed: {e}")
            return False


def main():
    """Generate RSS feed for multi-topic digests"""
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