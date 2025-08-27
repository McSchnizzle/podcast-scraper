#!/usr/bin/env python3
"""
Failure Analysis Tool
Analyzes failed episodes, categorizes failure patterns, and provides debugging info
"""

import sqlite3
import requests
from pathlib import Path
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi

def analyze_failed_episodes(db_path="podcast_monitor.db"):
    """Analyze all failed episodes and categorize failure reasons"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all failed episodes
        cursor.execute("""
            SELECT episode_id, title, audio_url, failure_reason
            FROM episodes 
            WHERE status = 'failed'
            ORDER BY published_date DESC
        """)
        
        failed_episodes = cursor.fetchall()
        
        if not failed_episodes:
            print("✅ No failed episodes found!")
            return
        
        print(f"🔍 Analyzing {len(failed_episodes)} failed episodes...")
        print("=" * 80)
        
        # Categorize failures
        failure_categories = {}
        
        for episode_id, title, audio_url, existing_reason in failed_episodes:
            print(f"\n📄 Episode: {title[:60]}...")
            print(f"   ID: {episode_id}")
            print(f"   URL: {audio_url}")
            
            # Determine failure reason if not already set
            if existing_reason:
                reason = existing_reason
                print(f"   Known Reason: {reason}")
            else:
                reason = determine_failure_reason(episode_id, audio_url)
                print(f"   Diagnosed Reason: {reason}")
                
                # Update database with diagnosed reason
                cursor.execute("""
                    UPDATE episodes 
                    SET failure_reason = ?, failure_timestamp = datetime('now')
                    WHERE episode_id = ?
                """, (reason, episode_id))
            
            # Categorize
            category = reason.split(':')[0] if ':' in reason else reason
            failure_categories[category] = failure_categories.get(category, 0) + 1
        
        conn.commit()
        conn.close()
        
        # Show failure summary
        print("\n" + "=" * 80)
        print("📊 FAILURE PATTERN ANALYSIS")
        print("=" * 80)
        
        for category, count in sorted(failure_categories.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(failed_episodes)) * 100
            print(f"• {category}: {count} episodes ({percentage:.1f}%)")
        
        # Provide recommendations
        print("\n💡 RECOMMENDATIONS:")
        if 'YouTube' in failure_categories:
            print("• YouTube transcript issues - implement retry logic with different language codes")
        if 'Network' in failure_categories:
            print("• Network issues - implement exponential backoff retry mechanism") 
        if 'Audio' in failure_categories:
            print("• Audio processing issues - add audio format validation and conversion")
        if 'SSL' in failure_categories:
            print("• SSL/Certificate issues - update certificates or add SSL bypass for specific domains")
            
    except Exception as e:
        print(f"❌ Analysis error: {e}")

def determine_failure_reason(episode_id, audio_url):
    """Determine why an episode failed by testing various failure modes"""
    
    # YouTube episode analysis
    if episode_id.startswith('yt:video:'):
        video_id = episode_id.replace('yt:video:', '')
        return analyze_youtube_failure(video_id)
    
    # RSS episode analysis
    else:
        return analyze_rss_failure(audio_url)

def analyze_youtube_failure(video_id):
    """Analyze why a YouTube video failed"""
    try:
        # Test transcript availability
        try:
            # Use the API instance method approach
            api = YouTubeTranscriptApi()
            transcript = api.fetch(video_id, languages=['en'])
            
            if not transcript:
                return "YouTube: Empty transcript returned"
            
            # Check transcript quality
                total_text = ' '.join([item['text'] for item in transcript])
                if len(total_text.strip()) < 100:
                    return "YouTube: Transcript too short (< 100 chars)"
                
                # If we get here, transcript should work - might be a processing issue
                return "YouTube: Transcript available but processing failed"
                
            except Exception as fetch_error:
                return f"YouTube: Transcript fetch error - {str(fetch_error)}"
                
        except Exception as list_error:
            if "disabled" in str(list_error).lower():
                return "YouTube: Transcripts disabled by uploader"
            elif "unavailable" in str(list_error).lower():
                return "YouTube: Video unavailable or private"
            else:
                return f"YouTube: API error - {str(list_error)}"
                
    except Exception as e:
        return f"YouTube: Analysis failed - {str(e)}"

def analyze_rss_failure(audio_url):
    """Analyze why an RSS episode failed"""
    try:
        if not audio_url:
            return "RSS: No audio URL provided"
        
        # Test URL accessibility
        try:
            response = requests.head(audio_url, timeout=30, allow_redirects=True)
            
            if response.status_code == 404:
                return "RSS: Audio file not found (404)"
            elif response.status_code == 403:
                return "RSS: Access forbidden (403)"
            elif response.status_code >= 500:
                return f"RSS: Server error ({response.status_code})"
            elif response.status_code != 200:
                return f"RSS: HTTP error ({response.status_code})"
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'audio' not in content_type and 'mpeg' not in content_type:
                return f"RSS: Invalid content type ({content_type})"
            
            # Check file size
            content_length = response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb < 1:
                    return "RSS: File too small (< 1MB)"
                elif size_mb > 1000:
                    return f"RSS: File very large ({size_mb:.0f}MB) - may timeout"
            
            return "RSS: Audio accessible but processing failed"
            
        except requests.exceptions.Timeout:
            return "RSS: Network timeout"
        except requests.exceptions.SSLError:
            return "RSS: SSL certificate error"
        except requests.exceptions.ConnectionError:
            return "RSS: Connection failed"
        except Exception as req_error:
            return f"RSS: Network error - {str(req_error)}"
            
    except Exception as e:
        return f"RSS: Analysis failed - {str(e)}"

def show_failure_statistics(db_path="podcast_monitor.db"):
    """Show detailed failure statistics"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("📊 DETAILED FAILURE STATISTICS")
        print("=" * 60)
        
        # Failure reasons breakdown
        cursor.execute("""
            SELECT 
                failure_reason,
                COUNT(*) as count,
                GROUP_CONCAT(SUBSTR(title, 1, 30) || '...', ' | ') as sample_titles
            FROM episodes 
            WHERE status = 'failed' AND failure_reason IS NOT NULL
            GROUP BY failure_reason
            ORDER BY count DESC
        """)
        
        failure_breakdown = cursor.fetchall()
        
        if failure_breakdown:
            for reason, count, sample_titles in failure_breakdown:
                print(f"\n🔴 {reason}: {count} episode(s)")
                print(f"   Examples: {sample_titles[:100]}...")
        else:
            print("No detailed failure reasons available")
        
        # Retry statistics
        cursor.execute("""
            SELECT 
                AVG(retry_count) as avg_retries,
                MAX(retry_count) as max_retries,
                COUNT(CASE WHEN retry_count > 0 THEN 1 END) as episodes_with_retries
            FROM episodes 
            WHERE status = 'failed'
        """)
        
        retry_stats = cursor.fetchone()
        if retry_stats and retry_stats[0]:
            print(f"\n🔄 RETRY STATISTICS:")
            print(f"   Average retries: {retry_stats[0]:.1f}")
            print(f"   Max retries: {retry_stats[1]}")
            print(f"   Episodes with retries: {retry_stats[2]}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Statistics error: {e}")

