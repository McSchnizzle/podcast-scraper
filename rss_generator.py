#!/usr/bin/env python3
"""
RSS Feed Generator for Daily Podcast Digest
Generates podcatcher-compatible RSS XML with iTunes tags and Apple Podcasts optimization
"""

import os
import json
import sqlite3
from datetime import datetime, timezone
from utils.datetime_utils import now_utc
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import hashlib
from pathlib import Path

class PodcastRSSGenerator:
    def __init__(self, db_path="podcast_monitor.db", base_url="https://paulrbrown.org"):
        self.db_path = db_path
        self.base_url = base_url
        self.podcast_info = {
            "title": "Daily Tech Digest",
            "description": "AI-generated daily digest of tech news, product launches, and industry insights from leading podcasts and creators",
            "author": "Paul Brown",
            "email": "podcast@paulrbrown.org",
            "language": "en-US",
            "category": "Technology",
            "subcategory": "News",
            "artwork_url": f"{base_url}/podcast-artwork.jpg",
            "website": f"{base_url}/daily-digest",
            "copyright": f"© {now_utc().year} Paul Brown"
        }
    
    def get_recent_episodes(self, days=7):
        """Get digest episodes from the last 7 days"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            cursor = conn.cursor()
            
            # Get recent digests (look for complete topic digest files)
            digests = []
            digest_dir = Path("daily_digests")
            
            if digest_dir.exists():
                for file in digest_dir.glob("complete_topic_digest_*.mp3"):
                    # Extract timestamp from filename
                    timestamp_str = file.stem.replace("complete_topic_digest_", "")
                    try:
                        episode_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        
                        # Calculate age in days
                        age_days = (now_utc() - episode_date).days
                        
                        if age_days <= days:
                            file_size = file.stat().st_size
                            duration = self.estimate_duration_from_size(file_size)
                            
                            digests.append({
                                "file_path": str(file),
                                "filename": file.name,
                                "date": episode_date,
                                "size": file_size,
                                "duration": duration,
                                "title": f"Daily Tech Digest - {episode_date.strftime('%B %d, %Y')}",
                                "description": self.generate_episode_description(episode_date),
                                "guid": self.generate_guid(file.name),
                                "url": f"{self.base_url}/audio/{file.name}"
                            })
                    except ValueError:
                        continue
            
            # Sort by date descending (newest first)
            digests.sort(key=lambda x: x["date"], reverse=True)
            return digests
            
        finally:
            conn.close()
    
    def estimate_duration_from_size(self, size_bytes):
        """Estimate audio duration from MP3 file size (128kbps)"""
        # 128kbps = 16KB/s, typical compression
        estimated_seconds = size_bytes / (16 * 1024)
        return int(estimated_seconds)
    
    def generate_guid(self, filename):
        """Generate unique GUID for episode"""
        return hashlib.md5(f"{self.base_url}/{filename}".encode()).hexdigest()
    
    def generate_episode_description(self, episode_date):
        """Generate episode description with source attribution"""
        return f"""Daily digest of tech news and insights from leading podcasts and creators, covering AI tools, product launches, and industry developments. Generated on {episode_date.strftime('%B %d, %Y')} from multiple verified sources including The Vergecast, The AI Advantage, and How I AI.

