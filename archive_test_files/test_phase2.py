#!/usr/bin/env python3
"""
Phase 2 Testing Script
Tests the content processing pipeline with real data
"""

import sqlite3
from pathlib import Path
from pipeline import PipelineOrchestrator
from content_analyzer import ContentAnalyzer

def test_dependencies():
    """Test that required dependencies are available"""
    import subprocess
    
    dependencies = [
        ('ffmpeg', ['ffmpeg', '-version']),
        ('youtube-transcript-api', ['python3', '-c', 'import youtube_transcript_api; print("OK")'])
    ]
    
    results = {}
    for name, cmd in dependencies:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            results[name] = result.returncode == 0
        except:
            results[name] = False
    
    return results

def test_youtube_transcript():
    """Test YouTube transcript extraction"""
    from get_transcript import get_transcript
    
    # Test with a known working video
    test_url = "https://www.youtube.com/watch?v=8P7v1lgl-1s"
    
    print("Testing YouTube transcript extraction...")
    transcript = get_transcript(test_url)
    
    if transcript:
        lines = transcript.split('\n')
        print(f"✅ Extracted {len(lines)} lines of transcript")
        print("Sample content:")
        for line in lines[:3]:
            print(f"  {line}")
        return True
    else:
        print("❌ Failed to extract transcript")
        return False

def test_content_analysis():
    """Test content analysis with sample transcript"""
    analyzer = ContentAnalyzer()
    
    # Sample transcript content
    sample_transcript = """
    [00:30] Today we're excited to announce the launch of our new AI platform
    [01:15] This is a breakthrough in machine learning technology
    [02:00] The impact is going to be huge for developers everywhere
    [02:30] We're seeing incredible adoption from major companies like Google and Microsoft
    [03:00] This revolutionary approach will change how we build applications
    """
    
    print("Testing content analysis...")
    analysis = analyzer.analyze_episode_content(
        sample_transcript, 
        'tech_news', 
        'Announcing Revolutionary AI Platform'
    )
    
    print(f"Priority Score: {analysis['priority_score']:.2f}")
    print(f"Content Type: {analysis['content_type']}")
    print(f"Sentiment: {analysis['sentiment']}")
    print(f"Announcements: {len(analysis['announcements'])}")
    print(f"Key Topics: {', '.join(analysis['key_topics'][:3])}")
    
    return analysis['priority_score'] > 0.5  # Should be high priority

def main():
    """Run Phase 2 tests"""
    print("Daily Podcast Digest - Phase 2 Testing")
    print("======================================")
    
    # Test 1: Dependencies
    print("1. Testing dependencies...")
    deps = test_dependencies()
    
    for name, available in deps.items():
        status = "✅" if available else "❌"
        print(f"   {status} {name}")
    
    if not all(deps.values()):
        print("\n⚠️  Some dependencies missing. Install with:")
        if not deps['ffmpeg']:
            print("   brew install ffmpeg")
        if not deps['youtube-transcript-api']:
            print("   pip install youtube-transcript-api")
    
    print()
    
    # Test 2: YouTube transcript
    print("2. Testing YouTube transcript extraction...")
    youtube_success = test_youtube_transcript()
    print()
    
    # Test 3: Content analysis
    print("3. Testing content analysis...")
    analysis_success = test_content_analysis()
    print()
    
    # Test 4: Database integrity
    print("4. Testing database...")
    db_path = Path("podcast_monitor.db")
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check episode count
        cursor.execute('SELECT COUNT(*) FROM episodes')
        episode_count = cursor.fetchone()[0]
        
        # Check processed count  
        cursor.execute('SELECT COUNT(*) FROM episodes WHERE processed = 1')
        processed_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"   📊 Total episodes: {episode_count}")
        print(f"   ✅ Processed episodes: {processed_count}")
        
        db_success = episode_count > 0
    else:
        print("   ❌ Database not found")
        db_success = False
    
    print()
    
    # Summary
    all_tests = [
        ("Dependencies", all(deps.values())),
        ("YouTube Transcripts", youtube_success),
        ("Content Analysis", analysis_success),
        ("Database", db_success)
    ]
    
    print("TEST SUMMARY:")
    print("=" * 20)
    
    passed = 0
    for test_name, success in all_tests:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{len(all_tests)} tests passed")
    
    if passed == len(all_tests):
        print("🎉 Phase 2 implementation ready!")
        print("\nNext steps:")
        print("   python pipeline.py run    # Process all pending episodes")
        print("   python pipeline.py analyze # Show cross-references")
    else:
        print("🔧 Some issues need to be resolved before Phase 2 is complete")

if __name__ == "__main__":
    main()