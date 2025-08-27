#!/usr/bin/env python3
"""
Test script to verify Parakeet MLX transcription with cached audio files
"""

import os
import sys
from content_processor import ContentProcessor

def test_parakeet_transcription():
    """Test Parakeet MLX transcription with an existing cached audio file"""
    
    # Initialize processor
    processor = ContentProcessor()
    
    # Find a test audio file
    audio_cache_dir = "audio_cache"
    if not os.path.exists(audio_cache_dir):
        print("❌ No audio_cache directory found")
        return False
    
    # Get a smaller .wav file for testing (to avoid memory issues)
    wav_files = []
    for f in os.listdir(audio_cache_dir):
        if f.endswith('.wav'):
            file_path = os.path.join(audio_cache_dir, f)
            size_mb = os.path.getsize(file_path) / 1024 / 1024
            wav_files.append((f, size_mb))
    
    if not wav_files:
        print("❌ No .wav files found in audio_cache")
        return False
    
    # Sort by size and pick smallest for testing
    wav_files.sort(key=lambda x: x[1])
    test_file = os.path.join(audio_cache_dir, wav_files[0][0])
    print(f"🎵 Testing Parakeet MLX with: {test_file}")
    print(f"📏 File size: {os.path.getsize(test_file) / 1024 / 1024:.1f} MB")
    
    # Test transcription
    try:
        transcript = processor._parakeet_mlx_transcribe(test_file)
        
        if transcript:
            print(f"✅ Parakeet MLX transcription successful!")
            print(f"📝 Transcript length: {len(transcript)} characters")
            print(f"📄 Sample (first 200 chars): {transcript[:200]}...")
            
            # Save test transcript
            with open("test_transcript.txt", "w", encoding="utf-8") as f:
                f.write(transcript)
            print(f"💾 Full transcript saved to test_transcript.txt")
            return True
        else:
            print("❌ Parakeet MLX transcription returned empty result")
            return False
            
    except Exception as e:
        print(f"❌ Parakeet MLX test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_parakeet_transcription()
    sys.exit(0 if success else 1)