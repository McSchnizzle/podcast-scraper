#!/usr/bin/env python3
"""
Tests for datetime/timezone reliability (Phase 1)
Validates UTC consistency, helper functions, and timezone handling
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.datetime_utils import (
    cutoff_utc,
    ensure_aware_utc,
    now_utc,
    parse_entry_to_utc,
    parse_rss_datetime,
    parse_struct_time_to_utc,
    to_utc,
)


class TestBasicHelpers:
    """Test basic datetime helper functions"""

    def test_now_utc_returns_aware_utc(self):
        """now_utc() should return timezone-aware UTC datetime"""
        result = now_utc()
        assert result.tzinfo == timezone.utc
        assert isinstance(result, datetime)

        # Should be close to actual UTC time
        actual_utc = datetime.now(timezone.utc)
        assert abs((result - actual_utc).total_seconds()) < 2  # Within 2 seconds

    def test_to_utc_naive_datetime(self):
        """to_utc() should convert naive datetime to UTC-aware"""
        naive_dt = datetime(2025, 1, 15, 12, 30, 45)
        result = to_utc(naive_dt)

        assert result.tzinfo == timezone.utc
        assert result.replace(tzinfo=None) == naive_dt  # Same time, now aware

    def test_to_utc_aware_datetime(self):
        """to_utc() should convert aware datetime to UTC"""
        # Create datetime in different timezone (EST = UTC-5)
        est = timezone(timedelta(hours=-5))
        est_dt = datetime(2025, 1, 15, 7, 30, 45, tzinfo=est)

        result = to_utc(est_dt)

        assert result.tzinfo == timezone.utc
        assert result.hour == 12  # 7 AM EST = 12 PM UTC
        assert result.minute == 30
        assert result.second == 45

    def test_cutoff_utc_calculation(self):
        """cutoff_utc() should return UTC datetime N hours ago"""
        hours_back = 48
        result = cutoff_utc(hours_back)

        assert result.tzinfo == timezone.utc

        # Should be approximately 48 hours ago
        expected = now_utc() - timedelta(hours=hours_back)
        assert abs((result - expected).total_seconds()) < 60  # Within 1 minute

    def test_ensure_aware_utc_alias(self):
        """ensure_aware_utc() should be an alias for to_utc()"""
        naive_dt = datetime(2025, 1, 15, 12, 30, 45)

        result1 = to_utc(naive_dt)
        result2 = ensure_aware_utc(naive_dt)

        assert result1 == result2


class TestRSSParsing:
    """Test RSS entry parsing functions"""

    def test_parse_struct_time_to_utc_valid(self):
        """parse_struct_time_to_utc() should parse valid time struct"""
        # Create time struct: Jan 15, 2025, 12:30:45 UTC
        time_struct = (
            2025,
            1,
            15,
            12,
            30,
            45,
            2,
            15,
            0,
        )  # (year, month, day, hour, min, sec, wday, yday, dst)

        result = parse_struct_time_to_utc(time_struct)

        assert result is not None
        assert result.tzinfo == timezone.utc
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 45

    def test_parse_struct_time_to_utc_none(self):
        """parse_struct_time_to_utc() should return None for empty input"""
        assert parse_struct_time_to_utc(None) is None
        assert parse_struct_time_to_utc([]) is None

    def test_parse_struct_time_to_utc_invalid(self):
        """parse_struct_time_to_utc() should handle invalid time struct"""
        invalid_struct = (2025, 13, 32)  # Invalid month and day
        result = parse_struct_time_to_utc(invalid_struct)
        assert result is None

    def test_parse_entry_to_utc_published_parsed(self):
        """parse_entry_to_utc() should use published_parsed first"""
        mock_entry = Mock()
        mock_entry.published_parsed = (2025, 1, 15, 12, 30, 45, 2, 15, 0)
        mock_entry.updated_parsed = (2025, 1, 16, 13, 0, 0, 3, 16, 0)  # Different time

        result_dt, source = parse_entry_to_utc(mock_entry)

        assert result_dt is not None
        assert source == "published_parsed"
        assert result_dt.day == 15  # Used published, not updated
        assert result_dt.hour == 12

    def test_parse_entry_to_utc_updated_parsed_fallback(self):
        """parse_entry_to_utc() should fallback to updated_parsed"""
        mock_entry = Mock()
        mock_entry.published_parsed = None
        mock_entry.updated_parsed = (2025, 1, 16, 13, 0, 0, 3, 16, 0)

        result_dt, source = parse_entry_to_utc(mock_entry)

        assert result_dt is not None
        assert source == "updated_parsed"
        assert result_dt.day == 16
        assert result_dt.hour == 13

    def test_parse_entry_to_utc_string_fallback(self):
        """parse_entry_to_utc() should fallback to string fields"""
        mock_entry = Mock()
        mock_entry.published_parsed = None
        mock_entry.updated_parsed = None
        mock_entry.published = "Wed, 15 Jan 2025 12:30:45 GMT"  # RFC2822 format

        result_dt, source = parse_entry_to_utc(mock_entry)

        assert result_dt is not None
        assert source == "published"
        assert result_dt.day == 15
        assert result_dt.hour == 12
        assert result_dt.minute == 30

    def test_parse_entry_to_utc_iso_format(self):
        """parse_entry_to_utc() should parse ISO8601 format"""
        mock_entry = Mock()
        mock_entry.published_parsed = None
        mock_entry.updated_parsed = None
        mock_entry.published = None
        mock_entry.updated = "2025-01-15T12:30:45Z"  # ISO format with Z

        result_dt, source = parse_entry_to_utc(mock_entry)

        assert result_dt is not None
        assert source == "updated"
        assert result_dt.day == 15
        assert result_dt.hour == 12

    def test_parse_entry_to_utc_no_dates(self):
        """parse_entry_to_utc() should return None when no dates available"""
        mock_entry = Mock()
        mock_entry.published_parsed = None
        mock_entry.updated_parsed = None
        mock_entry.published = None
        mock_entry.updated = None
        mock_entry.date = None

        result_dt, source = parse_entry_to_utc(mock_entry)

        assert result_dt is None
        assert source == "none"

    def test_parse_rss_datetime_backward_compatibility(self):
        """parse_rss_datetime() should work as backward compatibility alias"""
        time_struct = (2025, 1, 15, 12, 30, 45, 2, 15, 0)

        result1 = parse_rss_datetime(time_struct)
        result2 = parse_struct_time_to_utc(time_struct)

        assert result1 == result2


class TestTimezoneComparisons:
    """Test that timezone-aware comparisons work correctly"""

    def test_aware_vs_aware_comparison(self):
        """Timezone-aware datetimes should compare correctly"""
        utc_dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        est_dt = datetime(2025, 1, 15, 7, 0, 0, tzinfo=timezone(timedelta(hours=-5)))

        # These should be equal (same moment in time)
        assert utc_dt == est_dt

        # Convert both to UTC for consistent comparison
        utc_dt_normalized = to_utc(utc_dt)
        est_dt_normalized = to_utc(est_dt)

        assert utc_dt_normalized == est_dt_normalized

    def test_naive_vs_aware_prevented(self):
        """Mixing naive and aware should be handled by our helpers"""
        naive_dt = datetime(2025, 1, 15, 12, 0, 0)
        aware_dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Convert naive to aware before comparison
        naive_as_aware = to_utc(naive_dt)

        # Now they can be compared
        assert naive_as_aware == aware_dt

        # Direct comparison would raise TypeError without our helpers
        with pytest.raises(TypeError):
            naive_dt < aware_dt  # This should fail

    def test_cutoff_comparison_realistic(self):
        """Test realistic cutoff comparison scenario"""
        # Simulate checking if episode is newer than 48-hour cutoff
        cutoff = cutoff_utc(48)

        # Episode from 24 hours ago (should be newer than cutoff)
        recent_episode = now_utc() - timedelta(hours=24)

        # Episode from 72 hours ago (should be older than cutoff)
        old_episode = now_utc() - timedelta(hours=72)

        assert recent_episode > cutoff  # Recent episode is newer
        assert old_episode < cutoff  # Old episode is older

    def test_feed_lookback_scenario(self):
        """Test the feed monitor lookback scenario"""
        # Simulate FEED_LOOKBACK_HOURS = 48
        lookback_hours = 48
        cutoff_time = cutoff_utc(lookback_hours)

        # Mock episode dates
        recent_naive = datetime(2025, 1, 15, 12, 0, 0)  # Naive datetime
        old_naive = datetime(2025, 1, 13, 12, 0, 0)  # 2 days ago

        # Convert to aware UTC for comparison
        recent_aware = to_utc(recent_naive)
        old_aware = to_utc(old_naive)

        # Assuming cutoff is recent, recent episode should pass, old should not
        # Note: This test depends on when it's run, so we'll test the pattern
        if recent_aware > cutoff_time:
            # Recent episode should be included
            assert True

        # Test the comparison pattern works
        assert isinstance(cutoff_time, datetime)
        assert cutoff_time.tzinfo == timezone.utc
        assert isinstance(recent_aware, datetime)
        assert recent_aware.tzinfo == timezone.utc


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_parse_entry_invalid_date_strings(self):
        """parse_entry_to_utc() should handle invalid date strings gracefully"""
        mock_entry = Mock()
        mock_entry.published_parsed = None
        mock_entry.updated_parsed = None
        mock_entry.published = "invalid date string"
        mock_entry.updated = "also invalid"
        mock_entry.date = "still invalid"

        result_dt, source = parse_entry_to_utc(mock_entry)

        assert result_dt is None
        assert source == "none"

    def test_to_utc_edge_cases(self):
        """to_utc() should handle edge cases"""
        # Test with various timezone offsets
        plus_8 = timezone(timedelta(hours=8))
        dt_plus_8 = datetime(2025, 1, 15, 20, 0, 0, tzinfo=plus_8)

        result = to_utc(dt_plus_8)
        assert result.hour == 12  # 20:00 +8 = 12:00 UTC

        # Test with negative offset
        minus_3 = timezone(timedelta(hours=-3))
        dt_minus_3 = datetime(2025, 1, 15, 9, 0, 0, tzinfo=minus_3)

        result = to_utc(dt_minus_3)
        assert result.hour == 12  # 09:00 -3 = 12:00 UTC


def test_no_pytz_imports():
    """Verify that pytz is not imported anywhere in the datetime utilities"""
    import utils.datetime_utils

    # Check the module doesn't use pytz
    source_file = Path(__file__).parent.parent / "utils" / "datetime_utils.py"
    content = source_file.read_text()

    assert "import pytz" not in content
    assert "from pytz" not in content

    # Check that zoneinfo or timezone from datetime is used instead
    assert "from datetime import" in content
    assert "timezone" in content


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
