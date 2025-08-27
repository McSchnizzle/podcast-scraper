#!/usr/bin/env python3
"""
Simple batch test - process 3 smallest audio files
"""

import os
import time
import subprocess
from content_processor import ContentProcessor

def get_audio_duration(filepath):
    """Get audio duration using ffprobe"""
    probe_cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', filepath]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    
    if result.returncode == 0 and result.stdout.strip():
        try:
            return float(result.stdout.strip())
        except:
            return 0
    return 0

def test_batch_processing():
    """Test batch processing on 3 smallest files"""
    
    print("🎯 SIMPLE BATCH TEST - 3 SMALLEST FILES")
    print("=" * 50)
    
    # Initialize processor
    processor = ContentProcessor()
    
    # Get all WAV files with durations
    audio_files = []
    for filename in os.listdir("audio_cache"):
        if filename.endswith('.wav'):
            filepath = os.path.join("audio_cache", filename)
            duration = get_audio_duration(filepath)
            size_mb = os.path.getsize(filepath) / 1024 / 1024
            
            audio_files.append({
                'filename': filename,
                'filepath': filepath,
                'duration': duration,
                'duration_min': duration / 60,
                'size_mb': size_mb,
                'predicted_time': duration * 0.10  # RTF 0.10 estimate
            })
    
    # Sort by duration and take 3 smallest
    audio_files.sort(key=lambda x: x['duration'])
    test_files = audio_files[:3]
    
    print(f"Testing {len(test_files)} files:")
    for i, f in enumerate(test_files, 1):
        print(f"  {i}. {f['filename']} - {f['duration_min']:.1f}min ({f['size_mb']:.1f}MB) - Est: {f['predicted_time']/60:.1f}min")
    
    print()
    
    # Process each file
    results = []
    for i, file_info in enumerate(test_files, 1):
        print(f"🎵 [{i}/{len(test_files)}] Processing {file_info['filename']}...")
        print(f"    Duration: {file_info['duration_min']:.1f}min | Predicted: {file_info['predicted_time']/60:.1f}min")
        
        start_time = time.time()
        
        try:
            transcript = processor._audio_to_transcript(file_info['filepath'])
            end_time = time.time()
            
            processing_time = end_time - start_time
            rtf = processing_time / file_info['duration'] if file_info['duration'] > 0 else 0
            
            if transcript and len(transcript.strip()) > 50:
                print(f"    ✅ SUCCESS! Actual: {processing_time/60:.1f}min (RTF: {rtf:.3f})")
                print(f"    📝 Transcript: {len(transcript)} characters")
                
                # Calculate prediction accuracy
                prediction_error = abs(processing_time - file_info['predicted_time']) / file_info['predicted_time'] * 100
                print(f"    📊 Prediction accuracy: {prediction_error:.0f}% error")
                
                results.append({
                    'filename': file_info['filename'],
                    'actual_time': processing_time,
                    'predicted_time': file_info['predicted_time'],
                    'rtf': rtf,
                    'success': True,
                    'prediction_error': prediction_error
                })
            else:
                print(f"    ❌ FAILED: No valid transcript")
                results.append({'filename': file_info['filename'], 'success': False})
                
        except Exception as e:
            print(f"    ❌ ERROR: {e}")
            results.append({'filename': file_info['filename'], 'success': False, 'error': str(e)})
        
        print()
    
    # Summary
    successful = [r for r in results if r['success']]
    print("📋 BATCH TEST SUMMARY:")
    print(f"✅ Successful: {len(successful)}/{len(test_files)} files")
    
    if successful:
        avg_rtf = sum(r['rtf'] for r in successful) / len(successful)
        avg_error = sum(r['prediction_error'] for r in successful) / len(successful)
        print(f"📊 Average RTF: {avg_rtf:.3f} ({1/avg_rtf:.1f}x real-time)")
        print(f"🎯 Average prediction error: {avg_error:.0f}%")
        
        print(f"\nDetailed results:")
        for r in successful:
            print(f"  {r['filename']}: {r['actual_time']/60:.1f}min actual vs {r['predicted_time']/60:.1f}min predicted")

if __name__ == '__main__':
    test_batch_processing()