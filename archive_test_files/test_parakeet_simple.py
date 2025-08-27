#!/usr/bin/env python3
"""
Simple direct test of Parakeet MLX transcription functionality
"""

from content_processor import ContentProcessor
import os

def test_direct_transcription():
    """Test direct Parakeet transcription on smallest audio file"""
    
    processor = ContentProcessor()
    
    # Get the smallest audio file for quick testing
    audio_files = []
    for f in os.listdir("audio_cache"):
        if f.endswith('.wav'):
            path = os.path.join("audio_cache", f)
            size = os.path.getsize(path) / 1024 / 1024  # MB
            audio_files.append((f, size, path))
    
    audio_files.sort(key=lambda x: x[1])  # Sort by size
    smallest_file = audio_files[0]
    
    print(f"🎵 Testing with smallest file: {smallest_file[0]} ({smallest_file[1]:.1f} MB)")
    
    # Test transcription directly
    transcript = processor._parakeet_mlx_transcribe(smallest_file[2])
    
    if transcript:
        print(f"✅ Success! Transcript length: {len(transcript)} chars")
        print(f"Sample: {transcript[:100]}...")
        return True
    else:
        print("❌ Transcription failed")
        return False

if __name__ == "__main__":
    test_direct_transcription()