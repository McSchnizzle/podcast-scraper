#!/usr/bin/env python3
"""
Schema Integrity Verification Script

Comprehensive validation of database schema integrity for Phase 4+.
- Validates foreign key enforcement and integrity
- Checks schema version
- Verifies required indexes and unique constraints
- Detects orphaned records
- Tests Phase 4 functionality
"""

import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.datetime_utils import now_utc
from utils.db import get_connection

# Add utils to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Expected configuration
EXPECTED_SCHEMA_VERSION = 2
REQUIRED_TABLES = ["episodes", "feeds", "feed_metadata", "item_seen"]
OPTIONAL_TABLES = ["episode_failures"]

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SchemaIntegrityVerifier:
    """
    Comprehensive schema integrity verification for podcast scraper databases.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.results = {
            "database": str(self.db_path),
            "timestamp": now_utc().isoformat(),
            "checks": {},
            "overall_status": "unknown",
            "errors": [],
            "warnings": [],
        }

    def verify_all(self, strict: bool = True) -> bool:
        """
        Run all verification checks.

        Args:
            strict: If True, warnings count as failures

        Returns:
            True if all checks pass, False otherwise
        """

        logger.info(f"=== Schema Integrity Verification ===")
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Strict mode: {strict}")

        if not self.db_path.exists():
            self._add_error(f"Database file not found: {self.db_path}")
            return False

        try:
            with get_connection(self.db_path) as conn:
                # Enable foreign keys for testing
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.cursor()

                # Run all verification checks
                self._check_foreign_key_enforcement(cursor)
                self._check_foreign_key_integrity(cursor)
                self._check_schema_version(cursor)
                self._check_required_tables(cursor)
                self._check_required_indexes(cursor)
                self._check_unique_constraints(cursor)
                self._check_orphaned_records(cursor)
                self._check_data_integrity(cursor)

                # Determine overall status
                has_errors = len(self.results["errors"]) > 0
                has_warnings = len(self.results["warnings"]) > 0

                if has_errors:
                    self.results["overall_status"] = "failed"
                elif strict and has_warnings:
                    self.results["overall_status"] = "failed"
                elif has_warnings:
                    self.results["overall_status"] = "warning"
                else:
                    self.results["overall_status"] = "passed"

                # Log summary
                self._log_summary()

                return (
                    self.results["overall_status"] in ["passed", "warning"]
                    if not strict
                    else self.results["overall_status"] == "passed"
                )

        except sqlite3.Error as e:
            self._add_error(f"Database connection/query error: {e}")
            return False
        except Exception as e:
            self._add_error(f"Unexpected error during verification: {e}")
            return False

    def _check_foreign_key_enforcement(self, cursor: sqlite3.Cursor) -> None:
        """Verify that foreign key enforcement is enabled"""

        cursor.execute("PRAGMA foreign_keys")
        fk_status = cursor.fetchone()[0]

        self.results["checks"]["foreign_key_enforcement"] = {
            "status": "passed" if fk_status == 1 else "failed",
            "value": fk_status,
            "expected": 1,
            "description": "Foreign key enforcement must be enabled",
        }

        if fk_status != 1:
            self._add_error(
                "Foreign key enforcement is not enabled (PRAGMA foreign_keys != 1)"
            )
        else:
            logger.info("✅ Foreign key enforcement is enabled")

    def _check_foreign_key_integrity(self, cursor: sqlite3.Cursor) -> None:
        """Check for foreign key violations"""

        cursor.execute("PRAGMA foreign_key_check")
        violations = cursor.fetchall()

        self.results["checks"]["foreign_key_integrity"] = {
            "status": "passed" if not violations else "failed",
            "violations": violations,
            "description": "No foreign key violations should exist",
        }

        if violations:
            self._add_error(
                f"Foreign key violations found: {len(violations)} violations"
            )
            for violation in violations[:5]:  # Show first 5
                logger.error(f"  FK violation: {violation}")
        else:
            logger.info("✅ No foreign key violations found")

    def _check_schema_version(self, cursor: sqlite3.Cursor) -> None:
        """Verify schema version matches expected"""

        cursor.execute("PRAGMA user_version")
        current_version = cursor.fetchone()[0]

        self.results["checks"]["schema_version"] = {
            "status": (
                "passed" if current_version == EXPECTED_SCHEMA_VERSION else "failed"
            ),
            "current": current_version,
            "expected": EXPECTED_SCHEMA_VERSION,
            "description": f"Schema version should be {EXPECTED_SCHEMA_VERSION}",
        }

        if current_version != EXPECTED_SCHEMA_VERSION:
            if current_version == 0:
                self._add_warning(
                    f"Schema version not set (user_version=0). Expected: {EXPECTED_SCHEMA_VERSION}"
                )
            else:
                self._add_error(
                    f"Schema version mismatch: {current_version}, expected: {EXPECTED_SCHEMA_VERSION}"
                )
        else:
            logger.info(f"✅ Schema version correct: {current_version}")

    def _check_required_tables(self, cursor: sqlite3.Cursor) -> None:
        """Verify required tables exist"""

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        missing_required = [t for t in REQUIRED_TABLES if t not in existing_tables]
        missing_optional = [t for t in OPTIONAL_TABLES if t not in existing_tables]

        self.results["checks"]["required_tables"] = {
            "status": "passed" if not missing_required else "failed",
            "existing_tables": list(existing_tables),
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "description": "All required tables must exist",
        }

        if missing_required:
            self._add_error(f"Missing required tables: {missing_required}")
        else:
            logger.info(f"✅ All required tables exist ({len(REQUIRED_TABLES)} tables)")

        if missing_optional:
            logger.info(f"Optional tables missing: {missing_optional}")

    def _check_required_indexes(self, cursor: sqlite3.Cursor) -> None:
        """Verify required indexes exist"""

        # Get all indexes
        cursor.execute(
            "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        )
        existing_indexes = {
            row[0]: {"table": row[1], "sql": row[2]} for row in cursor.fetchall()
        }

        # Define required indexes
        required_indexes = [
            ("idx_episodes_feed_id", "episodes"),
            ("idx_episode_failures_episode_pk", "episode_failures"),
            ("idx_feed_metadata_feed_id", "feed_metadata"),
            ("idx_item_seen_feed_id", "item_seen"),
            ("idx_item_seen_first_seen", "item_seen"),
        ]

        missing_indexes = []

        for index_name, table_name in required_indexes:
            # Check if table exists first
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            if not cursor.fetchone():
                continue  # Skip if table doesn't exist

            if index_name not in existing_indexes:
                missing_indexes.append((index_name, table_name))

        self.results["checks"]["required_indexes"] = {
            "status": "passed" if not missing_indexes else "failed",
            "existing_indexes": list(existing_indexes.keys()),
            "missing_indexes": missing_indexes,
            "description": "Required indexes must exist for performance",
        }

        if missing_indexes:
            self._add_error(
                f"Missing required indexes: {[idx[0] for idx in missing_indexes]}"
            )
        else:
            logger.info(
                f"✅ All required indexes exist ({len(existing_indexes)} indexes)"
            )

    def _check_unique_constraints(self, cursor: sqlite3.Cursor) -> None:
        """Verify unique constraints exist"""

        # Check for unique indexes (SQLite's way of implementing unique constraints)
        cursor.execute(
            """
            SELECT name, tbl_name, sql
            FROM sqlite_master
            WHERE type='index' AND sql LIKE '%UNIQUE%'
        """
        )
        unique_constraints = {
            row[0]: {"table": row[1], "sql": row[2]} for row in cursor.fetchall()
        }

        # Required unique constraints
        required_uniques = [
            "ux_episodes_episode_id",  # Temporary during migration
            "ux_item_seen_feed_hash",  # For deduplication
        ]

        missing_uniques = []
        for unique_name in required_uniques:
            if unique_name not in unique_constraints:
                # Check if the table exists first
                table_name = unique_name.split("_")[1] if "_" in unique_name else None
                if table_name:
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table_name,),
                    )
                    if cursor.fetchone():
                        missing_uniques.append(unique_name)

        self.results["checks"]["unique_constraints"] = {
            "status": "warning" if missing_uniques else "passed",  # Warnings for now
            "existing_unique_constraints": list(unique_constraints.keys()),
            "missing_unique_constraints": missing_uniques,
            "description": "Unique constraints should exist for data integrity",
        }

        if missing_uniques:
            self._add_warning(f"Missing unique constraints: {missing_uniques}")
        else:
            logger.info(
                f"✅ Unique constraints in place ({len(unique_constraints)} constraints)"
            )

    def _check_orphaned_records(self, cursor: sqlite3.Cursor) -> None:
        """Check for orphaned records"""

        orphan_queries = [
            (
                "orphaned_episodes",
                "SELECT COUNT(*) FROM episodes e WHERE e.feed_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM feeds f WHERE f.id = e.feed_id)",
            ),
            (
                "orphaned_episode_failures",
                "SELECT COUNT(*) FROM episode_failures ef WHERE NOT EXISTS (SELECT 1 FROM episodes e WHERE e.id = ef.episode_pk)",
            ),
            (
                "orphaned_item_seen",
                "SELECT COUNT(*) FROM item_seen s WHERE NOT EXISTS (SELECT 1 FROM feeds f WHERE f.id = s.feed_id)",
            ),
            (
                "orphaned_feed_metadata",
                "SELECT COUNT(*) FROM feed_metadata fm WHERE NOT EXISTS (SELECT 1 FROM feeds f WHERE f.id = fm.feed_id)",
            ),
        ]

        orphan_counts = {}
        total_orphans = 0

        for check_name, query in orphan_queries:
            try:
                cursor.execute(query)
                count = cursor.fetchone()[0]
                orphan_counts[check_name] = count
                total_orphans += count
            except sqlite3.Error as e:
                # Table might not exist, which is OK
                orphan_counts[check_name] = 0
                logger.debug(f"Orphan check {check_name} skipped: {e}")

        self.results["checks"]["orphaned_records"] = {
            "status": "passed" if total_orphans == 0 else "failed",
            "orphan_counts": orphan_counts,
            "total_orphans": total_orphans,
            "description": "No orphaned records should exist",
        }

        if total_orphans > 0:
            self._add_error(f"Orphaned records found: {total_orphans} total")
            for check, count in orphan_counts.items():
                if count > 0:
                    logger.error(f"  {check}: {count} orphaned records")
        else:
            logger.info("✅ No orphaned records found")

    def _check_data_integrity(self, cursor: sqlite3.Cursor) -> None:
        """Additional data integrity checks"""

        integrity_issues = []

        # Check for NULL primary keys (shouldn't happen but let's be sure)
        cursor.execute("SELECT COUNT(*) FROM episodes WHERE id IS NULL")
        null_pks = cursor.fetchone()[0]
        if null_pks > 0:
            integrity_issues.append(f"Episodes with NULL primary key: {null_pks}")

        # Check for NULL episode_id values (needed for backward compatibility)
        cursor.execute(
            "SELECT COUNT(*) FROM episodes WHERE episode_id IS NULL OR episode_id = ''"
        )
        null_episode_ids = cursor.fetchone()[0]
        if null_episode_ids > 0:
            integrity_issues.append(
                f"Episodes with NULL/empty episode_id: {null_episode_ids}"
            )

        # Check for duplicate episode_id values
        cursor.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT episode_id, COUNT(*)
                FROM episodes
                WHERE episode_id IS NOT NULL
                GROUP BY episode_id
                HAVING COUNT(*) > 1
            )
        """
        )
        duplicate_episode_ids = cursor.fetchone()[0]
        if duplicate_episode_ids > 0:
            integrity_issues.append(
                f"Duplicate episode_id values: {duplicate_episode_ids}"
            )

        self.results["checks"]["data_integrity"] = {
            "status": "passed" if not integrity_issues else "failed",
            "issues": integrity_issues,
            "description": "Data should meet basic integrity requirements",
        }

        if integrity_issues:
            for issue in integrity_issues:
                self._add_error(f"Data integrity issue: {issue}")
        else:
            logger.info("✅ Data integrity checks passed")

    def _add_error(self, message: str) -> None:
        """Add an error to the results"""
        self.results["errors"].append(message)
        logger.error(message)

    def _add_warning(self, message: str) -> None:
        """Add a warning to the results"""
        self.results["warnings"].append(message)
        logger.warning(message)

    def _log_summary(self) -> None:
        """Log verification summary"""

        logger.info(f"\n{'='*60}")
        logger.info("SCHEMA INTEGRITY VERIFICATION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Overall Status: {self.results['overall_status'].upper()}")
        logger.info(f"Errors: {len(self.results['errors'])}")
        logger.info(f"Warnings: {len(self.results['warnings'])}")

        # Check breakdown
        logger.info(f"\nCheck Results:")
        for check_name, check_result in self.results["checks"].items():
            status_icon = (
                "✅"
                if check_result["status"] == "passed"
                else "⚠️" if check_result["status"] == "warning" else "❌"
            )
            logger.info(f"  {status_icon} {check_name}: {check_result['status']}")

        # Show errors and warnings
        if self.results["errors"]:
            logger.info(f"\nErrors:")
            for error in self.results["errors"]:
                logger.info(f"  ❌ {error}")

        if self.results["warnings"]:
            logger.info(f"\nWarnings:")
            for warning in self.results["warnings"]:
                logger.info(f"  ⚠️ {warning}")

        logger.info(f"{'='*60}")

    def save_results(self, output_path: Optional[str] = None) -> str:
        """Save verification results to JSON file"""

        if output_path is None:
            timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
            output_path = (
                f"schema_integrity_report_{self.db_path.stem}_{timestamp}.json"
            )

        with open(output_path, "w") as f:
            json.dump(self.results, f, indent=2, sort_keys=True)

        logger.info(f"Verification report saved: {output_path}")
        return output_path


