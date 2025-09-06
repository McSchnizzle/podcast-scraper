#!/usr/bin/env python3
"""
Startup Preflight Logging for Podcast Scraper

PID-guarded one-time logging of critical database and system settings.
Prevents noisy logs during multi-module imports/starts.
"""

import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from utils.db import EXPECTED_SCHEMA_VERSION, get_connection

logger = logging.getLogger(__name__)

# Global state to track if preflight has already run for this process
_PREFLIGHT_COMPLETED = False
_CURRENT_PID = None


class StartupPreflight:
    """
    One-time startup preflight checks with PID guarding.

    Logs critical system information exactly once per process:
    - SQLite version and configuration
    - Database schema versions and settings
    - Foreign key enforcement status
    - Journal mode and synchronization settings
    """

    @classmethod
    def run_preflight_checks(cls, db_paths: Optional[list] = None) -> Dict[str, Any]:
        """
        Run comprehensive startup preflight checks with PID guarding.

        Args:
            db_paths: List of database paths to check.
                     Defaults to ['podcast_monitor.db', 'youtube_transcripts.db']

        Returns:
            Dict containing all preflight check results

        Note:
            This function is PID-guarded and will only execute once per process.
            Subsequent calls return cached results or empty dict if already run.
        """

        global _PREFLIGHT_COMPLETED, _CURRENT_PID

        # PID guard: only run once per process
        current_pid = os.getpid()
        if _PREFLIGHT_COMPLETED and _CURRENT_PID == current_pid:
            logger.debug(f"Preflight checks already completed for PID {current_pid}")
            return {}

        # Set up defaults
        if db_paths is None:
            db_paths = ["podcast_monitor.db", "youtube_transcripts.db"]

        results = {
            "pid": current_pid,
            "sqlite_version": None,
            "databases": {},
            "system_info": {},
        }

        try:
            # Log startup header
            logger.info("🚀 Podcast Scraper Startup Preflight Checks")
            logger.info(f"   Process ID: {current_pid}")

            # Check SQLite version
            sqlite_version = sqlite3.sqlite_version
            results["sqlite_version"] = sqlite_version
            logger.info(f"   SQLite Version: {sqlite_version}")

            # Check each database
            for db_path in db_paths:
                if not Path(db_path).exists():
                    logger.warning(f"   Database not found: {db_path}")
                    continue

                db_info = cls._check_database_settings(db_path)
                results["databases"][db_path] = db_info

                # Log database status
                logger.info(f"   Database: {db_path}")
                logger.info(
                    f"     - Foreign Keys: {'ON' if db_info.get('foreign_keys') == 1 else 'OFF'}"
                )
                logger.info(
                    f"     - Journal Mode: {db_info.get('journal_mode', 'UNKNOWN')}"
                )
                logger.info(
                    f"     - Synchronous: {db_info.get('synchronous', 'UNKNOWN')}"
                )
                logger.info(
                    f"     - Schema Version: {db_info.get('user_version', 'UNKNOWN')} (expected: {EXPECTED_SCHEMA_VERSION})"
                )

            # System information
            results["system_info"] = {
                "python_version": sys.version.split()[0],
                "platform": sys.platform,
                "working_directory": str(Path.cwd()),
            }

            logger.info(
                f"   Python Version: {results['system_info']['python_version']}"
            )
            logger.info(f"   Platform: {results['system_info']['platform']}")
            logger.info("✅ Startup preflight checks completed")

            # Mark as completed for this PID
            _PREFLIGHT_COMPLETED = True
            _CURRENT_PID = current_pid

            return results

        except Exception as e:
            logger.error(f"❌ Preflight checks failed: {e}")
            results["error"] = str(e)
            return results

    @classmethod
    def _check_database_settings(cls, db_path: str) -> Dict[str, Any]:
        """
        Check database configuration settings.

        Args:
            db_path: Path to SQLite database

        Returns:
            Dict containing database configuration
        """

        settings = {}

        try:
            with get_connection(db_path, readonly=True, validate_schema=False) as conn:
                # Check PRAGMA settings
                pragma_checks = [
                    "foreign_keys",
                    "journal_mode",
                    "synchronous",
                    "user_version",
                    "cache_size",
                    "temp_store",
                ]

                for pragma in pragma_checks:
                    try:
                        cursor = conn.execute(f"PRAGMA {pragma}")
                        result = cursor.fetchone()
                        settings[pragma] = result[0] if result else None
                    except sqlite3.Error as e:
                        logger.debug(f"Could not check PRAGMA {pragma}: {e}")
                        settings[pragma] = None

        except Exception as e:
            logger.warning(f"Could not check database settings for {db_path}: {e}")
            settings["error"] = str(e)

        return settings


def run_startup_preflight(db_paths: Optional[list] = None) -> Dict[str, Any]:
    """
    Convenience function to run startup preflight checks.

    Args:
        db_paths: Optional list of database paths to check

    Returns:
        Dict containing preflight results

    Example:
        >>> from utils.startup_preflight import run_startup_preflight
        >>> results = run_startup_preflight()
        >>> # Logs will only appear once per process
    """

    return StartupPreflight.run_preflight_checks(db_paths)


# Module-level convenience for imports
preflight_check = run_startup_preflight

if __name__ == "__main__":
    # Allow running as standalone script
    import sys
    from pathlib import Path

    # Set up basic logging for standalone execution
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Run preflight with command line database paths if provided
    db_paths = sys.argv[1:] if len(sys.argv) > 1 else None
    results = run_startup_preflight(db_paths)

    # Exit with appropriate code
    if "error" in results:
        sys.exit(1)
    else:
        print(f"✅ Preflight checks completed for PID {results.get('pid', 'unknown')}")
        sys.exit(0)
