#!/usr/bin/env python3
import argparse
import os
import shutil
import sqlite3
from datetime import datetime

from utils.datetime_utils import now_utc
from utils.db import get_connection


def backup_db(path):
    ts = now_utc().strftime("%Y%m%d-%H%M%S")
    dst = f"{path}.backup.{ts}.db"
    shutil.copy2(path, dst)
    print(f"[backup] {path} -> {dst}")
    return dst


def exec_sql(db_path, sql, params=()):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if isinstance(sql, (list, tuple)):
            for s in sql:
                cur.execute(s)
        else:
            cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def query(db_path, sql):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        return rows
    finally:
        conn.close()


def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def write_dummy(path, content="This is a dummy transcript for testing."):
    ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    p = argparse.ArgumentParser(
        description="Prep podcast DBs for multi-topic digest test (2 YouTube, 1 RSS)."
    )
    p.add_argument("--youtube-db", required=True, help="Path to youtube_transcripts.db")
    p.add_argument("--rss-db", required=True, help="Path to podcast_monitor.db")
    p.add_argument(
        "--youtube-ids",
        required=True,
        help="Comma-separated two YouTube episode IDs to keep, e.g. Y1,Y2",
    )
    p.add_argument(
        "--rss-id", required=True, help="Single RSS episode ID to keep, e.g. R1"
    )
    p.add_argument(
        "--transcripts-dir",
        default="transcripts",
        help="Directory for transcript files (default: transcripts)",
    )
    p.add_argument(
        "--dummy-transcripts",
        action="store_true",
        help="Create dummy transcript files for the YouTube episodes",
    )
    p.add_argument(
        "--mode",
        choices=["archive", "delete"],
        default="archive",
        help="Archive (status='archived') or delete other episodes (default: archive)",
    )
    p.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup of DBs before modifying (not recommended)",
    )
    args = p.parse_args()

    yids = [x.strip() for x in args.youtube_ids.split(",") if x.strip()]
    if len(yids) != 2:
        raise SystemExit(
            "Please provide exactly TWO YouTube IDs via --youtube-ids (e.g., --youtube-ids Y1,Y2)"
        )
    rid = args.rss_id.strip()
    if not rid:
        raise SystemExit("Please provide ONE RSS ID via --rss-id")

    # Backups
    if not args.no_backup:
        backup_db(args.youtube_db)
        backup_db(args.rss_db)
    else:
        print("[warn] --no-backup used; proceeding without backups.")

    # Clear digest stamps in both DBs
    for db in (args.youtube_db, args.rss_db):
        exec_sql(db, ["UPDATE episodes SET digest_topic=NULL, digest_date=NULL;"])
        print(f"[stamp] Cleared digest_topic/digest_date in {db}")

    # Prune YouTube DB to two IDs
    if args.mode == "archive":
        exec_sql(
            args.youtube_db,
            f"""
            UPDATE episodes SET status='archived' WHERE id NOT IN ('{yids[0]}','{yids[1]}');
        """,
        )
        print(f"[prune] Archived all YouTube episodes except {yids}")
    else:
        exec_sql(
            args.youtube_db,
            f"""
            DELETE FROM episodes WHERE id NOT IN ('{yids[0]}','{yids[1]}');
        """,
        )
        print(f"[prune] Deleted all YouTube episodes except {yids}")

    # Set the two YouTube IDs to transcribed status + transcript_path
    y_paths = []
    for i, yid in enumerate(yids, start=1):
        tpath = os.path.join(args.transcripts_dir, f"{yid}.txt")
        y_paths.append(tpath)
        exec_sql(
            args.youtube_db,
            """
            UPDATE episodes SET status='transcribed', transcript_path=? WHERE id=?;
        """,
            params=(tpath, yid),
        )
        print(f"[state] YouTube {yid} -> transcribed, transcript_path={tpath}")
        if args.dummy_transcripts:
            write_dummy(
                tpath,
                content=f"Dummy transcript for {yid}. This is a short snippet for testing the digest pipeline.",
            )

    # Prune RSS DB to one ID
    if args.mode == "archive":
        exec_sql(
            args.rss_db,
            f"""
            UPDATE episodes SET status='archived' WHERE id != '{rid}';
        """,
        )
        print(f"[prune] Archived all RSS episodes except {rid}")
    else:
        exec_sql(
            args.rss_db,
            f"""
            DELETE FROM episodes WHERE id != '{rid}';
        """,
        )
        print(f"[prune] Deleted all RSS episodes except {rid}")

    # Set the RSS ID to downloaded (to trigger fresh transcription)
    exec_sql(
        args.rss_db,
        """
        UPDATE episodes SET status='downloaded', transcript_path=NULL WHERE id=?;
    """,
        params=(rid,),
    )
    print(f"[state] RSS {rid} -> downloaded (will be transcribed during run)")

    # Show a compact summary
    y_rows = query(
        args.youtube_db,
        "SELECT id, status, transcript_path, digest_topic, digest_date FROM episodes ORDER BY id;",
    )
    r_rows = query(
        args.rss_db,
        "SELECT id, status, transcript_path, digest_topic, digest_date FROM episodes ORDER BY id;",
    )

    print("\n=== YouTube episodes (post-prep) ===")
    for row in y_rows:
        print(row)
    print("\n=== RSS episodes (post-prep) ===")
    for row in r_rows:
        print(row)

    print("\n[done] Databases prepared. Next: run the pipeline and verify outputs.\n")


if __name__ == "__main__":
    main()
