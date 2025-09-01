#!/usr/bin/env python3
"""
Feed Management CLI
Easy command-line interface for managing podcast feeds
"""

import argparse
from config import Config

def list_feeds():
    """List all active feeds"""
    config = Config()
    feeds = config.get_active_feeds_from_db()
    
    print(f"\n📊 Active Feeds ({len(feeds)} total):")
    print("=" * 60)
    print("Note: Categories are informational only. Content selection is based on AI relevance scoring.")
    
    if not feeds:
        print("No feeds configured.")
        return
    
    # Group by category
    categories = {}
    for feed in feeds:
        category = feed['topic_category'] or "general"
        if category not in categories:
            categories[category] = []
        categories[category].append(feed)
    
    for category, category_feeds in sorted(categories.items()):
        print(f"\n🏷️  {category.upper()} (informational):")
        for feed in category_feeds:
            feed_type_emoji = "📺" if feed['type'] == 'youtube' else "📻"
            print(f"  {feed['id']:2d}. {feed_type_emoji} {feed['title']}")

def add_feed():
    """Interactive feed addition"""
    config = Config()
    
    print("\n➕ Add New Feed")
    print("=" * 30)
    
    # Get feed details
    title = input("Feed title: ").strip()
    url = input("Feed URL: ").strip()
    
    # Determine type
    if 'youtube.com' in url:
        feed_type = 'youtube'
    elif url.endswith('.rss') or 'rss' in url or url.startswith('https://feeds.'):
        feed_type = 'rss'
    else:
        feed_type = input("Feed type (rss/youtube): ").strip().lower()
    
    # Get category (informational only - selection is now 100% score-based)
    print("\nTopic categories are informational only. Content selection is based on AI relevance scoring.")
    print("Available categories: technology, business, philosophy, politics, culture")
    topic_category = input("Topic category (optional): ").strip().lower() or "general"
    
    # Confirm
    print(f"\n📋 Review:")
    print(f"Title: {title}")
    print(f"URL: {url}")
    print(f"Type: {feed_type}")
    print(f"Category: {topic_category} (informational only)")
    print("\nNote: Episodes will be selected for digests based on AI-powered relevance scoring, not category.")
    
    if input("\nAdd this feed? (y/N): ").lower() == 'y':
        if config.add_feed_to_db(url, title, feed_type, topic_category):
            print("✅ Feed added successfully!")
        else:
            print("❌ Failed to add feed")

def remove_feed():
    """Interactive feed removal"""
    config = Config()
    
    # List current feeds
    list_feeds()
    
    print("\n➖ Remove Feed")
    print("=" * 30)
    
    try:
        feed_id = int(input("Enter feed ID to remove: "))
        
        if input(f"Remove feed ID {feed_id}? (y/N): ").lower() == 'y':
            if config.remove_feed_from_db(feed_id):
                print("✅ Feed removed successfully!")
            else:
                print("❌ Failed to remove feed")
    except ValueError:
        print("Invalid feed ID")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Manage podcast feeds")
    parser.add_argument('action', choices=['list', 'add', 'remove'], 
                       help='Action to perform')
    
    args = parser.parse_args()
    
    if args.action == 'list':
        list_feeds()
    elif args.action == 'add':
        add_feed()
    elif args.action == 'remove':
        remove_feed()

if __name__ == "__main__":
    main()