#!/usr/bin/env python3
"""
Batch Parakeet MLX Transcription Script
Processes all cached audio files with time prediction and progress tracking
"""

import os
import time
import subprocess
import threading
from datetime import datetime
from content_processor import ContentProcessor

class ProgressTracker:
    def __init__(self, estimated_duration):
        self.estimated_duration = estimated_duration
        self.start_time = time.time()
        self.running = True
        
    def show_progress(self):
        """Show live progress updates every 30 seconds"""
        while self.running:
            elapsed = time.time() - self.start_time
            progress_pct = min((elapsed / self.estimated_duration) * 100, 100)
            
            if elapsed < 60:
                time_str = f"{elapsed:.0f}s"
            else:
                time_str = f"{elapsed/60:.1f}min"
                
            print(f"    ⏳ Progress: {time_str} elapsed | {progress_pct:.1f}% of estimated time")
            
            if not self.running:
                break
                
            time.sleep(30)  # Update every 30 seconds
    
    def stop(self):
        self.running = False

def analyze_audio_file(filepath):
    """Get audio file duration and size info"""
    probe_cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', filepath]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    
    duration = 0
    if result.returncode == 0 and result.stdout.strip():
        try:
            duration = float(result.stdout.strip())
        except:
            pass
    
    size_mb = os.path.getsize(filepath) / 1024 / 1024
    return duration, size_mb

