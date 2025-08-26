#!/usr/bin/env python3
"""
Test script for Parakeet integration
"""

from content_processor import ContentProcessor

def test_parakeet_integration():
    """Test the Parakeet ASR integration"""
    print("Testing Parakeet ASR Integration")
    print("=" * 40)
    
    # Initialize processor
    processor = ContentProcessor()
    
    # Check what ASR engine is available
    print(f"NeMo Available: {hasattr(processor, 'asr_model') and processor.asr_model is not None}")
    
    # Try to process one RSS episode
    print("\nAttempting to process RSS episode...")
    
    # Get first pending RSS episode
    import sqlite3
    conn = sqlite3.connect('podcast_monitor.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT e.id, e.title, f.title as feed_title
        FROM episodes e
        JOIN feeds f ON e.feed_id = f.id
        WHERE e.processed = 0 AND f.type = 'rss'
        ORDER BY e.published_date DESC
        LIMIT 1
    ''')
    episode = cursor.fetchone()
    conn.close()
    
    if episode:
        episode_id, title, feed_title = episode
        print(f"Processing episode: {title}")
        print(f"From feed: {feed_title}")
        
        # Process the episode
        result = processor.process_episode(episode_id)
        
        if result:
            print(f"✅ Successfully processed episode {episode_id}")
            print(f"Priority score: {result['analysis']['priority_score']:.2f}")
        else:
            print("❌ Failed to process episode")
    else:
        print("No pending RSS episodes found")

if __name__ == "__main__":
    test_parakeet_integration()