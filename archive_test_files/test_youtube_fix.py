#!/usr/bin/env python3
"""
Test script to verify YouTube transcript API fix
"""

from content_processor import ContentProcessor

def test_youtube_fix():
    """Test the YouTube API fix with one of the failed episodes"""
    
    # Use one of the failed YouTube episodes that's longer
    test_video_url = "https://www.youtube.com/watch?v=lrvchpRvKXA"  # Gemini & Claude Got HUGE Memory Upgrades!
    
    print("🧪 Testing YouTube API fix...")
    print(f"Video URL: {test_video_url}")
    print("=" * 60)
    
    try:
        processor = ContentProcessor(min_youtube_minutes=0.5)  # Lower threshold for testing
        transcript = processor._process_youtube_episode(test_video_url, "yt:video:lrvchpRvKXA")
        
        if transcript:
            print("✅ YouTube transcript extraction successful!")
            print(f"Transcript length: {len(transcript):,} characters")
            print("\nTranscript preview:")
            print("=" * 40)
            preview = transcript[:500] + "..." if len(transcript) > 500 else transcript
            print(preview)
            print("=" * 40)
            return True
        else:
            print("❌ YouTube transcript extraction failed")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_youtube_fix()
    if success:
        print("\n🎉 YouTube API fix appears to be working!")
    else:
        print("\n💥 YouTube API fix needs more work")