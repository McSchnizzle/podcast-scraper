#!/usr/bin/env python3
"""
Startup Preflight Checks for Podcast Scraper

Validates database health and system readiness at startup.
Fail fast if critical issues are detected.
"""

import logging
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent))
from utils.db import EXPECTED_SCHEMA_VERSION, get_connection

logger = logging.getLogger(__name__)


class StartupValidator:
    """
    Validates system readiness at startup.
    Designed to fail fast if critical issues are detected.
    """

    def __init__(self, databases: Optional[List[str]] = None):
        """
        Initialize startup validator.

        Args:
            databases: List of database paths to check. If None, uses defaults.
        """
        self.databases = databases or ["podcast_monitor.db", "youtube_transcripts.db"]
        self.errors = []
        self.warnings = []

    def run_all_checks(self, strict: bool = True) -> bool:
        """
        Run all startup validation checks.

        Args:
            strict: If True, warnings are treated as failures

        Returns:
            True if system is ready, False if critical issues found
        """
        logger.info("Running startup validation checks...")

        try:
            # Check database files exist
            self._check_database_files_exist()

            # Check database connectivity and basic health
            for db_path in self.databases:
                if Path(db_path).exists():
                    self._check_database_health(db_path)

            # System-wide checks
            self._check_required_directories()
            self._check_environment_variables()

            # Evaluate results
            has_errors = len(self.errors) > 0
            has_warnings = len(self.warnings) > 0

            if has_errors:
                logger.error(
                    f"❌ Startup validation failed with {len(self.errors)} errors"
                )
                for error in self.errors:
                    logger.error(f"  ERROR: {error}")
                return False
            elif strict and has_warnings:
                logger.error(
                    f"❌ Startup validation failed in strict mode with {len(self.warnings)} warnings"
                )
                for warning in self.warnings:
                    logger.error(f"  WARNING: {warning}")
                return False
            elif has_warnings:
                logger.warning(
                    f"⚠️ Startup validation passed with {len(self.warnings)} warnings"
                )
                for warning in self.warnings:
                    logger.warning(f"  WARNING: {warning}")
                return True
            else:
                logger.info("✅ All startup validation checks passed")
                return True

        except Exception as e:
            logger.error(f"❌ Startup validation failed with exception: {e}")
            return False

    def _check_database_files_exist(self) -> None:
        """Check that required database files exist"""

        missing_dbs = []
        for db_path in self.databases:
            if not Path(db_path).exists():
                missing_dbs.append(db_path)

        if missing_dbs:
            if len(missing_dbs) == len(self.databases):
                self.errors.append(f"All database files missing: {missing_dbs}")
            else:
                self.warnings.append(f"Some database files missing: {missing_dbs}")
        else:
            logger.debug(f"✅ All database files exist: {self.databases}")

    def _check_database_health(self, db_path: str) -> None:
        """
        Check database health and schema integrity.

        Args:
            db_path: Path to database file
        """
        logger.debug(f"Checking database health: {db_path}")

        try:
            # Test connection with our factory (this validates FK enforcement)
            with get_connection(db_path, readonly=True, validate_schema=False) as conn:
                cursor = conn.cursor()

                # Check foreign key enforcement
                cursor.execute("PRAGMA foreign_keys")
                fk_status = cursor.fetchone()[0]
                if fk_status != 1:
                    self.errors.append(
                        f"Foreign keys not enabled in {db_path} (status: {fk_status})"
                    )
                else:
                    logger.debug(f"  ✅ Foreign keys enabled: {db_path}")

                # Check schema version
                cursor.execute("PRAGMA user_version")
                current_version = cursor.fetchone()[0]

                if current_version == 0:
                    self.warnings.append(
                        f"Schema version not set in {db_path} (user_version=0)"
                    )
                elif current_version < EXPECTED_SCHEMA_VERSION:
                    self.errors.append(
                        f"Schema version outdated in {db_path}: "
                        f"current={current_version}, expected={EXPECTED_SCHEMA_VERSION}"
                    )
                elif current_version > EXPECTED_SCHEMA_VERSION:
                    self.warnings.append(
                        f"Schema version newer than expected in {db_path}: "
                        f"current={current_version}, expected={EXPECTED_SCHEMA_VERSION}"
                    )
                else:
                    logger.debug(
                        f"  ✅ Schema version correct: {db_path} v{current_version}"
                    )

                # Quick foreign key integrity check
                cursor.execute("PRAGMA foreign_key_check")
                violations = cursor.fetchall()
                if violations:
                    self.errors.append(
                        f"Foreign key violations in {db_path}: {len(violations)} violations"
                    )
                else:
                    logger.debug(f"  ✅ No FK violations: {db_path}")

                # Check critical tables exist
                critical_tables = ["episodes", "feeds"]
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = {row[0] for row in cursor.fetchall()}

                missing_tables = [
                    t for t in critical_tables if t not in existing_tables
                ]
                if missing_tables:
                    self.errors.append(
                        f"Critical tables missing in {db_path}: {missing_tables}"
                    )
                else:
                    logger.debug(f"  ✅ Critical tables exist: {db_path}")

        except Exception as e:
            self.errors.append(f"Database health check failed for {db_path}: {e}")

    def _check_required_directories(self) -> None:
        """Check that required directories exist"""

        required_dirs = ["transcripts", "daily_digests", "utils"]

        missing_dirs = []
        for dir_path in required_dirs:
            if not Path(dir_path).exists():
                missing_dirs.append(dir_path)

        if missing_dirs:
            self.errors.append(f"Required directories missing: {missing_dirs}")
        else:
            logger.debug(f"✅ All required directories exist: {required_dirs}")

    def _check_environment_variables(self) -> None:
        """Check critical environment variables"""

        import os

        # Critical environment variables
        critical_env_vars = []  # None are truly critical for basic operation

        # Important environment variables (warnings if missing)
        important_env_vars = ["GITHUB_TOKEN", "ELEVENLABS_API_KEY", "OPENAI_API_KEY"]

        missing_critical = []
        missing_important = []

        for var in critical_env_vars:
            if not os.getenv(var):
                missing_critical.append(var)

        for var in important_env_vars:
            if not os.getenv(var):
                missing_important.append(var)

        if missing_critical:
            self.errors.append(
                f"Critical environment variables missing: {missing_critical}"
            )

        if missing_important:
            self.warnings.append(
                f"Important environment variables missing: {missing_important}"
            )

        if not missing_critical and not missing_important:
            logger.debug("✅ All important environment variables are set")

    def get_health_summary(self) -> Dict:
        """Get a summary of system health"""

        return {
            "healthy": len(self.errors) == 0,
            "ready": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "databases_checked": self.databases,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


def validate_startup(
    databases: Optional[List[str]] = None, strict: bool = True
) -> bool:
    """
    Convenience function to run startup validation.

    Args:
        databases: List of database paths to check
        strict: If True, warnings are treated as failures

    Returns:
        True if system is ready, False otherwise
    """
    validator = StartupValidator(databases)
    return validator.run_all_checks(strict=strict)


def fail_fast_check(databases: Optional[List[str]] = None) -> None:
    """
    Run startup validation and exit with error code if validation fails.
    Designed for use at the beginning of main application entry points.

    Args:
        databases: List of database paths to check
    """
    if not validate_startup(databases, strict=False):
        logger.error("❌ System not ready - exiting")
        sys.exit(1)

    logger.info("✅ System ready - proceeding with application startup")


if __name__ == "__main__":
    # Command-line interface for startup checks

    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print("Usage: python utils/startup_checks.py [database_path...] [--strict]")
            print("       python utils/startup_checks.py --all [--strict]")
            print("")
            print("Options:")
            print("  --strict    Treat warnings as errors")
            print("  --all       Check default databases")
            print("  --help      Show this help")
            sys.exit(0)

        strict = "--strict" in sys.argv

        if "--all" in sys.argv:
            databases = None  # Use defaults
        else:
            databases = [arg for arg in sys.argv[1:] if not arg.startswith("--")]

        if validate_startup(databases, strict=strict):
            print("✅ All startup validation checks passed")
            sys.exit(0)
        else:
            print("❌ Startup validation failed")
            sys.exit(1)
    else:
        # Default: check all databases in non-strict mode
        if validate_startup(strict=False):
            print("✅ System ready")
            sys.exit(0)
        else:
            print("❌ System not ready")
            sys.exit(1)