def main():
    """Main entry point"""

    if len(sys.argv) < 2:
        print(
            "Usage: python verify_schema_integrity.py <database_path> [--strict] [--output report.json]"
        )
        print(
            "       python verify_schema_integrity.py --all [--strict] [--output-dir reports/]"
        )
        sys.exit(1)

    strict_mode = "--strict" in sys.argv

    # Parse output options
    output_path = None
    output_dir = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    if "--output-dir" in sys.argv:
        idx = sys.argv.index("--output-dir")
        if idx + 1 < len(sys.argv):
            output_dir = Path(sys.argv[idx + 1])
            output_dir.mkdir(exist_ok=True)

    if "--all" in sys.argv:
        # Verify all databases
        databases = ["podcast_monitor.db", "youtube_transcripts.db"]
    else:
        databases = [sys.argv[1]]

    success_count = 0
    reports = []

    for db_path in databases:
        if not Path(db_path).exists():
            logger.warning(f"Database not found: {db_path}, skipping")
            continue

        logger.info(f"\n{'='*80}")
        verifier = SchemaIntegrityVerifier(db_path)

        if verifier.verify_all(strict=strict_mode):
            success_count += 1

        # Save report
        if output_dir:
            report_path = (
                output_dir
                / f"schema_integrity_report_{Path(db_path).stem}_{now_utc().strftime('%Y%m%d_%H%M%S')}.json"
            )
            verifier.save_results(str(report_path))
        elif output_path:
            verifier.save_results(output_path)
        else:
            report_path = verifier.save_results()

        reports.append(report_path)

    # Final summary
    logger.info(f"\n{'='*80}")
    logger.info("FINAL VERIFICATION SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Databases processed: {len(databases)}")
    logger.info(f"Successful verifications: {success_count}")
    logger.info(f"Failed verifications: {len(databases) - success_count}")

    if success_count == len(databases):
        logger.info("🎉 All schema integrity checks passed!")
        sys.exit(0)
    else:
        logger.error("❌ Some schema integrity checks failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
