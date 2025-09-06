#!/usr/bin/env python3
"""
Pytest configuration and fixtures for podcast scraper tests.
Includes monkeypatch to prevent direct sqlite3.connect usage.
"""

import logging
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session", autouse=True)
def enforce_db_connection_factory():
    """
    Monkeypatch sqlite3.connect to prevent direct usage in tests.
    This ensures all database connections use our connection factory.
    """
    original_connect = sqlite3.connect

    def patched_connect(*args, **kwargs):
        import inspect

        # Get the calling frame to see where connect was called from
        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back
            caller_filename = caller_frame.f_code.co_filename
            caller_function = caller_frame.f_code.co_name

            # Allow direct connections from our db.py module
            if "utils/db.py" in caller_filename or "utils\\db.py" in caller_filename:
                return original_connect(*args, **kwargs)

            # Allow direct connections in migration scripts (they need low-level access)
            if "migrate_" in caller_filename or "verify_schema" in caller_filename:
                return original_connect(*args, **kwargs)

            # Allow direct connections in test files that explicitly test sqlite3
            if "test_" in caller_filename and "sqlite3" in caller_function.lower():
                return original_connect(*args, **kwargs)

            # Block all other direct usage
            raise RuntimeError(
                f"Direct sqlite3.connect() usage detected in {caller_filename}:{caller_frame.f_lineno} "
                f"(function: {caller_function}). Use utils.db.get_connection() instead."
            )

        finally:
            del frame

    # Apply the monkeypatch
    sqlite3.connect = patched_connect

    # Yield to run tests
    yield

    # Restore original function after tests
    sqlite3.connect = original_connect


@pytest.fixture
def temp_database():
    """
    Create a temporary database for testing.
    Automatically cleaned up after test.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = f.name

    yield temp_db_path

    # Cleanup
    Path(temp_db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_directory():
    """
    Create a temporary directory for testing.
    Automatically cleaned up after test.
    """
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def setup_test_logging():
    """Setup logging for tests"""
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise in test output
        format="%(name)s - %(levelname)s - %(message)s",
    )


@pytest.fixture
def mock_podcast_episode():
    """Sample podcast episode data for testing"""
    return {
        "episode_id": "test_episode_123",
        "title": "Test Episode Title",
        "published_date": "2023-09-01T10:00:00Z",
        "audio_url": "https://example.com/audio.mp3",
        "feed_id": 1,
        "status": "pre-download",
    }


@pytest.fixture
def mock_feed_data():
    """Sample feed data for testing"""
    return {
        "id": 1,
        "title": "Test Podcast Feed",
        "url": "https://example.com/rss",
        "type": "rss",
        "topic_category": "technology",
        "active": 1,
    }


def pytest_configure(config):
    """Pytest configuration hook"""
    # Ensure test environment is properly set up
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    # Add custom markers
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (may be slow)"
    )
    config.addinivalue_line(
        "markers", "database: mark test as requiring database setup"
    )
    config.addinivalue_line("markers", "network: mark test as requiring network access")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names"""
    for item in items:
        # Mark integration tests
        if "integration" in item.nodeid.lower():
            item.add_marker(pytest.mark.integration)

        # Mark database tests
        if "database" in item.nodeid.lower() or "db" in item.nodeid.lower():
            item.add_marker(pytest.mark.database)

        # Mark network tests
        if "network" in item.nodeid.lower() or "http" in item.nodeid.lower():
            item.add_marker(pytest.mark.network)
