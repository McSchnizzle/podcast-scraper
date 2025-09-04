#!/usr/bin/env python3
"""
Restore feeds to database from config
One-time script to populate database with all configured feeds
"""

from config import Config

def main():
    """Restore all feeds to database"""
    config = Config()
    
    print("🔄 Restoring feeds to database...")
    config.sync_feeds_to_database(force_update=True)
    
    # Show active feeds
    feeds = config.get_active_feeds_from_db()
    print(f"\n📊 Database now has {len(feeds)} active feeds:")
    
    for feed in feeds:
        print(f"  {feed['id']:2d}. {feed['title']} ({feed['type']}) - {feed['topic_category']}")
    
    print("\n✅ Feed restoration complete!")
    print("The database is now the single source of truth for feed management.")

if __name__ == "__main__":
    main()