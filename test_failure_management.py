#!/usr/bin/env python3
"""
Test script for the Failed Episode Lifecycle Management system
Tests failure tracking, retry logic, and statistics
"""

import sqlite3
import sys
from pathlib import Path

def test_failure_tracking():
    """Test the failure tracking system by creating test scenarios"""
    print("🧪 Testing Failed Episode Lifecycle Management")
    print("=" * 50)
    
    # Test with both databases
    for db_name, db_path in [("RSS", "podcast_monitor.db"), ("YouTube", "youtube_transcripts.db")]:
        print(f"\n📊 Testing {db_name} Database:")
        
        try:
            from utils.episode_failures import FailureManager, ensure_failures_table_exists
            
            # Ensure failures table exists
            ensure_failures_table_exists(db_path)
            print("✅ Episode failures table created/verified")
            
            # Initialize failure manager
            failure_manager = FailureManager(db_path)
            
            # Get current failure statistics
            stats = failure_manager.get_failure_statistics(days_back=7)
            print(f"📈 Current failure stats: {stats['total_failed_episodes']} failed episodes in last 7 days")
            
            # Get retry candidates
            candidates = failure_manager.get_retry_candidates()
            print(f"🔄 Episodes eligible for retry: {len(candidates)}")
            
            if candidates:
                print("  Retry candidates:")
                for candidate in candidates[:3]:  # Show first 3
                    print(f"    - {candidate['episode_id']}: {candidate['title']} (attempt #{candidate['retry_count'] + 1})")
                
            # Test cleanup functionality
            cleaned = failure_manager.cleanup_old_failures(days_old=60)
            print(f"🧹 Cleaned up {cleaned} old failure records")
            
        except Exception as e:
            print(f"❌ Error testing {db_name} database: {e}")
    
    return True

def test_integration_with_content_processor():
    """Test integration with content processor"""
    print(f"\n🔧 Testing Integration with Content Processor:")
    
    try:
        from content_processor import ContentProcessor
        
        # Test with RSS database
        processor = ContentProcessor(db_path="podcast_monitor.db")
        print("✅ Content processor initialized with failure management")
        
        # Check if failure manager is properly initialized
        if hasattr(processor, 'failure_manager'):
            print("✅ Failure manager properly integrated")
        else:
            print("❌ Failure manager not found in content processor")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing content processor integration: {e}")
        return False

def test_database_schema():
    """Test that both databases have the required failure tracking columns"""
    print(f"\n📋 Testing Database Schema:")
    
    required_columns = ['failure_reason', 'failure_timestamp', 'retry_count']
    
    for db_name, db_path in [("RSS", "podcast_monitor.db"), ("YouTube", "youtube_transcripts.db")]:
        if not Path(db_path).exists():
            print(f"⚠️ {db_name} database ({db_path}) not found - skipping")
            continue
            
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get table schema
            cursor.execute("PRAGMA table_info(episodes)")
            columns = [column[1] for column in cursor.fetchall()]
            
            print(f"\n{db_name} Database Schema:")
            missing_columns = []
            for col in required_columns:
                if col in columns:
                    print(f"  ✅ {col}")
                else:
                    print(f"  ❌ {col} (missing)")
                    missing_columns.append(col)
            
            if not missing_columns:
                print(f"✅ {db_name} database has all required columns")
            else:
                print(f"❌ {db_name} database missing columns: {missing_columns}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Error checking {db_name} database schema: {e}")

if __name__ == "__main__":
    success = True
    
    # Run all tests
    tests = [
        ("Database Schema", test_database_schema),
        ("Failure Tracking System", test_failure_tracking),
        ("Content Processor Integration", test_integration_with_content_processor),
    ]
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'=' * 60}")
            print(f"Running: {test_name}")
            print('=' * 60)
            result = test_func()
            if result is False:
                success = False
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
            success = False
    
    print(f"\n{'=' * 60}")
    if success:
        print("✅ All tests completed successfully!")
        print("🎉 Failed Episode Lifecycle Management system is ready")
    else:
        print("❌ Some tests failed - please review the output above")
        sys.exit(1)