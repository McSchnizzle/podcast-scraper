#!/usr/bin/env python3
"""
Failed Episode Lifecycle Management
Provides comprehensive retry logic and failure tracking for podcast episodes
"""

import sqlite3
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from utils.datetime_utils import now_utc
from utils.db import get_connection
from pathlib import Path

# Configuration - removed dependency on config module to avoid conflicts
DB_TIMEOUT = 30  # seconds

logger = logging.getLogger(__name__)

class FailureManager:
    """Manages failed episode tracking and retry logic"""
    
    # Retry configuration
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAYS = [300, 1800, 7200]  # 5min, 30min, 2hrs
    FAILURE_CATEGORIES = {
        'download': {'max_retries': 3, 'retry_delay': 300},     # Network issues
        'transcription': {'max_retries': 2, 'retry_delay': 600},  # Processing issues  
        'scoring': {'max_retries': 4, 'retry_delay': 180},      # API rate limits
        'digest': {'max_retries': 2, 'retry_delay': 900},       # Claude API issues
        'publishing': {'max_retries': 3, 'retry_delay': 300}    # GitHub/RSS issues
    }
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    def log_episode_failure(self, episode_id: str, failure_reason: str, 
                           failure_category: str = 'general', 
                           traceback_info: str = None) -> bool:
        """Log episode failure with categorization and retry tracking"""
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            # Get current failure info - using episode.id for proper FK relationship
            cursor.execute("""
                SELECT id, retry_count, failure_reason, status 
                FROM episodes 
                WHERE episode_id = ?
            """, (episode_id,))
            
            result = cursor.fetchone()
            if not result:
                self.logger.warning(f"Episode {episode_id} not found for failure logging")
                return False
                
            db_id, current_retry_count, current_reason, current_status = result
            new_retry_count = (current_retry_count or 0) + 1
            
            # Determine if episode should be marked as permanently failed
            max_retries = self.FAILURE_CATEGORIES.get(failure_category, {}).get('max_retries', self.MAX_RETRY_ATTEMPTS)
            final_status = 'failed' if new_retry_count >= max_retries else current_status
            
            # Create comprehensive failure reason
            full_reason = f"[{failure_category.upper()}] {failure_reason}"
            if current_reason:
                full_reason = f"{current_reason}; {full_reason}"
                
            # Update episode with failure information
            cursor.execute("""
                UPDATE episodes 
                SET failure_reason = ?,
                    failure_timestamp = datetime('now'),
                    retry_count = ?,
                    status = ?
                WHERE id = ?
            """, (full_reason, new_retry_count, final_status, db_id))
            
            # Log failure to episode_failures table for detailed tracking
            # Pass the integer db_id for proper FK relationship
            self._log_detailed_failure(cursor, db_id, failure_reason, 
                                     failure_category, traceback_info)
            
            conn.commit()
            conn.close()
            
            status_msg = "permanently failed" if final_status == 'failed' else f"retry #{new_retry_count}"
            self.logger.info(f"📝 Episode {episode_id} {status_msg}: [{failure_category}] {failure_reason}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to log episode failure: {e}")
            return False
    
    def _log_detailed_failure(self, cursor, episode_pk: int, failure_reason: str, 
                             failure_category: str, traceback_info: str = None):
        """Log detailed failure information to episode_failures table"""
        try:
            # Try new schema first (episode_pk column)
            cursor.execute("""
                INSERT INTO episode_failures (
                    episode_pk, failure_reason, failure_category, 
                    traceback_info, failure_timestamp
                ) VALUES (?, ?, ?, ?, datetime('now'))
            """, (episode_pk, failure_reason, failure_category, traceback_info))
        except sqlite3.OperationalError as e:
            if "no such column: episode_pk" in str(e):
                # Fall back to old schema (episode_id column) - get episode_id from episode_pk
                cursor.execute("SELECT episode_id FROM episodes WHERE id = ?", (episode_pk,))
                result = cursor.fetchone()
                if result:
                    episode_id = result[0]
                    cursor.execute("""
                        INSERT INTO episode_failures (
                            episode_id, failure_reason, failure_category, 
                            traceback_info, failure_timestamp
                        ) VALUES (?, ?, ?, ?, datetime('now'))
                    """, (episode_id, failure_reason, failure_category, traceback_info))
                else:
                    raise RuntimeError(f"Cannot find episode with id {episode_pk} for failure logging")
            else:
                raise
            
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                self.logger.info("Creating episode_failures table...")
                self._create_failures_table(cursor)
                # Retry the insert
                cursor.execute("""
                    INSERT INTO episode_failures (
                        episode_id, failure_reason, failure_category, 
                        traceback_info, failure_timestamp
                    ) VALUES (?, ?, ?, ?, datetime('now'))
                """, (episode_id, failure_reason, failure_category, traceback_info))
            else:
                raise
    
    def _create_failures_table(self, cursor):
        """Create episode_failures table for detailed failure tracking"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episode_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id TEXT NOT NULL,
                failure_reason TEXT NOT NULL,
                failure_category TEXT NOT NULL,
                traceback_info TEXT,
                failure_timestamp TIMESTAMP NOT NULL,
                resolved BOOLEAN DEFAULT 0,
                resolution_notes TEXT,
                FOREIGN KEY (episode_id) REFERENCES episodes (episode_id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_episode_failures_episode_id 
            ON episode_failures(episode_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_episode_failures_category 
            ON episode_failures(failure_category)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_episode_failures_timestamp 
            ON episode_failures(failure_timestamp)
        """)
        
        self.logger.info("✅ Created episode_failures table with indexes")
    
    def get_retry_candidates(self) -> List[Dict]:
        """Get episodes eligible for retry based on failure category and timing"""
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            retry_candidates = []
            current_time = now_utc()
            
            # Get episodes that failed but haven't exceeded max retries
            cursor.execute("""
                SELECT id, episode_id, title, failure_reason, failure_timestamp, 
                       retry_count, status, audio_url
                FROM episodes 
                WHERE status != 'failed' 
                  AND retry_count > 0 
                  AND failure_timestamp IS NOT NULL
                ORDER BY failure_timestamp DESC
            """)
            
            for row in cursor.fetchall():
                db_id, episode_id, title, failure_reason, failure_timestamp, retry_count, status, audio_url = row
                
                # Parse failure timestamp
                try:
                    failure_time = datetime.fromisoformat(failure_timestamp.replace('Z', '+00:00'))
                except:
                    # Fallback for different timestamp formats
                    failure_time = datetime.strptime(failure_timestamp, '%Y-%m-%d %H:%M:%S')
                
                # Determine failure category and retry configuration
                failure_category = self._extract_failure_category(failure_reason)
                category_config = self.FAILURE_CATEGORIES.get(failure_category, {})
                max_retries = category_config.get('max_retries', self.MAX_RETRY_ATTEMPTS)
                retry_delay = category_config.get('retry_delay', 300)
                
                # Check if episode is eligible for retry
                if retry_count < max_retries:
                    time_since_failure = (current_time - failure_time).total_seconds()
                    if time_since_failure >= retry_delay:
                        retry_candidates.append({
                            'db_id': db_id,
                            'episode_id': episode_id,
                            'title': title,
                            'failure_reason': failure_reason,
                            'failure_category': failure_category,
                            'retry_count': retry_count,
                            'status': status,
                            'audio_url': audio_url,
                            'time_since_failure': time_since_failure
                        })
            
            conn.close()
            
            self.logger.info(f"🔄 Found {len(retry_candidates)} episodes eligible for retry")
            return retry_candidates
            
        except Exception as e:
            self.logger.error(f"Failed to get retry candidates: {e}")
            return []
    
    def _extract_failure_category(self, failure_reason: str) -> str:
        """Extract failure category from failure reason string"""
        if not failure_reason:
            return 'general'
            
        reason_lower = failure_reason.lower()
        
        # Check for category markers
        for category in self.FAILURE_CATEGORIES.keys():
            if f'[{category.upper()}]' in failure_reason:
                return category
        
        # Infer category from failure reason content
        if any(term in reason_lower for term in ['download', 'fetch', 'network', 'connection']):
            return 'download'
        elif any(term in reason_lower for term in ['transcrib', 'audio', 'speech', 'whisper']):
            return 'transcription'
        elif any(term in reason_lower for term in ['score', 'openai', 'api', 'rate limit']):
            return 'scoring'
        elif any(term in reason_lower for term in ['digest', 'claude', 'generation']):
            return 'digest'
        elif any(term in reason_lower for term in ['deploy', 'github', 'rss', 'publish']):
            return 'publishing'
        else:
            return 'general'
    
    def mark_episode_recovered(self, episode_id: str, recovery_notes: str = None) -> bool:
        """Mark episode as recovered and update failure tracking"""
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            # Clear failure information from episodes table
            cursor.execute("""
                UPDATE episodes 
                SET failure_reason = NULL,
                    failure_timestamp = NULL
                WHERE episode_id = ?
            """, (episode_id,))
            
            # Mark failures as resolved in detailed tracking table
            cursor.execute("""
                UPDATE episode_failures 
                SET resolved = 1,
                    resolution_notes = ?
                WHERE episode_id = ? AND resolved = 0
            """, (recovery_notes, episode_id))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"✅ Episode {episode_id} marked as recovered: {recovery_notes}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to mark episode as recovered: {e}")
            return False
    
    def get_failure_statistics(self, days_back: int = 7) -> Dict:
        """Get comprehensive failure statistics for monitoring"""
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = now_utc() - timedelta(days=days_back)
            
            # Get failure counts by category
            cursor.execute("""
                SELECT failure_reason, COUNT(*) as count
                FROM episodes 
                WHERE failure_timestamp >= ? 
                  AND failure_reason IS NOT NULL
                GROUP BY failure_reason
                ORDER BY count DESC
            """, (cutoff_date.isoformat(),))
            
            failure_reasons = cursor.fetchall()
            
            # Get retry statistics
            cursor.execute("""
                SELECT retry_count, COUNT(*) as count
                FROM episodes 
                WHERE retry_count > 0 
                  AND failure_timestamp >= ?
                GROUP BY retry_count
                ORDER BY retry_count
            """, (cutoff_date.isoformat(),))
            
            retry_stats = cursor.fetchall()
            
            # Get status distribution
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM episodes 
                WHERE created_at >= ?
                GROUP BY status
                ORDER BY count DESC
            """, (cutoff_date.isoformat(),))
            
            status_stats = cursor.fetchall()
            
            conn.close()
            
            return {
                'time_period_days': days_back,
                'failure_reasons': dict(failure_reasons),
                'retry_distribution': dict(retry_stats),
                'status_distribution': dict(status_stats),
                'total_failed_episodes': sum(count for _, count in failure_reasons)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get failure statistics: {e}")
            return {}
    
    def cleanup_old_failures(self, days_old: int = 30) -> int:
        """Clean up old resolved failures to keep database manageable"""
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = now_utc() - timedelta(days=days_old)
            
            cursor.execute("""
                DELETE FROM episode_failures 
                WHERE resolved = 1 
                  AND failure_timestamp < ?
            """, (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                self.logger.info(f"🧹 Cleaned up {deleted_count} old resolved failures")
            
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old failures: {e}")
            return 0

class RetryProcessor:
    """Processes retry candidates through the appropriate pipeline stages"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.failure_manager = FailureManager(db_path)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def process_retry_queue(self, max_retries_per_run: int = 5) -> Dict:
        """Process episodes in retry queue through appropriate pipeline stages"""
        retry_candidates = self.failure_manager.get_retry_candidates()
        
        if not retry_candidates:
            self.logger.info("🔄 No episodes eligible for retry")
            return {'processed': 0, 'succeeded': 0, 'failed': 0}
        
        # Limit retries per run to prevent overwhelming the system
        candidates_to_process = retry_candidates[:max_retries_per_run]
        
        results = {
            'processed': len(candidates_to_process),
            'succeeded': 0,
            'failed': 0,
            'retry_results': []
        }
        
        for candidate in candidates_to_process:
            self.logger.info(f"🔄 Retrying {candidate['episode_id']}: {candidate['title']}")
            
            success = self._retry_episode(candidate)
            if success:
                results['succeeded'] += 1
                self.failure_manager.mark_episode_recovered(
                    candidate['episode_id'], 
                    f"Retry successful after {candidate['retry_count']} attempts"
                )
            else:
                results['failed'] += 1
            
            results['retry_results'].append({
                'episode_id': candidate['episode_id'],
                'title': candidate['title'],
                'success': success,
                'retry_attempt': candidate['retry_count'] + 1
            })
        
        return results
    
    def _retry_episode(self, candidate: Dict) -> bool:
        """Retry episode processing based on its current status and failure category"""
        try:
            episode_id = candidate['episode_id']
            failure_category = candidate['failure_category']
            current_status = candidate['status']
            
            # Import processors here to avoid circular imports
            from content_processor import ContentProcessor
            
            # Initialize processor
            processor = ContentProcessor(self.db_path)
            
            # Route retry based on failure category and current status
            if failure_category == 'download' or current_status == 'pre-download':
                # Retry download and transcription
                return self._retry_download_and_transcription(processor, candidate)
            
            elif failure_category == 'transcription' or current_status == 'downloaded':
                # Retry transcription only
                return self._retry_transcription_only(processor, candidate)
            
            elif failure_category == 'scoring' or current_status == 'transcribed':
                # Retry scoring
                return self._retry_scoring(candidate)
            
            else:
                self.logger.warning(f"Unknown retry scenario for {episode_id}: {failure_category}/{current_status}")
                return False
                
        except Exception as e:
            self.logger.error(f"Exception during retry for {candidate['episode_id']}: {e}")
            self.failure_manager.log_episode_failure(
                candidate['episode_id'], 
                f"Retry failed: {str(e)}", 
                failure_category='retry'
            )
            return False
    
    def _retry_download_and_transcription(self, processor, candidate: Dict) -> bool:
        """Retry download and transcription for pre-download episodes"""
        try:
            episode_id = candidate['episode_id']
            audio_url = candidate['audio_url']
            
            if not audio_url:
                self.logger.warning(f"No audio URL for episode {episode_id}")
                return False
            
            # Download audio
            audio_file = processor._download_audio(audio_url, episode_id)
            if not audio_file:
                self.failure_manager.log_episode_failure(episode_id, "Audio download failed on retry", 'download')
                return False
            
            # Update status to downloaded
            processor._update_episode_status(candidate['db_id'], 'downloaded')
            
            # Transcribe
            transcript_path = processor._transcribe_audio(audio_file, episode_id)
            if not transcript_path:
                self.failure_manager.log_episode_failure(episode_id, "Transcription failed on retry", 'transcription')
                return False
            
            # Update status to transcribed
            processor._update_episode_status(candidate['db_id'], 'transcribed')
            
            self.logger.info(f"✅ Successfully retried download+transcription for {episode_id}")
            return True
            
        except Exception as e:
            self.failure_manager.log_episode_failure(candidate['episode_id'], f"Download retry failed: {str(e)}", 'download')
            return False
    
    def _retry_transcription_only(self, processor, candidate: Dict) -> bool:
        """Retry transcription for downloaded episodes"""
        try:
            episode_id = candidate['episode_id']
            
            # Find downloaded audio file
            audio_cache_dir = Path("audio_cache")  # Default directory
            audio_file = None
            
            for ext in ['.mp3', '.wav', '.m4a', '.mp4']:  # Common audio formats
                potential_file = audio_cache_dir / f"{episode_id}{ext}"
                if potential_file.exists():
                    audio_file = str(potential_file)
                    break
            
            if not audio_file:
                self.logger.warning(f"No cached audio file found for {episode_id}")
                return False
            
            # Transcribe
            transcript_path = processor._transcribe_audio(audio_file, episode_id)
            if not transcript_path:
                self.failure_manager.log_episode_failure(episode_id, "Transcription retry failed", 'transcription')
                return False
            
            # Update status to transcribed
            processor._update_episode_status(candidate['db_id'], 'transcribed')
            
            self.logger.info(f"✅ Successfully retried transcription for {episode_id}")
            return True
            
        except Exception as e:
            self.failure_manager.log_episode_failure(candidate['episode_id'], f"Transcription retry failed: {str(e)}", 'transcription')
            return False
    
    def _retry_scoring(self, candidate: Dict) -> bool:
        """Retry scoring for transcribed episodes"""
        try:
            episode_id = candidate['episode_id']
            
            # Import scorer here to avoid circular imports
            from openai_scorer import OpenAITopicScorer
            
            # Initialize scorer
            scorer = OpenAITopicScorer()
            
            # Retry scoring for this episode
            success = scorer.score_pending_in_db(self.db_path, max_episodes=1, target_episode_id=episode_id)
            
            if success:
                self.logger.info(f"✅ Successfully retried scoring for {episode_id}")
                return True
            else:
                self.failure_manager.log_episode_failure(episode_id, "Scoring retry failed", 'scoring')
                return False
                
        except Exception as e:
            self.failure_manager.log_episode_failure(candidate['episode_id'], f"Scoring retry failed: {str(e)}", 'scoring')
            return False

def ensure_failures_table_exists(db_path: str):
    """Ensure the episode_failures table exists in the database"""
    failure_manager = FailureManager(db_path)
    
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        failure_manager._create_failures_table(cursor)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to ensure failures table exists: {e}")
        return False

if __name__ == "__main__":
    # Test the failure management system
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python episode_failures.py <command> [args]")
        print("Commands:")
        print("  stats [days] - Show failure statistics")
        print("  retry - Process retry queue") 
        print("  cleanup [days] - Clean up old failures")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Test with both databases
    for db_name, db_path in [("RSS", "podcast_monitor.db"), ("YouTube", "youtube_transcripts.db")]:
        print(f"\n=== {db_name} Database ===")
        failure_manager = FailureManager(db_path)
        
        if command == "stats":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            stats = failure_manager.get_failure_statistics(days)
            print(f"Failure statistics for last {days} days:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
        
        elif command == "retry":
            retry_processor = RetryProcessor(db_path)
            results = retry_processor.process_retry_queue()
            print(f"Retry results: {results}")
        
        elif command == "cleanup":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            deleted = failure_manager.cleanup_old_failures(days)
            print(f"Cleaned up {deleted} old failure records")
        
        else:
            print(f"Unknown command: {command}")