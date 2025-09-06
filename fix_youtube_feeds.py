#!/usr/bin/env python3
"""
Fix YouTube Feeds - Remove duplicates and invalid channel IDs
"""

import sqlite3
from urllib.parse import parse_qs, urlparse

import requests


def test_youtube_feed(channel_id):
    """Test if a YouTube channel ID works"""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        response = requests.get(url, timeout=10)
        return response.status_code == 200
    except:
        return False


def get_channel_id_from_url(url):
    """Extract channel ID from YouTube RSS URL"""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    return query_params.get("channel_id", [None])[0]


def main():
    # Get YouTube feeds from RSS database (source of truth)
    rss_conn = sqlite3.connect("podcast_monitor.db")
    rss_cursor = rss_conn.cursor()

    rss_cursor.execute(
        "SELECT title, url, topic_category FROM feeds WHERE type='youtube'"
    )
    rss_feeds = rss_cursor.fetchall()
    rss_conn.close()

    # Parse channel IDs from URLs
    working_feeds = []
    for title, url, topic_category in rss_feeds:
        channel_id = get_channel_id_from_url(url)
        if channel_id:
            working_feeds.append(
                {
                    "title": title,
                    "channel_id": channel_id,
                    "topic_category": topic_category or "technology",
                }
            )

    print(f"📊 Found {len(working_feeds)} YouTube feeds in RSS database")

    conn = sqlite3.connect("youtube_transcripts.db")
    cursor = conn.cursor()

    print("🧹 Cleaning up YouTube feeds...")

    # First, test all feeds
    print("\n📡 Testing YouTube channel IDs...")
    valid_feeds = []
    for feed in working_feeds:
        print(f"Testing {feed['title']} ({feed['channel_id']})...", end=" ")
        if test_youtube_feed(feed["channel_id"]):
            print("✅ Valid")
            valid_feeds.append(feed)
        else:
            print("❌ Invalid")

    print(f"\n✅ Found {len(valid_feeds)} working feeds")

    # Clear existing YouTube feeds
    cursor.execute("DELETE FROM feeds WHERE type = 'youtube'")
    print(f"🗑️  Removed old YouTube feeds")

    # Add clean feeds
    for feed in valid_feeds:
        url = (
            f"https://www.youtube.com/feeds/videos.xml?channel_id={feed['channel_id']}"
        )
        cursor.execute(
            """
            INSERT INTO feeds (url, title, type, topic_category, active)
            VALUES (?, ?, 'youtube', ?, 1)
        """,
            (url, feed["title"], feed["topic_category"]),
        )
        print(f"✅ Added: {feed['title']}")

    conn.commit()
    conn.close()

    print(f"\n🎉 YouTube feeds cleanup complete!")
    print(f"📊 Active YouTube feeds: {len(valid_feeds)}")


if __name__ == "__main__":
    main()
