#!/usr/bin/env python3
"""
Database Connection Factory for Podcast Scraper
Centralized connection management with enforced foreign key integrity
"""

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Schema version tracking
EXPECTED_SCHEMA_VERSION = 2


class DatabaseConnectionFactory:
    """
    Centralized database connection management with enforced standards:
    - PRAGMA foreign_keys = ON (always enforced)
    - PRAGMA journal_mode = WAL (better concurrency)
    - PRAGMA synchronous = NORMAL (balance durability/performance)
    - Schema version validation
    - Connection pooling and error handling
    """

    _connections: Dict[str, sqlite3.Connection] = {}
    _lock = threading.Lock()

    @classmethod
    def get_connection(
        cls, db_path: str, readonly: bool = False, validate_schema: bool = True
    ) -> sqlite3.Connection:
        """
        Get a database connection with enforced standards.

        Args:
            db_path: Path to SQLite database file
            readonly: Whether this is a read-only connection
            validate_schema: Whether to validate schema version (default: True)

        Returns:
            Configured SQLite connection

        Raises:
            sqlite3.Error: Database connection or configuration failed
            AssertionError: Schema validation failed
        """

        # Normalize path
        db_path = str(Path(db_path).resolve())

        with cls._lock:
            # Create new connection (don't pool for now due to threading complexity)
            try:
                conn = sqlite3.connect(
                    db_path,
                    timeout=30,
                    check_same_thread=False,  # Allow cross-thread usage
                )

                # Configure connection with enforced standards
                cls._configure_connection(conn, readonly=readonly)

                # Validate schema version if requested
                if validate_schema:
                    cls._validate_schema_version(conn, db_path)

                logger.debug(
                    f"Database connection established: {db_path} (readonly={readonly})"
                )
                return conn

            except sqlite3.Error as e:
                logger.error(f"Failed to connect to database {db_path}: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error connecting to {db_path}: {e}")
                raise

    @classmethod
    def _configure_connection(
        cls, conn: sqlite3.Connection, readonly: bool = False
    ) -> None:
        """Configure connection with enforced standards"""

        # CRITICAL: Always enable foreign key enforcement
        conn.execute("PRAGMA foreign_keys = ON")

        # Performance and durability settings
        conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
        conn.execute("PRAGMA synchronous = NORMAL")  # Balance durability/performance
        conn.execute("PRAGMA busy_timeout = 30000")  # 30 seconds for concurrent access

        # Additional performance settings
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        conn.execute("PRAGMA temp_store = MEMORY")  # Use memory for temp tables

        if readonly:
            conn.execute(
                "PRAGMA query_only = ON"
            )  # Prevent writes on readonly connections

        # Verify foreign keys are actually enabled
        fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        if fk_status != 1:
            raise sqlite3.Error(
                f"Failed to enable foreign key enforcement (status: {fk_status})"
            )

    @classmethod
    def _validate_schema_version(cls, conn: sqlite3.Connection, db_path: str) -> None:
        """
        Validate that database schema version matches expected.
        Fail fast if schema is outdated or incompatible.
        """
        try:
            current_version = conn.execute("PRAGMA user_version").fetchone()[0]

            if current_version == 0:
                # New database or pre-versioned schema - this is expected during migration
                logger.info(
                    f"Database {db_path} has no schema version (user_version=0), skipping validation"
                )
                return

            if current_version != EXPECTED_SCHEMA_VERSION:
                raise AssertionError(
                    f"Schema version mismatch in {db_path}: "
                    f"expected {EXPECTED_SCHEMA_VERSION}, got {current_version}. "
                    f"Run migration script to update schema."
                )

            logger.debug(f"Schema version validated: {current_version} for {db_path}")

        except sqlite3.Error as e:
            logger.error(f"Failed to check schema version for {db_path}: {e}")
            raise


@contextmanager
def get_db_connection(
    db_path: str, readonly: bool = False, validate_schema: bool = True
):
    """
    Context manager for database connections with automatic cleanup.

    Usage:
        with get_db_connection('podcast_monitor.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM episodes LIMIT 1")
            result = cursor.fetchone()
    """
    conn = None
    try:
        conn = DatabaseConnectionFactory.get_connection(
            db_path, readonly=readonly, validate_schema=validate_schema
        )
        yield conn
    except Exception:
        if conn:
            conn.rollback()  # Rollback any pending transaction
        raise
    finally:
        if conn:
            conn.close()


# Convenience functions for common patterns
def get_connection(
    db_path: str, readonly: bool = False, validate_schema: bool = True
) -> sqlite3.Connection:
    """
    Convenience function to get a database connection.

    IMPORTANT: Caller is responsible for closing the connection.
    Consider using get_db_connection() context manager instead.
    """
    return DatabaseConnectionFactory.get_connection(
        db_path, readonly=readonly, validate_schema=validate_schema
    )


def execute_query(
    db_path: str, query: str, params: tuple = (), readonly: bool = False
) -> list:
    """
    Execute a single query and return results.
    Handles connection management automatically.
    """
    with get_db_connection(db_path, readonly=readonly) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)

        if readonly or query.strip().upper().startswith("SELECT"):
            return cursor.fetchall()
        else:
            conn.commit()
            return cursor.fetchall()


def check_foreign_key_violations(db_path: str) -> list:
    """
    Check for foreign key violations in database.
    Returns list of violations (empty if all good).
    """
    with get_db_connection(db_path, readonly=True) as conn:
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        return violations


# Legacy compatibility - will be removed after migration
def sqlite3_connect_deprecated(db_path: str, **kwargs):
    """
    DEPRECATED: Use get_connection() instead.
    This function exists only for migration compatibility.
    """
    logger.warning(
        f"DEPRECATED: sqlite3_connect_deprecated() called from {db_path}. Use get_connection() instead."
    )
    return get_connection(db_path, **kwargs)


if __name__ == "__main__":
    # Test the connection factory
    import sys

    if len(sys.argv) > 1:
        db_path = sys.argv[1]

        print(f"Testing database connection: {db_path}")

        try:
            # Test connection
            with get_db_connection(db_path, validate_schema=False) as conn:
                # Check foreign key enforcement
                fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                print(f"✅ Foreign keys enabled: {fk_status == 1}")

                # Check schema version
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                print(f"Schema version: {version}")

                # Check for violations
                violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    print(f"❌ Foreign key violations found: {len(violations)}")
                    for violation in violations[:5]:  # Show first 5
                        print(f"  {violation}")
                else:
                    print("✅ No foreign key violations")

                print("Connection test successful!")

        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            sys.exit(1)
    else:
        print("Usage: python utils/db.py <database_path>")
        sys.exit(1)
