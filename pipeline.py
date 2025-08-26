#!/usr/bin/env python3
"""
Integrated Content Processing Pipeline
Orchestrates feed monitoring, content processing, and analysis
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Import our modules
from feed_monitor import FeedMonitor
from content_processor import ContentProcessor
from content_analyzer import ContentAnalyzer

class PipelineOrchestrator:
    def __init__(self, db_path="podcast_monitor.db"):
        self.db_path = db_path
        self.feed_monitor = FeedMonitor(db_path)
        self.processor = ContentProcessor(db_path)
        self.analyzer = ContentAnalyzer(db_path)
    
    def run_daily_pipeline(self, hours_back=24, min_priority=0.4):
        """Run the complete daily content processing pipeline"""
        print("🚀 Starting Daily Podcast Digest Pipeline")
        print("=" * 50)
        
        # Step 1: Check for new episodes
        print("📡 Checking for new episodes...")
        new_episodes = self.feed_monitor.check_new_episodes(hours_back)
        
        if not new_episodes:
            print("No new episodes found in the last 24 hours")
            return None
        
        print(f"Found {len(new_episodes)} new episodes")
        
        # Step 2: Process all pending episodes
        print("\n🔄 Processing episode content...")
        processing_results = self.processor.process_all_pending()
        
        if not processing_results:
            print("No episodes were successfully processed")
            return None
        
        print(f"Successfully processed {len(processing_results)} episodes")
        
        # Step 3: Generate daily digest content
        print("\n📊 Analyzing content for daily digest...")
        digest_content = self.analyzer.get_daily_digest_content(min_priority)
        
        # Step 4: Show results summary
        self._print_pipeline_summary(digest_content)
        
        return digest_content
    
    def _print_pipeline_summary(self, digest_content):
        """Print summary of pipeline results"""
        print("\n" + "=" * 50)
        print("📋 DAILY DIGEST SUMMARY")
        print("=" * 50)
        
        if not digest_content['episodes']:
            print("❌ No high-priority content found for today's digest")
            return
        
        episodes = digest_content['episodes']
        cross_refs = digest_content['cross_references']
        summary = digest_content['summary']
        
        print(f"✅ {len(episodes)} high-priority episodes ready for digest")
        
        # Show top episodes by category
        episodes_by_category = {}
        for ep in episodes:
            category = ep[5]  # topic_category
            if category not in episodes_by_category:
                episodes_by_category[category] = []
            episodes_by_category[category].append(ep)
        
        for category, eps in episodes_by_category.items():
            print(f"\n📂 {category.upper()} ({len(eps)} episodes):")
            for ep in eps[:3]:  # Show top 3 per category
                title, priority, content_type, feed_title = ep[1], ep[2], ep[3], ep[4]
                print(f"  🎯 {title}")
                print(f"     Priority: {priority:.2f} | Type: {content_type}")
                print(f"     Source: {feed_title}")
        
        # Show cross-references
        if cross_refs:
            print(f"\n🔗 CROSS-REFERENCES ({len(cross_refs)} topics):")
            for ref in cross_refs[:3]:  # Show top 3
                topic = ref['topic']
                count = ref['episode_count'] 
                strength = ref['strength']
                categories = ', '.join(ref['categories'])
                print(f"  🌐 {topic}")
                print(f"     Appears in {count} episodes | Strength: {strength:.2f}")
                print(f"     Categories: {categories}")
        
        # Show aggregate stats
        if summary:
            print(f"\n📈 AGGREGATE STATS:")
            print(f"  Total Episodes: {summary['episode_count']}")
            print(f"  Average Priority: {summary['average_priority']:.2f}")
            print(f"  Unique Topics: {summary['total_topics']}")
            print(f"  Generated: {summary['generated_at']}")

def setup_test_feeds():
    """Set up test feeds for development"""
    monitor = FeedMonitor()
    
    print("Setting up test feeds...")
    
    # Add some test feeds
    test_feeds = [
        # Tech News
        ("https://feeds.theverge.com/theverge/index.xml", "tech_news", "The Verge"),
        ("https://feeds.feedburner.com/oreilly/radar", "tech_news", "O'Reilly Radar"),
        
        # Social Change (placeholder RSS feeds)
        ("https://rss.cnn.com/rss/edition.rss", "social_change", "CNN RSS"),
        
        # YouTube channels
        ("https://www.youtube.com/@aiadvantage", "tech_news", None),
        ("https://www.youtube.com/@HowIAI", "tech_news", None)
    ]
    
    for url, category, title in test_feeds:
        if "youtube.com/@" in url:
            # Extract channel handle for YouTube
            handle = url.split("/@")[1]
            monitor.add_youtube_channel(url, category, title, channel_id=handle)
        else:
            monitor.add_rss_feed(url, category, title)
    
    print("Test feeds configured")

def main():
    """CLI interface for pipeline orchestration"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "setup":
            setup_test_feeds()
            return
        elif command == "run":
            orchestrator = PipelineOrchestrator()
            digest_content = orchestrator.run_daily_pipeline()
            
            if digest_content and digest_content['episodes']:
                print(f"\n✅ Pipeline complete - {len(digest_content['episodes'])} episodes ready for TTS generation")
            else:
                print("\n⚠️  Pipeline complete - no content ready for digest")
            return
        elif command == "analyze":
            analyzer = ContentAnalyzer()
            cross_refs = analyzer.analyze_cross_references()
            
            print(f"Found {len(cross_refs)} cross-referenced topics:")
            for ref in cross_refs[:5]:
                print(f"  🔗 {ref['topic']} (strength: {ref['strength']:.2f})")
            return
    
    # Default: show help
    print("Daily Podcast Digest - Pipeline Orchestrator")
    print("===========================================")
    print()
    print("Commands:")
    print("  setup   - Configure test feeds")
    print("  run     - Execute daily pipeline")
    print("  analyze - Show cross-reference analysis")
    print()
    print("Example usage:")
    print("  python pipeline.py setup")
    print("  python pipeline.py run")

if __name__ == "__main__":
    main()