def suggest_retry_candidates(db_path="podcast_monitor.db"):
    """Suggest episodes that might succeed on retry"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find episodes with transient failure reasons that might work on retry
        cursor.execute("""
            SELECT episode_id, title, failure_reason, retry_count
            FROM episodes 
            WHERE status = 'failed' 
            AND (
                failure_reason LIKE '%timeout%' OR 
                failure_reason LIKE '%connection%' OR
                failure_reason LIKE '%server error%' OR
                failure_reason LIKE '%network%' OR
                retry_count < 2
            )
            ORDER BY retry_count ASC, published_date DESC
            LIMIT 5
        """)
        
        retry_candidates = cursor.fetchall()
        
        if retry_candidates:
            print("\n🔄 RETRY CANDIDATES (transient failures):")
            print("=" * 60)
            for episode_id, title, reason, retry_count in retry_candidates:
                print(f"• {title[:50]}...")
                print(f"  Reason: {reason}")
                print(f"  Retries: {retry_count}")
                print(f"  ID: {episode_id}")
                print()
        else:
            print("\n✅ No good retry candidates found")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Retry analysis error: {e}")

def main():
    """Main analysis function"""
    print("🔍 PODCAST EPISODE FAILURE ANALYSIS")
    print("=" * 60)
    
    analyze_failed_episodes()
    print()
    show_failure_statistics()
    print()
    suggest_retry_candidates()

if __name__ == "__main__":
    main()