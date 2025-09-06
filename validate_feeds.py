#!/usr/bin/env python3
"""
Feed Validation Script
Validates all feeds in the database and reports any issues
"""

import sqlite3

from config import config
from utils.db import get_connection


def validate_all_feeds():
    """Validate all active feeds in the database"""
    print("🔍 Validating all feeds in database...")

    conn = get_connection("podcast_monitor.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, title, url, type FROM feeds
        WHERE active = 1
        ORDER BY title
    """
    )

    feeds = cursor.fetchall()
    conn.close()

    valid_count = 0
    invalid_count = 0

    for feed_id, title, url, feed_type in feeds:
        print(f"\n📡 Testing: {title} ({feed_type})")
        print(f"   URL: {url}")

        is_valid, message = config.validate_feed_url(url)

        if is_valid:
            print(f"   ✅ {message}")
            valid_count += 1
        else:
            print(f"   ❌ {message}")
            invalid_count += 1

    print(f"\n📊 Validation Summary:")
    print(f"   ✅ Valid feeds: {valid_count}")
    print(f"   ❌ Invalid feeds: {invalid_count}")
    print(f"   📈 Success rate: {valid_count/(valid_count+invalid_count)*100:.1f}%")

    return valid_count, invalid_count


def cleanup_broken_feeds():
    """Remove feeds that fail validation"""
    print("\n🧹 Checking for broken feeds to remove...")

    conn = get_connection("podcast_monitor.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, title, url FROM feeds
        WHERE active = 1
    """
    )

    feeds = cursor.fetchall()
    broken_feeds = []

    for feed_id, title, url in feeds:
        is_valid, message = config.validate_feed_url(url)
        if not is_valid:
            broken_feeds.append((feed_id, title, url, message))

    if broken_feeds:
        print(f"Found {len(broken_feeds)} broken feeds:")
        for feed_id, title, url, error in broken_feeds:
            print(f"  ❌ {title}: {error}")
            cursor.execute("UPDATE feeds SET active = 0 WHERE id = ?", (feed_id,))

        conn.commit()
        print(f"✅ Deactivated {len(broken_feeds)} broken feeds")
    else:
        print("✅ No broken feeds found!")

    conn.close()


if __name__ == "__main__":
    valid, invalid = validate_all_feeds()

    if invalid > 0:
        response = input("\n❓ Remove broken feeds from active feeds? (y/N): ")
        if response.lower() in ["y", "yes"]:
            cleanup_broken_feeds()

    print("\n🎉 Feed validation complete!")
