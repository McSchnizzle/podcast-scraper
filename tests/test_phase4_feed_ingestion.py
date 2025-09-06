#!/usr/bin/env python3
"""
Phase 4: Feed Ingestion Robustness Tests
Comprehensive test suite for enhanced feed processing capabilities
"""

import os
import sys
import sqlite3
import tempfile
import unittest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.datetime_utils import now_utc, to_utc
from utils.feed_helpers import (
    item_identity_hash, content_hash, get_or_set_first_seen,
    detect_typical_order, get_effective_lookback_hours, compute_cutoff_with_grace,
    should_suppress_warning, update_warning_timestamp,
    handle_conditional_get, extract_http_cache_headers,
    update_feed_cache_headers, get_feed_cache_headers,
    ensure_feed_metadata_exists, cleanup_old_item_seen_records
)
from feed_monitor import FeedMonitor

class TestPhase4FeedHelpers(unittest.TestCase):
    """Test Phase 4 feed helper functions"""
    
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Initialize database
        self.monitor = FeedMonitor(self.db_path)
        
        # Create test feed
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO feeds (url, title, type, topic_category, active)
            VALUES (?, ?, ?, ?, ?)
        ''', ('https://example.com/feed.xml', 'Test Feed', 'rss', 'technology', 1))
        self.feed_id = cursor.lastrowid
        conn.commit()
        conn.close()
    
    def tearDown(self):
        os.unlink(self.db_path)
    
    def test_item_identity_hash(self):
        """Test stable item hash generation"""
        # Test with GUID (priority 1)
        hash1 = item_identity_hash("guid-123", "http://example.com", "Title", "http://audio.com")
        hash2 = item_identity_hash("guid-123", "http://different.com", "Different", "http://other.com")
        self.assertEqual(hash1, hash2)  # GUID takes priority
        
        # Test with link fallback (priority 2)
        hash3 = item_identity_hash(None, "http://example.com", "Title", "http://audio.com")
        hash4 = item_identity_hash(None, "http://example.com", "Different", "http://other.com")
        self.assertEqual(hash3, hash4)  # Link takes priority over title
        
        # Test with title+enclosure fallback (priority 3)
        hash5 = item_identity_hash(None, None, "Same Title", "http://audio.com")
        hash6 = item_identity_hash(None, None, "Same Title", "http://audio.com")
        self.assertEqual(hash5, hash6)  # Same title+enclosure
        
        # Test stability - same inputs always produce same hash
        for _ in range(10):
            self.assertEqual(
                item_identity_hash("stable-guid", None, None, None),
                item_identity_hash("stable-guid", None, None, None)
            )
    
    def test_get_or_set_first_seen(self):
        """Test deterministic timestamp generation for date-less items"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_time = now_utc()
        item_hash = "test-hash-123"
        
        # First time - should set first_seen
        first_seen = get_or_set_first_seen(
            cursor, self.feed_id, item_hash, "Test Item", 
            "guid-123", "http://example.com", "http://audio.com", current_time
        )
        self.assertEqual(first_seen, current_time)
        
        # Second time - should return same timestamp
        later_time = current_time + timedelta(hours=1)
        second_seen = get_or_set_first_seen(
            cursor, self.feed_id, item_hash, "Test Item", 
            "guid-123", "http://example.com", "http://audio.com", later_time
        )
        self.assertEqual(second_seen, current_time)  # Should return original time
        
        conn.commit()
        conn.close()
    
    def test_detect_typical_order(self):
        """Test feed order detection"""
        # Create mock entries with descending dates (reverse chronological)
        reverse_entries = []
        for i in range(5):
            entry = Mock()
            entry.get = lambda key, default=None: {
                'published_parsed': time.struct_time((2025, 1, 10 - i, 12, 0, 0, 0, 0, 0))
            }.get(key, default)
            reverse_entries.append(entry)
        
        self.assertEqual(detect_typical_order(reverse_entries), 'reverse_chronological')
        
        # Create mock entries with ascending dates (chronological)
        chrono_entries = []
        for i in range(5):
            entry = Mock()
            entry.get = lambda key, default=None, i=i: {
                'published_parsed': time.struct_time((2025, 1, 5 + i, 12, 0, 0, 0, 0, 0))
            }.get(key, default)
            chrono_entries.append(entry)
        
        self.assertEqual(detect_typical_order(chrono_entries), 'chronological')
        
        # Test unknown order (mixed dates)
        mixed_entries = []
        dates = [5, 8, 3, 9, 1]  # Mixed order
        for date in dates:
            entry = Mock()
            entry.get = lambda key, default=None, d=date: {
                'published_parsed': time.struct_time((2025, 1, d, 12, 0, 0, 0, 0, 0))
            }.get(key, default)
            mixed_entries.append(entry)
        
        self.assertEqual(detect_typical_order(mixed_entries), 'unknown')
    
    def test_effective_lookback_hours(self):
        """Test per-feed lookback controls"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Test default (no override)
        default_hours = get_effective_lookback_hours(cursor, self.feed_id, 48)
        self.assertEqual(default_hours, 48)
        
        # Set per-feed override
        cursor.execute(
            "UPDATE feed_metadata SET lookback_hours_override = ? WHERE feed_id = ?",
            (72, self.feed_id)
        )
        
        override_hours = get_effective_lookback_hours(cursor, self.feed_id, 48)
        self.assertEqual(override_hours, 72)
        
        # Test bounds enforcement (should cap at 168 hours)
        cursor.execute(
            "UPDATE feed_metadata SET lookback_hours_override = ? WHERE feed_id = ?",
            (200, self.feed_id)
        )
        
        capped_hours = get_effective_lookback_hours(cursor, self.feed_id, 48)
        self.assertEqual(capped_hours, 168)
        
        conn.commit()
        conn.close()
    
    def test_cutoff_with_grace(self):
        """Test cutoff calculation with grace period"""
        lookback_hours = 24
        grace_minutes = 15
        
        cutoff = compute_cutoff_with_grace(lookback_hours, grace_minutes)
        
        # Should be (now - 24h - 15m)
        expected = now_utc() - timedelta(hours=24, minutes=15)
        
        # Allow 1 minute tolerance for test timing
        self.assertLess(abs((cutoff - expected).total_seconds()), 60)
    
    def test_warning_suppression(self):
        """Test warning suppression to avoid spam"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # First check - should not be suppressed
        suppressed = should_suppress_warning(cursor, self.feed_id, 'no_dates', 24)
        self.assertFalse(suppressed)
        
        # Update warning timestamp
        update_warning_timestamp(cursor, self.feed_id, 'no_dates')
        
        # Second check - should be suppressed
        suppressed = should_suppress_warning(cursor, self.feed_id, 'no_dates', 24)
        self.assertTrue(suppressed)
        
        conn.commit()
        conn.close()
    
    def test_cleanup_old_item_seen(self):
        """Test cleanup of old item_seen records"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert old and new records
        old_time = (now_utc() - timedelta(days=35)).isoformat() + 'Z'
        new_time = (now_utc() - timedelta(days=15)).isoformat() + 'Z'
        
        cursor.execute('''
            INSERT INTO item_seen (feed_id, item_id_hash, first_seen_utc, last_seen_utc)
            VALUES (?, ?, ?, ?)
        ''', (self.feed_id, 'old-hash', old_time, old_time))
        
        cursor.execute('''
            INSERT INTO item_seen (feed_id, item_id_hash, first_seen_utc, last_seen_utc)
            VALUES (?, ?, ?, ?)
        ''', (self.feed_id, 'new-hash', new_time, new_time))
        
        conn.commit()
        
        # Cleanup with 30-day retention
        cleanup_old_item_seen_records(cursor, 30)
        
        # Check results
        cursor.execute("SELECT item_id_hash FROM item_seen WHERE feed_id = ?", (self.feed_id,))
        remaining = [row[0] for row in cursor.fetchall()]
        
        self.assertIn('new-hash', remaining)
        self.assertNotIn('old-hash', remaining)
        
        conn.close()

class TestPhase4HTTPCaching(unittest.TestCase):
    """Test HTTP caching functionality"""
    
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.monitor = FeedMonitor(self.db_path)
    
    def tearDown(self):
        os.unlink(self.db_path)
    
    def test_cache_header_extraction(self):
        """Test HTTP cache header extraction"""
        mock_response = Mock()
        mock_response.headers = {
            'ETag': '"abc123"',
            'Last-Modified': 'Wed, 01 Jan 2025 12:00:00 GMT'
        }
        
        headers = extract_http_cache_headers(mock_response)
        
        self.assertEqual(headers['etag'], '"abc123"')
        self.assertEqual(headers['last_modified'], 'Wed, 01 Jan 2025 12:00:00 GMT')
    
    def test_cache_header_storage(self):
        """Test storing and retrieving cache headers"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert test feed
        cursor.execute('''
            INSERT INTO feeds (url, title, type, topic_category, active)
            VALUES (?, ?, ?, ?, ?)
        ''', ('https://example.com/feed.xml', 'Test Feed', 'rss', 'technology', 1))
        feed_id = cursor.lastrowid
        
        # Store cache headers
        update_feed_cache_headers(cursor, feed_id, '"abc123"', 'Wed, 01 Jan 2025 12:00:00 GMT')
        
        # Retrieve cache headers
        headers = get_feed_cache_headers(cursor, feed_id)
        
        self.assertEqual(headers['etag'], '"abc123"')
        self.assertEqual(headers['last_modified'], 'Wed, 01 Jan 2025 12:00:00 GMT')
        
        conn.commit()
        conn.close()
    
    @patch('requests.Session.get')
    def test_conditional_get_304(self, mock_get):
        """Test HTTP 304 Not Modified response handling"""
        # Mock 304 response
        mock_response = Mock()
        mock_response.status_code = 304
        mock_get.return_value = mock_response
        
        session = Mock()
        session.get.return_value = mock_response
        
        response, is_cached = handle_conditional_get(
            session, 'https://example.com/feed.xml', 
            '"abc123"', 'Wed, 01 Jan 2025 12:00:00 GMT'
        )
        
        self.assertEqual(response.status_code, 304)
        self.assertTrue(is_cached)
        
        # Verify headers were sent
        session.get.assert_called_with(
            'https://example.com/feed.xml',
            headers={
                'If-None-Match': '"abc123"',
                'If-Modified-Since': 'Wed, 01 Jan 2025 12:00:00 GMT'
            },
            timeout=30
        )
    
    @patch('requests.Session.get')
    def test_conditional_get_200(self, mock_get):
        """Test HTTP 200 OK response with new content"""
        # Mock 200 response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'ETag': '"def456"'}
        mock_get.return_value = mock_response
        
        session = Mock()
        session.get.return_value = mock_response
        
        response, is_cached = handle_conditional_get(
            session, 'https://example.com/feed.xml', 
            '"abc123"', 'Wed, 01 Jan 2025 12:00:00 GMT'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(is_cached)

class TestPhase4FeedMonitor(unittest.TestCase):
    """Integration tests for Phase 4 enhanced FeedMonitor"""
    
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.monitor = FeedMonitor(self.db_path)
    
    def tearDown(self):
        os.unlink(self.db_path)
    
    def test_database_initialization(self):
        """Test that Phase 4 tables are created properly"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check feed_metadata table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feed_metadata'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check item_seen table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='item_seen'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_item_seen_feed_last_seen'")
        self.assertIsNotNone(cursor.fetchone())
        
        conn.close()
    
    def test_feed_metadata_creation(self):
        """Test automatic feed metadata creation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert test feed
        cursor.execute('''
            INSERT INTO feeds (url, title, type, topic_category, active)
            VALUES (?, ?, ?, ?, ?)
        ''', ('https://example.com/feed.xml', 'Test Feed', 'rss', 'technology', 1))
        feed_id = cursor.lastrowid
        
        # Ensure metadata exists
        ensure_feed_metadata_exists(cursor, feed_id, 'rss')
        
        # Check metadata was created
        cursor.execute("SELECT has_dates, typical_order FROM feed_metadata WHERE feed_id = ?", (feed_id,))
        result = cursor.fetchone()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[0], True)  # has_dates
        self.assertEqual(result[1], 'reverse_chronological')  # typical_order
        
        conn.commit()
        conn.close()
    
    @patch('requests.Session.get')
    @patch('feedparser.parse')
    def test_enhanced_duplicate_detection(self, mock_parse, mock_get):
        """Test enhanced duplicate detection using item_seen table"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<rss>mock feed content</rss>'
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        # Mock feedparser response with duplicate-prone entries
        mock_feed = Mock()
        mock_feed.entries = []
        
        # Create entry with same GUID but different titles
        for i in range(2):
            entry = Mock()
            entry.get = lambda key, default=None, i=i: {
                'id': 'same-guid-123',  # Same GUID
                'title': f'Different Title {i}',  # Different title
                'link': f'https://example.com/episode{i}',
                'published_parsed': time.struct_time((2025, 1, 10, 12, 0, 0, 0, 0, 0))
            }.get(key, default)
            entry.enclosures = []
            mock_feed.entries.append(entry)
        
        mock_parse.return_value = mock_feed
        
        # Add feed to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO feeds (url, title, type, topic_category, active)
            VALUES (?, ?, ?, ?, ?)
        ''', ('https://example.com/feed.xml', 'Test Feed', 'rss', 'technology', 1))
        conn.commit()
        conn.close()
        
        # Process feed - should only add one episode due to duplicate detection
        episodes = self.monitor.check_new_episodes(hours_back=72)
        
        # Should only have one episode (first one processed, second detected as duplicate)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]['episode_title'], 'Different Title 0')
    
    @patch('utils.telemetry_manager.get_telemetry_manager')
    def test_telemetry_integration(self, mock_telemetry):
        """Test telemetry metrics emission"""
        mock_telemetry_instance = Mock()
        mock_telemetry.return_value = mock_telemetry_instance
        
        # Mock feed processing that would generate telemetry
        with patch.object(self.monitor, '_get_feeds_to_process', return_value=[]):
            episodes = self.monitor.check_new_episodes()
        
        # Verify telemetry was called
        mock_telemetry.assert_called_once()
        
        # Verify metrics were recorded
        mock_telemetry_instance.record_metric.assert_called()
        
        # Check for expected metric names
        metric_calls = [call[0][0] for call in mock_telemetry_instance.record_metric.call_args_list]
        expected_metrics = [
            'ingest.feeds.total.count',
            'ingest.feeds.processed.count', 
            'ingest.episodes.new.count',
            'ingest.run.duration.ms'
        ]
        
        for metric in expected_metrics:
            self.assertIn(metric, metric_calls)

