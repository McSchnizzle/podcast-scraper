#!/usr/bin/env python3
"""
Test script for enhanced advertisement filtering
"""

from enhanced_ad_filter import EnhancedAdFilter
from pathlib import Path

def test_ad_filtering():
    """Test the enhanced ad filter on the test transcript"""
    
    # Load test transcript
    test_file = Path(__file__).parent / "test_transcript_with_ads.txt"
    
    if not test_file.exists():
        print("❌ Test transcript file not found")
        return
    
    with open(test_file, 'r') as f:
        original_transcript = f.read()
    
    print(f"📄 Original transcript: {len(original_transcript)} characters")
    print(f"📄 Original word count: {len(original_transcript.split())} words")
    
    # Test Claude filtering
    print("\n🧪 Testing Claude AI filtering...")
    filter = EnhancedAdFilter()
    cleaned_claude, removed_claude = filter.filter_advertisements(original_transcript)
    
    print(f"✂️ Claude filtering removed: {removed_claude} characters")
    print(f"📄 Cleaned transcript: {len(cleaned_claude)} characters")
    print(f"📄 Cleaned word count: {len(cleaned_claude.split())} words")
    
    # Save results for inspection
    claude_output = Path(__file__).parent / "test_output_claude.txt"
    
    with open(claude_output, 'w') as f:
        f.write(cleaned_claude)
    
    print(f"\n💾 Results saved:")
    print(f"   Claude filtering: {claude_output}")
    
    # Check if specific ads were removed
    ads_to_check = [
        "Podbean, your message amplified",
        "Tony Spezza here with AAA Heating",
        "Golden Valley Brewery", 
        "Pacific Northwest Pet ER",
        "Yo, this is an advertisement",
        "Kobe Dryer Sheets"
    ]
    
    print(f"\n🔍 Checking specific ad removal:")
    for ad in ads_to_check:
        in_claude = ad.lower() in cleaned_claude.lower()
        claude_status = "❌ FOUND" if in_claude else "✅ REMOVED"
        print(f"   '{ad[:30]}...': {claude_status}")

if __name__ == "__main__":
    test_ad_filtering()