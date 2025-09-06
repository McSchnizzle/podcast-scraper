#!/usr/bin/env python3
"""
Database Timestamp Migration Script
Normalizes legacy timestamp columns to UTC-aware ISO8601 format
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.datetime_utils import now_utc, parse_entry_to_utc, to_utc
from utils.db import get_connection


def migrate_database(db_path: str, dry_run: bool = False) -> dict:
    """
    Migrate all timestamp columns in a database to UTC-aware format

    Args:
        db_path: Path to SQLite database
        dry_run: If True, don't make changes, just report what would be done

    Returns:
        dict: Migration summary
    """
    if not os.path.exists(db_path):
        return {"error": f"Database not found: {db_path}"}

    migration_summary = {
        "database": db_path,
        "dry_run": dry_run,
        "timestamp": now_utc().isoformat(),
        "tables_processed": [],
        "total_rows_updated": 0,
        "errors": [],
    }

    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        for (table_name,) in tables:
            table_summary = migrate_table_timestamps(cursor, table_name, dry_run)
            migration_summary["tables_processed"].append(table_summary)
            migration_summary["total_rows_updated"] += table_summary["rows_updated"]

        if not dry_run:
            conn.commit()

        conn.close()

    except Exception as e:
        migration_summary["errors"].append(f"Database error: {e}")

    return migration_summary


def migrate_table_timestamps(cursor, table_name: str, dry_run: bool = False) -> dict:
    """
    Migrate timestamp columns in a specific table

    Args:
        cursor: Database cursor
        table_name: Name of table to process
        dry_run: If True, don't make changes

    Returns:
        dict: Table migration summary
    """
    table_summary = {
        "table": table_name,
        "columns_processed": [],
        "rows_updated": 0,
        "errors": [],
    }

    try:
        # Get table schema to identify timestamp columns
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()

        timestamp_columns = []
        for col_info in columns:
            col_name = col_info[1].lower()
            col_type = col_info[2].lower()

            # Identify timestamp columns by name patterns
            if any(
                pattern in col_name
                for pattern in ["published", "created", "updated", "timestamp", "date"]
            ):
                if col_type in ["text", "datetime", "timestamp"]:
                    timestamp_columns.append(col_info[1])  # Use original case

        if not timestamp_columns:
            return table_summary

        # Process each timestamp column
        for col_name in timestamp_columns:
            col_summary = migrate_column_timestamps(
                cursor, table_name, col_name, dry_run
            )
            table_summary["columns_processed"].append(col_summary)
            table_summary["rows_updated"] += col_summary["rows_updated"]

            if col_summary["errors"]:
                table_summary["errors"].extend(col_summary["errors"])

    except Exception as e:
        table_summary["errors"].append(f"Table {table_name} error: {e}")

    return table_summary


def migrate_column_timestamps(
    cursor, table_name: str, col_name: str, dry_run: bool = False
) -> dict:
    """
    Migrate a specific timestamp column to UTC format

    Args:
        cursor: Database cursor
        table_name: Name of table
        col_name: Name of timestamp column
        dry_run: If True, don't make changes

    Returns:
        dict: Column migration summary
    """
    col_summary = {
        "column": col_name,
        "rows_examined": 0,
        "rows_updated": 0,
        "conversion_types": {},
        "errors": [],
    }

    try:
        # Get all rows with non-null timestamp values
        cursor.execute(
            f"SELECT rowid, {col_name} FROM {table_name} WHERE {col_name} IS NOT NULL AND {col_name} != ''"
        )
        rows = cursor.fetchall()

        col_summary["rows_examined"] = len(rows)

        for rowid, timestamp_str in rows:
            try:
                # Parse and normalize the timestamp
                normalized_timestamp, conversion_type = normalize_timestamp(
                    timestamp_str
                )

                if normalized_timestamp and normalized_timestamp != timestamp_str:
                    # Track conversion types
                    col_summary["conversion_types"][conversion_type] = (
                        col_summary["conversion_types"].get(conversion_type, 0) + 1
                    )

                    if not dry_run:
                        # Update the row
                        cursor.execute(
                            f"UPDATE {table_name} SET {col_name} = ? WHERE rowid = ?",
                            (normalized_timestamp, rowid),
                        )

                    col_summary["rows_updated"] += 1

            except Exception as e:
                col_summary["errors"].append(f"Row {rowid}: {e}")
                continue

    except Exception as e:
        col_summary["errors"].append(f"Column {col_name} error: {e}")

    return col_summary


def normalize_timestamp(timestamp_str: str) -> tuple:
    """
    Normalize a timestamp string to UTC ISO8601 format

    Args:
        timestamp_str: Original timestamp string

    Returns:
        tuple: (normalized_timestamp, conversion_type)
    """
    if not timestamp_str or timestamp_str.strip() == "":
        return None, "empty"

    timestamp_str = timestamp_str.strip()

    # Already ISO8601 UTC format
    if timestamp_str.endswith("+00:00") or timestamp_str.endswith("Z"):
        return timestamp_str, "already_utc"

    try:
        # Try to parse as ISO format (naive, assume UTC)
        if "T" in timestamp_str and len(timestamp_str) >= 19:
            try:
                dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                normalized = to_utc(dt).isoformat().replace("+00:00", "Z")
                return normalized, "iso_naive_to_utc"
            except:
                pass

        # Try to parse as datetime string
        try:
            # Common formats
            for fmt in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%a, %d %b %Y %H:%M:%S %Z",  # RFC2822
                "%a, %d %b %Y %H:%M:%S GMT",
            ]:
                try:
                    dt = datetime.strptime(timestamp_str, fmt)
                    # Assume naive datetime is UTC
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    normalized = to_utc(dt).isoformat().replace("+00:00", "Z")
                    return normalized, f"parsed_{fmt}"
                except:
                    continue
        except:
            pass

        # If we can't parse it, leave it unchanged
        return timestamp_str, "unparseable"

    except Exception as e:
        return timestamp_str, f"error_{type(e).__name__}"


def main():
    """CLI interface for the migration script"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate database timestamps to UTC format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for migration report (JSON)",
    )
    parser.add_argument(
        "--databases",
        nargs="*",
        default=["podcast_monitor.db", "youtube_transcripts.db"],
        help="Databases to migrate",
    )

    args = parser.parse_args()

    all_results = []

    for db_path in args.databases:
        if not os.path.exists(db_path):
            print(f"⚠️ Database not found: {db_path}")
            continue

        print(f"{'🔍 Analyzing' if args.dry_run else '🔄 Migrating'} {db_path}...")
        result = migrate_database(db_path, dry_run=args.dry_run)
        all_results.append(result)

        # Print summary
        if result.get("errors"):
            print(f"❌ Errors in {db_path}:")
            for error in result["errors"]:
                print(f"   {error}")

        print(
            f"✅ {db_path}: {result['total_rows_updated']} rows {'would be updated' if args.dry_run else 'updated'}"
        )

        for table in result["tables_processed"]:
            if table["rows_updated"] > 0:
                print(f"   📋 {table['table']}: {table['rows_updated']} rows")
                for col in table["columns_processed"]:
                    if col["rows_updated"] > 0:
                        conversions = ", ".join(
                            [f"{k}:{v}" for k, v in col["conversion_types"].items()]
                        )
                        print(f"      📅 {col['column']}: {conversions}")

    # Save detailed report if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"📄 Detailed report saved to {args.output}")

    total_updated = sum(r["total_rows_updated"] for r in all_results)
    print(
        f"\n🎯 Migration {'simulation' if args.dry_run else 'complete'}: {total_updated} total rows {'would be updated' if args.dry_run else 'updated'}"
    )


if __name__ == "__main__":
    main()
