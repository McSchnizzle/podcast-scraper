#!/usr/bin/env python3
"""
Process a single episode for Phase 2.75 testing
"""

from content_processor import ContentProcessor

def main():
    processor = ContentProcessor()
    result = processor.process_episode(45)  # Process the Google Pixel episode
    
    if result:
        print(f"✅ Successfully processed episode {result['episode_id']}")
        print(f"   Transcript: {result['transcript_path']}")
        print(f"   Priority: {result['analysis']['priority_score']:.2f}")
    else:
        print("❌ Failed to process episode")

if __name__ == "__main__":
    main()