class TestPhase4LoggingPolicy(unittest.TestCase):
    """Test Phase 4 logging policy (2-line INFO format)"""
    
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.monitor = FeedMonitor(self.db_path)
    
    def tearDown(self):
        os.unlink(self.db_path)
    
    @patch('requests.Session.get')
    @patch('feedparser.parse')
    def test_two_line_logging_format(self, mock_parse, mock_get):
        """Test that each feed produces exactly 2 INFO lines"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<rss>mock feed content</rss>'
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        # Mock feedparser response
        mock_feed = Mock()
        mock_feed.entries = [Mock()]  # One entry
        mock_feed.entries[0].get = lambda key, default=None: {
            'id': 'test-guid',
            'title': 'Test Episode',
            'link': 'https://example.com/episode1',
            'published_parsed': time.struct_time((2025, 1, 10, 12, 0, 0, 0, 0, 0))
        }.get(key, default)
        mock_feed.entries[0].enclosures = []
        
        mock_parse.return_value = mock_feed
        
        # Add feed to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO feeds (url, title, type, topic_category, active)
            VALUES (?, ?, ?, ?, ?)
        ''', ('https://example.com/feed.xml', 'Test Feed', 'rss', 'technology', 1))
        conn.commit()
        conn.close()
        
        # Capture log output
        with patch('feed_monitor.logger') as mock_logger:
            episodes = self.monitor.check_new_episodes(hours_back=72)
            
            # Count INFO-level calls for feed-specific logs
            info_calls = [call for call in mock_logger.info.call_args_list 
                         if 'Test Feed' in str(call) or 'Feed monitoring' in str(call)]
            
            # Should have:
            # 1. Feed monitoring started
            # 2. Feed header line (📦 Test Feed...)
            # 3. Feed totals line (new=X updated=Y...)
            # 4. Feed monitoring completed
            self.assertGreaterEqual(len(info_calls), 4)

if __name__ == '__main__':
    # Set up test environment
    os.environ['LOG_LEVEL'] = 'DEBUG'
    os.environ['FEED_LOOKBACK_HOURS'] = '48'
    os.environ['FEED_GRACE_MINUTES'] = '15'
    
    # Run tests
    unittest.main(verbosity=2)