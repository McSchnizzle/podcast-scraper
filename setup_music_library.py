#!/usr/bin/env python3
"""
Setup Music Library
Pre-generate master music files for all podcast topics to create a static music library
"""

import logging
import os
from pathlib import Path

from music_integration import MusicIntegrator
from utils.logging_setup import configure_logging

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

# All topics from the digest system
TOPICS = [
    "AI News",
    "Tech Product Releases",
    "Tech News and Tech Culture",
    "Community Organizing",
    "Social Justice",
    "Societal Culture Change",
]


def setup_static_music_library():
    """Pre-generate music files for all topics"""
    logger.info("🎵 Setting up static music library for all topics")
    logger.info("=" * 60)

    integrator = MusicIntegrator()

    # Check if ElevenLabs API is available
    if not integrator.elevenlabs_api_key:
        logger.warning("❌ ElevenLabs API key not available")
        logger.info("💡 You can still use static fallback music files")
        integrator.create_static_music_files()
        return

    total_generated = 0
    total_cached = 0

    for topic in TOPICS:
        logger.info(f"\n🎧 Processing topic: {topic}")

        # Generate master music (60 seconds)
        master_file = integrator.generate_master_music(topic, duration=60)

        if master_file:
            if "Generated master music" in str(master_file):
                total_generated += 1
                logger.info(f"  ✅ Generated new master music")
            else:
                total_cached += 1
                logger.info(f"  📻 Using cached master music")

            # Generate all segments (intro, background, outro)
            for music_type in ["intro", "background", "outro"]:
                segment_file = integrator.generate_music(topic, music_type)
                if segment_file:
                    logger.info(f"  ✅ {music_type.capitalize()}: Ready")
                else:
                    logger.warning(f"  ❌ {music_type.capitalize()}: Failed")
        else:
            logger.error(f"  ❌ Failed to generate master music for {topic}")

    # Create static fallback files
    integrator.create_static_music_files()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 MUSIC LIBRARY SETUP COMPLETE")
    logger.info("=" * 60)
    logger.info(f"🆕 New master files generated: {total_generated}")
    logger.info(f"📻 Cached files used: {total_cached}")
    logger.info(f"📁 Total topics processed: {len(TOPICS)}")

    # Check music cache directory
    music_cache = Path("music_cache")
    if music_cache.exists():
        master_files = list(music_cache.glob("*_master_*.mp3"))
        segment_files = (
            list(music_cache.glob("*_intro.mp3"))
            + list(music_cache.glob("*_background.mp3"))
            + list(music_cache.glob("*_outro.mp3"))
        )
        static_files = list(music_cache.glob("static_*.mp3"))

        logger.info(f"📄 Master files: {len(master_files)}")
        logger.info(f"📄 Segment files: {len(segment_files)}")
        logger.info(f"📄 Static fallback files: {len(static_files)}")

        total_size = sum(f.stat().st_size for f in music_cache.glob("*.mp3"))
        logger.info(f"💾 Total cache size: {total_size / (1024*1024):.1f} MB")

    logger.info("\n🎧 Your podcast system now has topic-specific music!")
    logger.info(
        "🚀 Future TTS generations will use these cached music files automatically."
    )


if __name__ == "__main__":
    setup_static_music_library()
