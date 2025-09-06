#!/usr/bin/env python3
"""
Production-Hardened RSS Generator

Addresses critical production issues:
1. Environment-driven base URLs
2. Content-based stable GUIDs
3. UTC timezone consistency
4. Enhanced security validation
5. RSS specification conformance
"""

import logging
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import production configuration
from config.production import (
    format_rss_date,
    get_stable_guid,
    get_utc_now,
    production_config,
)
from utils.db import get_connection
from utils.sanitization import (
    create_topic_file_pattern,
    sanitize_filename,
    sanitize_xml_content,
)

logger = logging.getLogger(__name__)

# Import episode summary generator conditionally
try:
    from episode_summary_generator import EpisodeSummaryGenerator
except ImportError:
    logger.warning("⚠️ Episode summary generator not available")
    EpisodeSummaryGenerator = None


class ProductionRSSGenerator:
    """Production-hardened RSS generator with environment-driven configuration"""

    def __init__(self, db_path: str = "podcast_monitor.db"):
        self.db_path = db_path
        self.config = production_config

        # Initialize episode summary generator if available
        if EpisodeSummaryGenerator:
            self.episode_summary_generator = EpisodeSummaryGenerator()
        else:
            self.episode_summary_generator = None

        logger.info(f"🏭 Production RSS Generator initialized")
        logger.info(f"  Database: {db_path}")
        logger.info(f"  Base URL: {self.config.PODCAST_BASE_URL}")
        logger.info(f"  Audio URL: {self.config.AUDIO_BASE_URL}")

    def generate_rss(
        self, output_file: str = "daily-digest.xml", max_items: int = 100
    ) -> bool:
        """Generate RSS feed with production hardening"""

        try:
            # Get digest information
            digest_episodes = self._get_digest_episodes(max_items)

            if not digest_episodes:
                logger.warning("⚠️ No digest episodes found for RSS generation")
                return False

            # Create RSS XML structure
            rss_root = self._create_rss_structure()
            channel = rss_root.find("channel")

            # Add channel metadata
            self._add_channel_metadata(channel)

            # Add episodes to RSS
            episodes_added = 0
            for episode_info in digest_episodes:
                try:
                    if self._add_episode_to_rss(channel, episode_info):
                        episodes_added += 1
                except Exception as e:
                    logger.error(
                        f"❌ Failed to add episode {episode_info.get('topic', 'unknown')}: {e}"
                    )
                    continue

            if episodes_added == 0:
                logger.error("❌ No episodes successfully added to RSS feed")
                return False

            # Write RSS file atomically
            return self._write_rss_file(rss_root, output_file)

        except Exception as e:
            logger.error(f"❌ RSS generation failed: {e}")
            return False

    def _get_digest_episodes(self, max_items: int) -> List[Dict[str, Any]]:
        """Get digest episodes from database and filesystem"""

        digest_episodes = []

        # Scan daily_digests directory for recent digest files
        daily_digests_dir = Path("daily_digests")
        if not daily_digests_dir.exists():
            logger.warning("⚠️ daily_digests directory not found")
            return []

        # Get all digest files (both .md and .mp3)
        digest_files = {}
        for file_path in daily_digests_dir.iterdir():
            if file_path.is_file():
                # Extract topic and timestamp from filename
                topic_file_pattern = create_topic_file_pattern()
                match = topic_file_pattern.match(file_path.name)
                if match:
                    topic, timestamp_str, file_type = match.groups()

                    # Create unique key for this digest
                    digest_key = f"{topic}_{timestamp_str}"

                    if digest_key not in digest_files:
                        digest_files[digest_key] = {
                            "topic": topic.replace("_", " ").title(),
                            "timestamp": timestamp_str,
                            "files": {},
                        }

                    digest_files[digest_key]["files"][file_type] = file_path

        # Process digest files and create episode info
        cutoff_date = get_utc_now() - timedelta(days=30)  # Last 30 days

        for digest_key, digest_data in digest_files.items():
            try:
                # Parse timestamp
                file_date = datetime.strptime(digest_data["timestamp"], "%Y%m%d_%H%M%S")
                file_date = file_date.replace(tzinfo=timezone.utc)

                # Skip old files
                if file_date < cutoff_date:
                    continue

                # Check for required files
                if "mp3" not in digest_data["files"]:
                    logger.warning(f"⚠️ No MP3 file found for {digest_key}")
                    continue

                mp3_file = digest_data["files"]["mp3"]

                # Get file size
                file_size = mp3_file.stat().st_size

                # Get episode IDs for stable GUID generation
                episode_ids = self._get_episode_ids_for_digest(
                    digest_data["topic"], file_date
                )

                # Generate stable GUID based on content, not runtime
                stable_guid = get_stable_guid(
                    digest_data["topic"], episode_ids, file_date
                )

                # Generate episode summary
                episode_summary = self._generate_episode_summary(digest_data, mp3_file)

                # Create episode info
                episode_info = {
                    "topic": digest_data["topic"],
                    "timestamp": digest_data["timestamp"],
                    "date": file_date,
                    "mp3_file": mp3_file,
                    "file_size": file_size,
                    "guid": stable_guid,
                    "title": self._generate_episode_title(
                        digest_data["topic"], file_date
                    ),
                    "description": episode_summary,
                    "link": self.config.get_episode_link(digest_data["timestamp"]),
                    "audio_url": self.config.get_audio_url(mp3_file.name),
                    "duration": self._estimate_duration(file_size),
                    "keywords": self._get_episode_keywords(digest_data["topic"]),
                }

                digest_episodes.append(episode_info)

            except Exception as e:
                logger.error(f"❌ Error processing digest {digest_key}: {e}")
                continue

        # Sort by date (newest first) and limit
        digest_episodes.sort(key=lambda x: x["date"], reverse=True)
        digest_episodes = digest_episodes[:max_items]

        logger.info(f"📡 Found {len(digest_episodes)} digest episodes for RSS")

        return digest_episodes

    def _get_episode_ids_for_digest(self, topic: str, date: datetime) -> List[str]:
        """Get episode IDs that were used in a specific digest for stable GUID generation"""

        # This would ideally query the database for episodes that were included in the digest
        # For now, we'll use a date-based approach to get consistent episode IDs

        try:
            # Query both podcast_monitor.db and youtube_transcripts.db
            episode_ids = []

            for db_name in ["podcast_monitor.db", "youtube_transcripts.db"]:
                if Path(db_name).exists():
                    with get_connection(db_name) as conn:
                        cursor = conn.cursor()

                        # Get episodes from the same day that were digested
                        cursor.execute(
                            """
                            SELECT episode_id FROM episodes
                            WHERE status = 'digested'
                            AND date(created_at) = date(?)
                            ORDER BY episode_id
                        """,
                            (date.date(),),
                        )

                        db_episode_ids = [row[0] for row in cursor.fetchall()]
                        episode_ids.extend(db_episode_ids)

            return sorted(
                list(set(episode_ids))
            )  # Remove duplicates and sort for consistency

        except Exception as e:
            logger.warning(f"⚠️ Could not get episode IDs for stable GUID: {e}")
            # Fallback to topic and date for consistency
            return [f"{topic.lower().replace(' ', '_')}_{date.strftime('%Y%m%d')}"]

    def _create_rss_structure(self) -> ET.Element:
        """Create basic RSS XML structure"""

        rss = ET.Element("rss")
        rss.set("version", "2.0")
        rss.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

        channel = ET.SubElement(rss, "channel")

        return rss

    def _add_channel_metadata(self, channel: ET.Element):
        """Add channel metadata with production configuration"""

        channel_info = self.config.get_rss_channel_info()

        # Basic channel information
        ET.SubElement(channel, "title").text = sanitize_xml_content(
            channel_info["title"]
        )
        ET.SubElement(channel, "description").text = sanitize_xml_content(
            channel_info["description"]
        )
        ET.SubElement(channel, "link").text = channel_info["link"]
        ET.SubElement(channel, "language").text = channel_info["language"]
        ET.SubElement(channel, "copyright").text = sanitize_xml_content(
            channel_info["copyright"]
        )
        ET.SubElement(channel, "managingEditor").text = channel_info["managing_editor"]
        ET.SubElement(channel, "webMaster").text = channel_info["webmaster"]

        # Last build date in UTC
        ET.SubElement(channel, "lastBuildDate").text = format_rss_date()

        # iTunes-specific tags
        ET.SubElement(
            channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}author"
        ).text = channel_info["author"]
        ET.SubElement(
            channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}summary"
        ).text = sanitize_xml_content(channel_info["summary"])
        ET.SubElement(
            channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}owner"
        ).text = channel_info["owner"]

        # iTunes image
        itunes_image = ET.SubElement(
            channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}image"
        )
        itunes_image.set("href", channel_info["artwork_url"])

        # iTunes category
        itunes_category = ET.SubElement(
            channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}category"
        )
        itunes_category.set("text", channel_info["category"])

        # iTunes explicit
        ET.SubElement(
            channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}explicit"
        ).text = channel_info["explicit"]

        # Atom self link
        atom_link = ET.SubElement(channel, "{http://www.w3.org/2005/Atom}link")
        atom_link.set("rel", "self")
        atom_link.set("type", "application/rss+xml")
        atom_link.set("href", channel_info["feed_url"])

    def _add_episode_to_rss(
        self, channel: ET.Element, episode_info: Dict[str, Any]
    ) -> bool:
        """Add single episode to RSS feed"""

        try:
            item = ET.SubElement(channel, "item")

            # Title with XML safety
            title_text = sanitize_xml_content(episode_info["title"])
            ET.SubElement(item, "title").text = title_text

            # Description with length limits
            description_text = sanitize_xml_content(
                episode_info["description"][: self.config.MAX_XML_CONTENT_LENGTH]
            )
            ET.SubElement(item, "description").text = description_text

            # Link and GUID
            ET.SubElement(item, "link").text = episode_info["link"]

            # GUID with isPermaLink=false for RSS spec conformance
            guid_elem = ET.SubElement(item, "guid")
            guid_elem.set("isPermaLink", "false")
            guid_elem.text = episode_info["guid"]

            # Publication date in UTC
            ET.SubElement(item, "pubDate").text = format_rss_date(episode_info["date"])

            # Enclosure with accurate file size
            enclosure = ET.SubElement(item, "enclosure")
            enclosure.set("url", episode_info["audio_url"])
            enclosure.set("length", str(episode_info["file_size"]))
            enclosure.set("type", "audio/mpeg")

            # iTunes-specific tags
            ET.SubElement(
                item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}title"
            ).text = title_text
            ET.SubElement(
                item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}summary"
            ).text = description_text
            ET.SubElement(
                item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}duration"
            ).text = str(episode_info["duration"])
            ET.SubElement(
                item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}keywords"
            ).text = episode_info["keywords"]

            return True

        except Exception as e:
            logger.error(f"❌ Error adding episode to RSS: {e}")
            return False

    def _generate_episode_title(self, topic: str, date: datetime) -> str:
        """Generate episode title with weekday awareness"""

        weekday_label = self.config.get_weekday_label(date)
        formatted_date = date.strftime("%B %d, %Y")

        return f"{topic} - {formatted_date}"

    def _generate_episode_summary(self, digest_data: Dict, mp3_file: Path) -> str:
        """Generate episode summary using AI if available"""

        try:
            # Try to read markdown file for content
            md_file = digest_data["files"].get("md")
            if md_file and md_file.exists():
                content = md_file.read_text()

                # Use AI to generate summary if available
                if self.episode_summary_generator:
                    summary = self.episode_summary_generator.generate_summary(
                        content=content,
                        topic=digest_data["topic"],
                        timestamp=digest_data["timestamp"],
                    )

                    if summary and len(summary) > 50:
                        return summary

        except Exception as e:
            logger.warning(f"⚠️ Could not generate AI summary: {e}")

        # Fallback to generic summary
        return f"In this episode, we explore {digest_data['topic'].lower()} including key developments, insights, and analysis from leading voices in the field."

    def _estimate_duration(self, file_size: int) -> int:
        """Estimate audio duration from file size"""

        # Rough estimate: 1MB ≈ 1 minute for speech MP3 at typical bitrates
        duration_minutes = max(1, file_size // (1024 * 1024))
        return duration_minutes * 60  # Return in seconds

    def _get_episode_keywords(self, topic: str) -> str:
        """Get keywords for episode based on topic"""

        keyword_map = {
            "AI News": "Technology/AI",
            "Tech Product Releases": "Technology/Products",
            "Tech News and Tech Culture": "Technology/Culture",
            "Community Organizing": "Society/Community",
            "Social Justice": "Society/Justice",
            "Societal Culture Change": "Society/Culture",
        }

        return keyword_map.get(topic, "Technology/General")

    def _write_rss_file(self, rss_root: ET.Element, output_file: str) -> bool:
        """Write RSS file atomically"""

        try:
            # Create temporary file first
            temp_file = f"{output_file}.tmp"

            # Format XML with proper indentation
            self._indent_xml(rss_root)

            # Create XML tree and write to temp file
            tree = ET.ElementTree(rss_root)
            tree.write(temp_file, encoding="utf-8", xml_declaration=True)

            # Atomic move to final location
            Path(temp_file).rename(output_file)

            logger.info(f"✅ RSS feed generated: {output_file}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to write RSS file: {e}")
            # Clean up temp file
            try:
                Path(f"{output_file}.tmp").unlink(missing_ok=True)
            except:
                pass
            return False

    def _indent_xml(self, elem: ET.Element, level: int = 0):
        """Add proper indentation to XML"""

        indent = "  " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = f"\n{indent}  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = f"\n{indent}"
            for subelem in elem:
                self._indent_xml(subelem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = f"\n{indent}"
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = f"\n{indent}"


def main():
    """Test RSS generation"""

    generator = ProductionRSSGenerator()
    success = generator.generate_rss("daily-digest-production.xml")

    if success:
        print("✅ Production RSS feed generated successfully")
    else:
        print("❌ Production RSS feed generation failed")


if __name__ == "__main__":
    main()
