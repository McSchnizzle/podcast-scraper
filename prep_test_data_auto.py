#!/usr/bin/env python3
import argparse
import os
import shutil
import sqlite3
from datetime import datetime

from utils.datetime_utils import now_utc
from utils.db import get_connection

DATE_CANDIDATES = [
    "published_date",
    "pub_date",
    "created_at",
    "added_at",
    "date",
    "ingested_at",
]


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


def query(db_path, sql, params=()):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        return rows
    finally:
        conn.close()


def get_episode_columns(db_path):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(episodes)")
        rows = cur.fetchall()
        cols = {r[1] for r in rows}  # 0:cid,1:name,2:type,...
    finally:
        conn.close()
    return cols


def pick_date_column(db_path):
    cols = get_episode_columns(db_path)
    for c in DATE_CANDIDATES:
        if c in cols:
            return c
    # fallback to rowid sort if no date column found
    return None


def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def write_dummy(path, content="This is a dummy transcript for testing."):
    ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def newest_episode_ids(db_path, k=2):
    # Return newest K by best-effort date column, else by rowid desc
    date_col = pick_date_column(db_path)
    if date_col:
        sql = f"SELECT id FROM episodes ORDER BY {date_col} DESC LIMIT {k}"
    else:
        sql = "SELECT id FROM episodes ORDER BY rowid DESC LIMIT ?"
    rows = query(db_path, sql, (k,) if "?" in sql else ())
    return [r[0] for r in rows]


def prep_databases(youtube_db, rss_db, transcripts_dir, mode, make_dummy, no_backup):
    if not os.path.exists(youtube_db):
        raise SystemExit(f"Missing db: {youtube_db}")
    if not os.path.exists(rss_db):
        raise SystemExit(f"Missing db: {rss_db}")

    if not no_backup:
        backup_db(youtube_db)
        backup_db(rss_db)
    else:
        print("[warn] --no-backup used; proceeding without backups.")

    # Clear digest stamps in both DBs
    for db in (youtube_db, rss_db):
        exec_sql(db, "UPDATE episodes SET digest_topic=NULL, digest_date=NULL;")
        print(f"[stamp] Cleared digest_topic/digest_date in {db}")

    # Auto-pick YT 2 newest and RSS 1 newest
    y_ids = newest_episode_ids(youtube_db, k=2)
    if len(y_ids) < 2:
        raise SystemExit(f"Could not find two episodes in {youtube_db}. Found: {y_ids}")
    r_ids = newest_episode_ids(rss_db, k=1)
    if len(r_ids) < 1:
        raise SystemExit(f"Could not find one episode in {rss_db}. Found: {r_ids}")
    y1, y2 = y_ids[0], y_ids[1]
    rid = r_ids[0]

    print(f"[select] YouTube keep: {y1}, {y2}")
    print(f"[select] RSS keep: {rid}")

    # Prune YT
    if mode == "archive":
        exec_sql(
            youtube_db,
            f"UPDATE episodes SET status='archived' WHERE id NOT IN ('{y1}','{y2}');",
        )
        print(f"[prune] Archived all YouTube episodes except {y1}, {y2}")
    else:
        exec_sql(youtube_db, f"DELETE FROM episodes WHERE id NOT IN ('{y1}','{y2}');")
        print(f"[prune] Deleted all YouTube episodes except {y1}, {y2}")

    # Set YT to transcribed + transcript_path
    for yid in (y1, y2):
        tpath = os.path.join(transcripts_dir, f"{yid}.txt")
        exec_sql(
            youtube_db,
            "UPDATE episodes SET status='transcribed', transcript_path=? WHERE id=?;",
            (tpath, yid),
        )
        print(f"[state] YouTube {yid} -> transcribed, transcript_path={tpath}")
        if make_dummy:
            write_dummy(
                tpath,
                content=f"Dummy transcript for {yid}. Short snippet for testing the digest pipeline.",
            )

    # Prune RSS
    if mode == "archive":
        exec_sql(rss_db, f"UPDATE episodes SET status='archived' WHERE id != '{rid}';")
        print(f"[prune] Archived all RSS episodes except {rid}")
    else:
        exec_sql(rss_db, f"DELETE FROM episodes WHERE id != '{rid}';")
        print(f"[prune] Deleted all RSS episodes except {rid}")

    # Set RSS to downloaded for fresh transcription
    exec_sql(
        rss_db,
        "UPDATE episodes SET status='downloaded', transcript_path=NULL WHERE id=?;",
        (rid,),
    )
    print(f"[state] RSS {rid} -> downloaded (will be transcribed during run)")

    # Summaries
    y_rows = query(
        youtube_db,
        "SELECT id, status, transcript_path, digest_topic, digest_date FROM episodes ORDER BY id;",
    )
    r_rows = query(
        rss_db,
        "SELECT id, status, transcript_path, digest_topic, digest_date FROM episodes ORDER BY id;",
    )

    print("\n=== YouTube episodes (post-prep) ===")
    for row in y_rows:
        print(row)
    print("\n=== RSS episodes (post-prep) ===")
    for row in r_rows:
        print(row)

    print("\n[done] Databases prepared. Next: run the pipeline and verify outputs.\n")


def main():
    ap = argparse.ArgumentParser(
        description="Auto-prep DBs for testing: newest 2 YouTube + newest 1 RSS"
    )
    ap.add_argument(
        "--youtube-db",
        default="youtube_transcripts.db",
        help="Path to youtube_transcripts.db",
    )
    ap.add_argument(
        "--rss-db", default="podcast_monitor.db", help="Path to podcast_monitor.db"
    )
    ap.add_argument(
        "--transcripts-dir",
        default="transcripts",
        help="Where to put dummy transcripts",
    )
    ap.add_argument(
        "--mode",
        choices=["archive", "delete"],
        default="archive",
        help="Archive or delete others (default: archive)",
    )
    ap.add_argument("--no-backup", action="store_true", help="Skip backups")
    ap.add_argument(
        "--no-dummy", action="store_true", help="Do not create dummy transcript files"
    )
    args = ap.parse_args()

    prep_databases(
        youtube_db=args.youtube_db,
        rss_db=args.rss_db,
        transcripts_dir=args.transcripts_dir,
        mode=args.mode,
        make_dummy=not args.no_dummy,
        no_backup=args.no_backup,
    )


if __name__ == "__main__":
    main()
