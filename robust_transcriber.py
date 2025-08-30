#!/usr/bin/env python3
"""
Robust Parakeet MLX Transcription Workflow
Handles file chunking, progress monitoring, and time estimation
"""

import os
import subprocess
import time
import math
from pathlib import Path
from typing import List, Tuple, Optional
import threading
import queue

# Parakeet MLX imports
try:
    from parakeet_mlx import from_pretrained
    import mlx.core as mx
    PARAKEET_AVAILABLE = True
except ImportError:
    PARAKEET_AVAILABLE = False
    print("❌ Parakeet MLX not available")

class RobustTranscriber:
    def __init__(self):
        self.asr_model = None
        self.progress_queue = queue.Queue()
        
        if PARAKEET_AVAILABLE:
            self._initialize_model()
    
    def _initialize_model(self):
        """Initialize Parakeet MLX model"""
        try:
            print("🔄 Loading Parakeet MLX model...")
            self.asr_model = from_pretrained("mlx-community/parakeet-tdt-0.6b-v2")
            print("✅ Parakeet MLX model loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load Parakeet MLX model: {e}")
            raise
    
    def estimate_transcription_time(self, audio_file: str) -> Tuple[float, float, int]:
        """
        Estimate transcription time based on audio duration and file size
        Updated algorithm based on real performance data from logs
        Returns: (duration_seconds, estimated_processing_time, recommended_chunks)
        """
        try:
            # Get audio duration
            probe_cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration,size', '-of', 'csv=p=0', audio_file]
            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                print(f"⚠️ Could not probe audio file: {result.stderr}")
                return 0, 0, 1
            
            lines = result.stdout.strip().split('\n')
            if not lines or not lines[0]:
                return 0, 0, 1
                
            parts = lines[0].split(',')
            duration = float(parts[0]) if parts[0] else 0
            file_size = float(parts[1]) if len(parts) > 1 and parts[1] else 0
            
            # Updated estimation based on actual log data analysis:
            # Observed RTF range: 0.05x to 0.243x, with most chunks around 0.15-0.2x
            # Using more realistic estimate: 0.18x RTF (average of observed performance)
            # This accounts for variability and gives a more accurate prediction
            base_rtf = 0.18  # More realistic based on actual measurements
            base_processing_time = duration * base_rtf
            
            # Adjust for file size and complexity factors
            size_mb = file_size / (1024 * 1024)
            
            # Size-based adjustments (larger files tend to have higher RTF)
            if size_mb > 300:  # Very large files
                base_processing_time *= 1.4
            elif size_mb > 200:  # Large files
                base_processing_time *= 1.2
            elif size_mb > 100:  # Medium files
                base_processing_time *= 1.1
            
            # Account for variability in processing time (some chunks take 2-3x longer)
            # Add a safety margin of 30% to account for occasional slow chunks
            base_processing_time *= 1.3
            
            # Determine chunking strategy
            max_chunk_duration = 600  # 10 minutes per chunk (conservative)
            num_chunks = math.ceil(duration / max_chunk_duration)
            
            # Add realistic overhead for chunking operations
            if num_chunks > 1:
                chunking_overhead = num_chunks * 15  # 15 seconds per chunk overhead (more realistic)
                total_processing_time = base_processing_time + chunking_overhead
            else:
                total_processing_time = base_processing_time
            
            return duration, total_processing_time, num_chunks
            
        except Exception as e:
            print(f"⚠️ Error estimating transcription time: {e}")
            return 0, 90, 1  # Updated default fallback (was too optimistic at 60s)
    
    def split_audio_file(self, input_file: str, chunk_duration: int = 300) -> List[str]:
        """
        Split large audio file into smaller chunks for processing
        Returns list of chunk file paths
        """
        try:
            base_path = Path(input_file)
            chunk_dir = base_path.parent / f"{base_path.stem}_chunks"
            chunk_dir.mkdir(exist_ok=True)
            
            # Get total duration first
            duration, _, _ = self.estimate_transcription_time(input_file)
            if duration <= chunk_duration:
                print(f"📄 File duration ({duration/60:.1f}min) within chunk limit - no splitting needed")
                return [input_file]
            
            print(f"✂️ Splitting {duration/60:.1f}min audio into {chunk_duration//60}min chunks...")
            
            chunk_files = []
            start_time = 0
            chunk_num = 1
            
            while start_time < duration:
                chunk_file = chunk_dir / f"chunk_{chunk_num:03d}.wav"
                
                # Use ffmpeg to extract chunk
                ffmpeg_cmd = [
                    'ffmpeg', '-y',  # Overwrite existing
                    '-i', str(input_file),
                    '-ss', str(start_time),  # Start time
                    '-t', str(chunk_duration),  # Duration
                    '-c', 'copy',  # Copy codec (faster)
                    str(chunk_file)
                ]
                
                print(f"📄 Creating chunk {chunk_num}: {start_time//60:.0f}m-{(start_time+chunk_duration)//60:.0f}m")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode != 0:
                    print(f"❌ Failed to create chunk {chunk_num}: {result.stderr}")
                    break
                
                if chunk_file.exists() and chunk_file.stat().st_size > 1000:  # Minimum 1KB
                    chunk_files.append(str(chunk_file))
                    print(f"✅ Chunk {chunk_num} created: {chunk_file.stat().st_size//1024//1024}MB")
                
                start_time += chunk_duration
                chunk_num += 1
            
            if not chunk_files:
                print("⚠️ No chunks created - using original file")
                return [input_file]
            
            print(f"✅ Created {len(chunk_files)} chunks for processing")
            return chunk_files
            
        except Exception as e:
            print(f"❌ Error splitting audio file: {e}")
            return [input_file]  # Fallback to original file
    
    def _monitor_progress(self, start_time: float, estimated_time: float, chunk_num: int, total_chunks: int):
        """Monitor and report transcription progress every 15 seconds"""
        last_report = 0
        
        while True:
            try:
                # Check if transcription is complete
                if not self.progress_queue.empty():
                    message = self.progress_queue.get_nowait()
                    if message == "COMPLETE":
                        break
                    elif message == "ERROR":
                        print("❌ Transcription process encountered an error")
                        break
                
                elapsed = time.time() - start_time
                
                # Report every 15 seconds
                if elapsed - last_report >= 15:
                    progress_pct = min((elapsed / estimated_time) * 100, 99)
                    remaining_time = max(estimated_time - elapsed, 0)
                    
                    print(f"🔄 Chunk {chunk_num}/{total_chunks} - Progress: {progress_pct:.1f}% "
                          f"(Elapsed: {elapsed:.0f}s, Est. remaining: {remaining_time:.0f}s)")
                    
                    last_report = elapsed
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                print(f"⚠️ Progress monitoring error: {e}")
                break
    
    def transcribe_chunk(self, chunk_file: str, chunk_num: int, total_chunks: int) -> Optional[str]:
        """
        Transcribe a single audio chunk with progress monitoring
        """
        if not self.asr_model:
            raise RuntimeError("Parakeet MLX model not initialized")
        
        try:
            print(f"\n🎯 Transcribing chunk {chunk_num}/{total_chunks}: {Path(chunk_file).name}")
            
            # Estimate time for this chunk
            duration, estimated_time, _ = self.estimate_transcription_time(chunk_file)
            print(f"📊 Chunk duration: {duration/60:.1f}min, estimated processing: {estimated_time:.0f}s")
            
            # Start progress monitoring in separate thread
            start_time = time.time()
            progress_thread = threading.Thread(
                target=self._monitor_progress,
                args=(start_time, estimated_time, chunk_num, total_chunks)
            )
            progress_thread.daemon = True
            progress_thread.start()
            
            # Perform transcription
            print(f"🚀 Starting Parakeet MLX transcription...")
            try:
                result = self.asr_model.transcribe(
                    chunk_file,
                    chunk_duration=60 * 2.0,  # 2 minutes per internal chunk
                    overlap_duration=15.0     # 15 seconds overlap
                )
                transcription = result.text if result else ""
                
                # Signal completion
                self.progress_queue.put("COMPLETE")
                
            except Exception as transcription_error:
                self.progress_queue.put("ERROR")
                raise transcription_error
            
            # Wait for progress thread to finish
            progress_thread.join(timeout=5)
            
            processing_time = time.time() - start_time
            actual_rtf = processing_time / duration if duration > 0 else 0
            
            print(f"✅ Chunk {chunk_num} complete: {processing_time:.1f}s actual "
                  f"(RTF: {actual_rtf:.3f}x, chars: {len(transcription) if transcription else 0})")
            
            if not transcription or not transcription.strip():
                print(f"⚠️ Chunk {chunk_num} produced no transcription")
                return ""
            
            return transcription.strip()
            
        except Exception as e:
            self.progress_queue.put("ERROR")
            print(f"❌ Error transcribing chunk {chunk_num}: {e}")
            return None
    
    def cleanup_transcript(self, transcript: str) -> str:
        """
        Clean up transcript by removing commercials and improving formatting
        DISABLED: Enhanced ad filtering with Claude AI integration (temporarily on hold)
        """
        if not transcript:
            return transcript
        
        print("🧹 Cleaning up transcript...")
        
        # TODO: Ad filtering functionality is temporarily disabled
        # The Claude AI ad filtering is not working properly and has been put on hold
        # We might want to revisit this in the future with a different approach
        # For now, just return the original transcript without any ad filtering
        
        print("ℹ️ Ad filtering temporarily disabled - returning original transcript")
        return transcript
    
    def transcribe_file(self, audio_file: str) -> Optional[str]:
        """
        Main transcription workflow: estimate, chunk, transcribe, cleanup
        """
        try:
            print(f"\n🎬 Starting robust transcription workflow for: {Path(audio_file).name}")
            workflow_start = time.time()
            
            # Step 1: Estimate transcription time
            print("\n📊 Step 1: Analyzing audio file...")
            duration, estimated_time, recommended_chunks = self.estimate_transcription_time(audio_file)
            
            if duration == 0:
                print("❌ Could not analyze audio file")
                return None
            
            print(f"📋 Analysis Results:")
            print(f"   • Duration: {duration/60:.1f} minutes")
            print(f"   • Estimated processing time: {estimated_time/60:.1f} minutes")
            print(f"   • Recommended chunks: {recommended_chunks}")
            
            # Step 2: Split file if needed
            print(f"\n✂️ Step 2: File chunking...")
            chunks = self.split_audio_file(audio_file, chunk_duration=600)  # 10-minute chunks
            
            if not chunks:
                print("❌ Failed to prepare file for transcription")
                return None
            
            # Create progress file for incremental saving
            episode_id = Path(audio_file).stem
            transcript_dir = Path("transcripts")
            transcript_dir.mkdir(exist_ok=True)
            progress_file = transcript_dir / f"{episode_id}_progress.txt"
            
            # Initialize progress file
            with open(progress_file, 'w', encoding='utf-8') as f:
                f.write(f"# Transcript for {episode_id} - In Progress\n")
                f.write(f"# Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total chunks: {len(chunks)}\n\n")
            
            print(f"📝 Progress saved to: {progress_file}")
            
            # Step 3: Transcribe each chunk with incremental saving
            print(f"\n🎯 Step 3: Transcribing {len(chunks)} chunk(s)...")
            transcriptions = []
            
            for i, chunk_file in enumerate(chunks, 1):
                chunk_result = self.transcribe_chunk(chunk_file, i, len(chunks))
                if chunk_result is not None:
                    transcriptions.append(chunk_result)
                    
                    # Append chunk to progress file immediately
                    with open(progress_file, 'a', encoding='utf-8') as f:
                        f.write(f"\n=== CHUNK {i}/{len(chunks)} ===\n")
                        f.write(chunk_result)
                        f.write(f"\n")
                    
                    print(f"💾 Chunk {i} appended to {progress_file}")
                else:
                    print(f"⚠️ Chunk {i} failed - continuing with remaining chunks")
            
            if not transcriptions:
                print("❌ No successful transcriptions")
                return None
            
            # Step 4: Combine transcriptions
            print(f"\n🔗 Step 4: Combining {len(transcriptions)} transcription(s)...")
            combined_transcript = "\n\n".join(transcriptions)
            
            # Step 5: Cleanup
            print(f"\n🧹 Step 5: Cleaning up transcript...")
            final_transcript = self.cleanup_transcript(combined_transcript)
            
            # Step 6: Save final cleaned transcript  
            final_file = transcript_dir / f"{episode_id}.txt"
            print(f"\n💾 Step 6: Saving final cleaned transcript to: {final_file}")
            with open(final_file, 'w', encoding='utf-8') as f:
                f.write(final_transcript)
            
            # Step 7: Cleanup chunk files (if created)
            if len(chunks) > 1 and chunks[0] != audio_file:
                print(f"\n🗑️ Step 7: Cleaning up chunk files...")
                chunk_dir = Path(chunks[0]).parent
                try:
                    import shutil
                    shutil.rmtree(chunk_dir)
                    print(f"✅ Deleted chunk directory: {chunk_dir}")
                except Exception as e:
                    print(f"⚠️ Could not delete chunk directory: {e}")
            
            # Step 8: Remove progress file and keep final file
            try:
                progress_file.unlink()
                print(f"🧹 Removed progress file: {progress_file}")
            except Exception as e:
                print(f"⚠️ Could not remove progress file: {e}")
            
            total_time = time.time() - workflow_start
            print(f"\n✅ Transcription workflow complete!")
            print(f"   • Total time: {total_time/60:.1f} minutes")
            print(f"   • Transcript length: {len(final_transcript):,} characters")
            print(f"   • Overall RTF: {total_time/duration:.3f}x")
            print(f"   • Final transcript: {final_file}")
            
            return final_transcript
            
        except Exception as e:
            print(f"❌ Transcription workflow failed: {e}")
            if 'progress_file' in locals():
                print(f"⚠️ Check {progress_file} for any partial progress")
            return None

def test_transcriber():
    """Test the robust transcriber with a single file"""
    transcriber = RobustTranscriber()
    
    # Use the smallest file for testing
    test_file = "/Users/paulbrown/Desktop/podcast-scraper/audio_cache/50e08aaa.wav"
    
    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        return
    
    result = transcriber.transcribe_file(test_file)
    
    if result:
        print(f"\n📄 Transcription Result Preview:")
        print("=" * 60)
        print(result[:500] + "..." if len(result) > 500 else result)
        print("=" * 60)
        return result
    else:
        print("❌ Transcription failed")
        return None

if __name__ == "__main__":
    test_transcriber()