This episode features cross-episode synthesis with topic-based organization, multi-voice narration, and actionable insights curated by AI analysis."""
    
    def format_duration(self, seconds):
        """Format duration as HH:MM:SS for iTunes"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def generate_rss_xml(self):
        """Generate complete RSS feed XML with iTunes compatibility"""
        episodes = self.get_recent_episodes()
        
        # Create RSS root element
        rss = Element("rss")
        rss.set("version", "2.0")
        rss.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
        rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
        
        channel = SubElement(rss, "channel")
        
        # Channel metadata
        title = SubElement(channel, "title")
        title.text = self.podcast_info["title"]
        
        description = SubElement(channel, "description")
        description.text = self.podcast_info["description"]
        
        link = SubElement(channel, "link")
        link.text = self.podcast_info["website"]
        
        language = SubElement(channel, "language")
        language.text = self.podcast_info["language"]
        
        copyright_elem = SubElement(channel, "copyright")
        copyright_elem.text = self.podcast_info["copyright"]
        
        # iTunes specific tags
        itunes_author = SubElement(channel, "itunes:author")
        itunes_author.text = self.podcast_info["author"]
        
        itunes_summary = SubElement(channel, "itunes:summary")
        itunes_summary.text = self.podcast_info["description"]
        
        itunes_owner = SubElement(channel, "itunes:owner")
        owner_name = SubElement(itunes_owner, "itunes:name")
        owner_name.text = self.podcast_info["author"]
        owner_email = SubElement(itunes_owner, "itunes:email") 
        owner_email.text = self.podcast_info["email"]
        
        itunes_image = SubElement(channel, "itunes:image")
        itunes_image.set("href", self.podcast_info["artwork_url"])
        
        itunes_category = SubElement(channel, "itunes:category")
        itunes_category.set("text", self.podcast_info["category"])
        itunes_subcategory = SubElement(itunes_category, "itunes:category")
        itunes_subcategory.set("text", self.podcast_info["subcategory"])
        
        itunes_explicit = SubElement(channel, "itunes:explicit")
        itunes_explicit.text = "false"
        
        # Atom self-link
        atom_link = SubElement(channel, "atom:link")
        atom_link.set("href", f"{self.base_url}/daily-digest.xml")
        atom_link.set("rel", "self")
        atom_link.set("type", "application/rss+xml")
        
        # Publication date
        pub_date = SubElement(channel, "pubDate")
        pub_date.text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        
        # Add episodes
        for episode in episodes:
            item = SubElement(channel, "item")
            
            item_title = SubElement(item, "title")
            item_title.text = episode["title"]
            
            item_description = SubElement(item, "description")
            item_description.text = episode["description"]
            
            item_pub_date = SubElement(item, "pubDate")
            item_pub_date.text = episode["date"].strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            # Enclosure (audio file)
            enclosure = SubElement(item, "enclosure")
            enclosure.set("url", episode["url"])
            enclosure.set("type", "audio/mpeg")
            enclosure.set("length", str(episode["size"]))
            
            # GUID
            guid = SubElement(item, "guid")
            guid.text = episode["guid"]
            guid.set("isPermaLink", "false")
            
            # iTunes episode tags
            itunes_title = SubElement(item, "itunes:title")
            itunes_title.text = episode["title"]
            
            itunes_summary = SubElement(item, "itunes:summary")
            itunes_summary.text = episode["description"]
            
            itunes_duration = SubElement(item, "itunes:duration")
            itunes_duration.text = self.format_duration(episode["duration"])
            
            itunes_episode_type = SubElement(item, "itunes:episodeType")
            itunes_episode_type.text = "full"
        
        return rss
    
    def generate_feed_file(self, output_path="daily-digest.xml"):
        """Generate RSS feed file"""
        rss_xml = self.generate_rss_xml()
        
        # Pretty print XML
        xml_str = minidom.parseString(tostring(rss_xml)).toprettyxml(indent="  ")
        
        # Remove empty lines
        xml_lines = [line for line in xml_str.split('\n') if line.strip()]
        xml_content = '\n'.join(xml_lines)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        return output_path
    
    def validate_feed(self, xml_path):
        """Basic RSS feed validation"""
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Check required elements
            channel = root.find("channel")
            if channel is None:
                return False, "Missing channel element"
            
            required_elements = ["title", "description", "link"]
            for elem in required_elements:
                if channel.find(elem) is None:
                    return False, f"Missing required element: {elem}"
            
            # Check for episodes
            items = channel.findall("item")
            if len(items) == 0:
                return False, "No episodes found"
            
            return True, f"Valid RSS feed with {len(items)} episodes"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

def main():
    """Generate RSS feed for daily podcast digest"""
    generator = PodcastRSSGenerator()
    
    print("Generating RSS feed...")
    episodes = generator.get_recent_episodes()
    print(f"Found {len(episodes)} episodes from last 7 days")
    
    if episodes:
        feed_path = generator.generate_feed_file()
        print(f"RSS feed generated: {feed_path}")
        
        # Validate feed
        valid, message = generator.validate_feed(feed_path)
        if valid:
            print(f"✅ Feed validation: {message}")
        else:
            print(f"❌ Feed validation failed: {message}")
    else:
        print("No episodes found to include in feed")

if __name__ == "__main__":
    main()