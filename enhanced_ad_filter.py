#!/usr/bin/env python3
"""
Enhanced Advertisement Filter with Claude AI Integration
Uses Claude AI for intelligent advertisement detection and removal.
"""

import os
import subprocess
import tempfile
from typing import List, Tuple
from pathlib import Path

class EnhancedAdFilter:
    def __init__(self):
        self.advertisement_examples_path = Path(__file__).parent / "advertisement_examples.txt"
    
    def filter_advertisements_claude(self, transcript: str) -> Tuple[str, int]:
        """
        Use Claude AI for intelligent advertisement detection and removal
        """
        try:
            # Load advertisement examples for context
            examples_context = ""
            if self.advertisement_examples_path.exists():
                with open(self.advertisement_examples_path, 'r') as f:
                    examples_context = f.read()
            
            # Create optimized Claude prompt for ad filtering
            prompt = """Remove all advertisements from this podcast transcript while keeping all actual podcast content. 

Ads typically include:
- Sponsor mentions with company names/websites
- Promo codes and discount offers  
- Service descriptions with contact info
- Explicit ad markers

Return only the cleaned transcript:

"""
            
            # Use Claude Code in print mode for ad filtering
            result = subprocess.run([
                'claude', '--print'
            ], input=prompt + transcript, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0 and result.stdout.strip():
                cleaned_transcript = result.stdout.strip()
                
                # Basic validation - ensure we didn't remove too much content
                original_words = len(transcript.split())
                cleaned_words = len(cleaned_transcript.split())
                removed_chars = len(transcript) - len(cleaned_transcript)
                
                print(f"📊 Claude filtering: {original_words} → {cleaned_words} words ({cleaned_words/original_words:.1%} retained)")
                
                if cleaned_words >= original_words * 0.8:  # Skip filtering if >20% content lost
                    return cleaned_transcript, removed_chars
                else:
                    print(f"⚠️ Claude filtering removed too much content ({100-cleaned_words/original_words*100:.1f}% lost), skipping filtering")
            else:
                print(f"⚠️ Claude filtering failed: {result.stderr}")
            
        except Exception as e:
            print(f"⚠️ Claude filtering error: {e}")
        
        # If Claude filtering fails, return original transcript (no filtering)
        print("🔄 Returning original transcript without ad filtering")
        return transcript, 0
    
    def filter_advertisements(self, transcript: str) -> Tuple[str, int]:
        """
        Main advertisement filtering method using Claude AI
        """
        return self.filter_advertisements_claude(transcript)

def test_filter():
    """Test the enhanced ad filter with sample content"""
    filter = EnhancedAdFilter()
    
    test_transcript = """
    Today we're talking about AI developments. But first, let me tell you about our sponsor.
    
    Podbean, your message amplified. Ready to share your message with the world? Start your podcast journey with Podbean. Podbean. Podbean. The AI-powered all-in-one podcast platform. Thousands of businesses and enterprises trust Podbean to launch their podcasts. Launch your podcast on Podbean today.
    
    Now back to our conversation about artificial intelligence and its impact on society. The latest developments in LLMs are fascinating...
    
    Tony Spezza here with AAA Heating Cooling. In the last five years, most of our competitors have become total sellouts, man. We have Portland roots, not corporate suits. AAA! AAAAA Heating and Cooling. CCP number 222.
    
    So as I was saying, the implications of these AI developments are really significant for how we think about...
    """
    
    print("Testing enhanced ad filter...")
    cleaned, removed = filter.filter_advertisements(test_transcript)
    print(f"Removed {removed} characters")
    print("\nCleaned transcript:")
    print(cleaned)

if __name__ == "__main__":
    test_filter()