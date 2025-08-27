"""
Vercel Function: RSS Feed Generator  
Serves RSS feed for Daily Tech Digest podcast
Optimized for Android/Google Podcasts/Spotify compatibility
"""

import os
import json
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import hashlib
from http.server import BaseHTTPRequestHandler

class PodcastRSSAPI:
    def __init__(self):
        # Use environment variable or default
        self.base_url = os.environ.get('VERCEL_URL', 'https://paulrbrown.org')
        if not self.base_url.startswith('http'):
            self.base_url = f'https://{self.base_url}'
            
        self.podcast_info = {
            "title": "Daily Tech Digest",
            "description": "AI-generated daily digest of tech news, product launches, and industry insights from leading podcasts and creators",
            "author": "Paul Brown", 
            "email": "podcast@paulrbrown.org",
            "language": "en-US",
            "category": "Technology",
            "artwork_url": f"{self.base_url}/podcast-artwork.jpg",
            "website": f"{self.base_url}/daily-digest",
            "copyright": f"© {datetime.now().year} Paul Brown"
        }
    
    def get_episode_metadata(self):
        """Get episode metadata - this would be populated by GitHub Actions"""
        # In production, this would read from a JSON file uploaded by GitHub Actions
        # For now, return sample episode
        episodes = [
            {
                "title": "Daily Tech Digest - August 27, 2024",
                "description": "Today's digest covers AI tool launches, creative applications, and social commentary from leading tech podcasts.",
                "date": datetime.now(timezone.utc),
                "filename": "complete_topic_digest_20250827_112404.mp3",
                "size": 10485760,  # ~10MB
                "duration": 3600,  # 1 hour
                "guid": hashlib.md5("complete_topic_digest_20250827_112404.mp3".encode()).hexdigest(),
                "url": f"{self.base_url}/audio/complete_topic_digest_20250827_112404.mp3"
            }
        ]
        return episodes
    
    def format_duration(self, seconds):
        """Format duration as HH:MM:SS for iTunes"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def generate_rss_xml(self):
        """Generate RSS XML feed"""
        episodes = self.get_episode_metadata()
        
        # Create RSS root - simplified for Android/Spotify
        rss = Element("rss")
        rss.set("version", "2.0")
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
        
        # Managing editor
        editor = SubElement(channel, "managingEditor")
        editor.text = f"{self.podcast_info['email']} ({self.podcast_info['author']})"
        
        # Image
        image = SubElement(channel, "image")
        image_url = SubElement(image, "url")
        image_url.text = self.podcast_info["artwork_url"]
        image_title = SubElement(image, "title")
        image_title.text = self.podcast_info["title"]
        image_link = SubElement(image, "link")
        image_link.text = self.podcast_info["website"]
        
        # Atom self-link
        atom_link = SubElement(channel, "atom:link")
        atom_link.set("href", f"{self.base_url}/daily-digest.xml")
        atom_link.set("rel", "self") 
        atom_link.set("type", "application/rss+xml")
        
        # Episodes
        for episode in episodes:
            item = SubElement(channel, "item")
            
            item_title = SubElement(item, "title")
            item_title.text = episode["title"]
            
            item_description = SubElement(item, "description")
            item_description.text = episode["description"]
            
            item_pub_date = SubElement(item, "pubDate")
            item_pub_date.text = episode["date"].strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            enclosure = SubElement(item, "enclosure")
            enclosure.set("url", episode["url"])
            enclosure.set("type", "audio/mpeg")
            enclosure.set("length", str(episode["size"]))
            
            guid = SubElement(item, "guid")
            guid.text = episode["guid"]
            guid.set("isPermaLink", "false")
            
            # Duration for podcast apps
            duration = SubElement(item, "duration") 
            duration.text = self.format_duration(episode["duration"])
        
        return rss

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET request for RSS feed"""
        try:
            rss_generator = PodcastRSSAPI()
            rss_xml = rss_generator.generate_rss_xml()
            
            # Convert to string
            xml_str = minidom.parseString(tostring(rss_xml)).toprettyxml(indent="  ")
            xml_lines = [line for line in xml_str.split('\n') if line.strip()]
            xml_content = '\n'.join(xml_lines)
            
            # Set headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/rss+xml; charset=utf-8')
            self.send_header('Cache-Control', 'public, max-age=3600')  # Cache for 1 hour
            self.end_headers()
            
            # Send XML
            self.wfile.write(xml_content.encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error generating RSS feed: {str(e)}".encode('utf-8'))