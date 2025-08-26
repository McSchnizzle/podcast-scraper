#!/usr/bin/env python3
"""
YouTube Transcript Extractor
Extracts transcript from YouTube videos using the YouTube Transcript API
"""

from youtube_transcript_api import YouTubeTranscriptApi
import sys
import re

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:watch\?v=)([0-9A-Za-z_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_transcript(video_url):
    """Get transcript from YouTube video"""
    video_id = extract_video_id(video_url)
    
    if not video_id:
        print("Could not extract video ID from URL")
        return None
    
    try:
        # Create API instance and fetch transcript
        api = YouTubeTranscriptApi()
        transcript_data = api.fetch(video_id, languages=['en'])
        
        # Format the transcript
        full_transcript = []
        for entry in transcript_data:
            timestamp = entry.start
            text = entry.text
            # Format timestamp as MM:SS
            minutes = int(timestamp // 60)
            seconds = int(timestamp % 60)
            full_transcript.append(f"[{minutes:02d}:{seconds:02d}] {text}")
        
        return "\n".join(full_transcript)
        
    except Exception as e:
        print(f"Error getting transcript: {e}")
        return None

if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=8P7v1lgl-1s"
    
    print("Extracting transcript from YouTube video...")
    transcript = get_transcript(url)
    
    if transcript:
        # Save to file
        with open("transcript.txt", "w", encoding="utf-8") as f:
            f.write(transcript)
        
        print("Transcript saved to transcript.txt")
        print("\nFirst few lines:")
        print("=" * 50)
        lines = transcript.split("\n")
        for line in lines[:10]:
            print(line)
        if len(lines) > 10:
            print("...")
    else:
        print("Failed to extract transcript")