def batch_transcribe_cached_audio():
    """Process all cached audio files with Parakeet MLX"""
    
    print("🚀 BATCH PARAKEET MLX TRANSCRIPTION")
    print("=" * 60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    processor = ContentProcessor()
    
    # Collect all audio files
    audio_files = []
    cache_dir = "audio_cache"
    
    for filename in os.listdir(cache_dir):
        if filename.endswith('.wav'):
            filepath = os.path.join(cache_dir, filename)
            duration, size_mb = analyze_audio_file(filepath)
            
            # Check if transcript already exists
            hash_id = filename.split('.')[0]
            transcript_path = f"transcripts/{hash_id}.txt"
            already_exists = os.path.exists(transcript_path)
            
            # Check if linked to database episode
            import sqlite3
            conn = sqlite3.connect('podcast_monitor.db')
            cursor = conn.cursor()
            cursor.execute('SELECT id, title FROM episodes WHERE transcript_path LIKE ?', (f'%{hash_id}%',))
            db_episode = cursor.fetchone()
            conn.close()
            
            audio_files.append({
                'filename': filename,
                'filepath': filepath,
                'hash': hash_id,
                'duration': duration,
                'duration_min': duration / 60,
                'size_mb': size_mb,
                'estimated_time': duration * 0.10,  # Based on RTF ~0.10
                'already_exists': already_exists,
                'db_episode': db_episode
            })
    
    # Sort by duration (smallest first for early validation)
    audio_files.sort(key=lambda x: x['duration'])
    
    # Filter out already processed files
    pending_files = [f for f in audio_files if not f['already_exists']]
    
    print(f"📊 ANALYSIS SUMMARY:")
    print(f"   Total audio files: {len(audio_files)}")
    print(f"   Already transcribed: {len(audio_files) - len(pending_files)}")
    print(f"   Pending transcription: {len(pending_files)}")
    print(f"   Total pending duration: {sum(f['duration'] for f in pending_files)/3600:.1f} hours")
    print(f"   Estimated processing time: {sum(f['estimated_time'] for f in pending_files)/3600:.1f} hours")
    print()
    
    if not pending_files:
        print("✅ All audio files already transcribed!")
        return True
    
    # Process each file
    results = []
    total_start = time.time()
    
    for i, file_info in enumerate(pending_files, 1):
        print(f"🎵 [{i}/{len(pending_files)}] PROCESSING: {file_info['filename']}")
        print(f"    📏 Duration: {file_info['duration_min']:.1f}min | Size: {file_info['size_mb']:.1f}MB")
        print(f"    ⏱️  Predicted time: {file_info['estimated_time']/60:.1f}min (RTF ~0.10)")
        
        # Start progress tracker in background
        progress = ProgressTracker(file_info['estimated_time'])
        progress_thread = threading.Thread(target=progress.show_progress)
        progress_thread.daemon = True
        progress_thread.start()
        
        # Mark as transcribing if linked to database episode
        if file_info['db_episode']:
            episode_id, episode_title = file_info['db_episode']
            try:
                import sqlite3
                conn = sqlite3.connect('podcast_monitor.db')
                cursor = conn.cursor()
                cursor.execute('UPDATE episodes SET status = ? WHERE id = ?', ('transcribing', episode_id))
                conn.commit()
                conn.close()
                print(f"    🔄 Database updated: Episode {episode_id} status → transcribing")
            except Exception as e:
                print(f"    ⚠️ Database update failed: {e}")
        
        # Process the file
        start_time = time.time()
        try:
            transcript = processor._audio_to_transcript(file_info['filepath'])
            end_time = time.time()
            
            # Stop progress tracker
            progress.stop()
            progress_thread.join(timeout=1)
            
            processing_time = end_time - start_time
            rtf = processing_time / file_info['duration'] if file_info['duration'] > 0 else 0
            
            if transcript and len(transcript.strip()) > 100:
                # Save transcript
                os.makedirs('transcripts', exist_ok=True)
                transcript_path = f'transcripts/{file_info["hash"]}.txt'
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    f.write(transcript)
                
                # Update database if episode exists
                if file_info['db_episode']:
                    episode_id, episode_title = file_info['db_episode']
                    try:
                        import sqlite3
                        conn = sqlite3.connect('podcast_monitor.db')
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE episodes 
                            SET transcript_path = ?, status = 'transcribed'
                            WHERE id = ?
                        ''', (transcript_path, episode_id))
                        conn.commit()
                        conn.close()
                        print(f"    📊 Database updated: Episode {episode_id} status → transcribed")
                    except Exception as e:
                        print(f"    ⚠️ Database update failed: {e}")
                
                print(f"    ✅ SUCCESS! Actual: {processing_time/60:.1f}min (RTF: {rtf:.3f})")
                print(f"    📝 Transcript: {len(transcript)} chars saved to {transcript_path}")
                
                results.append({
                    **file_info,
                    'actual_time': processing_time,
                    'rtf': rtf,
                    'transcript_length': len(transcript),
                    'success': True
                })
            else:
                progress.stop()
                print(f"    ❌ FAILED: Empty or invalid transcript")
                results.append({**file_info, 'success': False})
                
        except Exception as e:
            progress.stop()
            progress_thread.join(timeout=1)
            print(f"    ❌ ERROR: {str(e)}")
            results.append({**file_info, 'success': False, 'error': str(e)})
        
        print()  # Spacing between files
    
    # Final report
    total_time = time.time() - total_start
    successful = [r for r in results if r['success']]
    
    print("🎉 BATCH PROCESSING COMPLETE!")
    print("=" * 60)
    print(f"⏱️  Total time: {total_time/3600:.2f} hours")
    print(f"✅ Successful: {len(successful)}/{len(pending_files)} files")
    
    if successful:
        avg_rtf = sum(r['rtf'] for r in successful) / len(successful)
        print(f"📊 Average RTF: {avg_rtf:.3f} (1/{1/avg_rtf:.1f}x real-time)")
        
        print(f"\n📋 SUCCESSFUL TRANSCRIPTIONS:")
        for r in successful:
            prediction_accuracy = abs(r['actual_time'] - r['estimated_time']) / r['estimated_time'] * 100
            print(f"   {r['filename']}: {r['actual_time']/60:.1f}min actual vs {r['estimated_time']/60:.1f}min predicted ({prediction_accuracy:.0f}% diff)")
    
    return len(successful) == len(pending_files)

if __name__ == '__main__':
    success = batch_transcribe_cached_audio()
    print(f"\n{'🎉 ALL FILES PROCESSED SUCCESSFULLY!' if success else '⚠️  Some files failed - check output above'}")