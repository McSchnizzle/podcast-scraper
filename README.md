# Podcast Scraper & Daily Digest
**Status:** v4-complete (Phases 0–4 finished) • **DB schema:** v2 • **Integrity enforced** ✅

A robust pipeline that ingests podcast RSS (and YouTube transcripts), transcribes as needed, scores with GPT‑5, and publishes a daily digest. Phases 0–4 focused on time correctness, stability, and database integrity. Phase 5 will improve pipeline gating and the pending/pre-download queue.

---

## Quick start

### 1) Requirements
- Python 3.11+ (recommended)
- `pip install -r requirements.txt`
- SQLite (bundled with Python)

### 2) Environment
Create `.env` (or set env vars) — defaults shown:
```env
LOOKBACK_HOURS=72
GRACE_MINUTES=15
MAX_FEED_BYTES=5242880
POLITENESS_DELAY_MS=250
ENABLE_HTTP_CACHING=true
DETECT_FEED_ORDER=true
ITEM_SEEN_RETENTION_DAYS=30
DIGEST_DISPLAY_TZ=UTC  # human-facing labels only
```

### 3) Initialize / verify databases
```bash
python scripts/migrate_phase4_schema_integrity.py  # idempotent
python scripts/verify_schema_integrity.py podcast_monitor.db --strict
python scripts/verify_schema_integrity.py youtube_transcripts.db --strict
```

### 4) Run the pipeline
```bash
python daily_podcast_pipeline.py --status     # quick status
python feed_monitor.py --dry-run              # shows per-feed 2-line logs + caching
python daily_podcast_pipeline.py              # full run
```

---

## Key features (v4)
- **UTC everywhere** via `utils.datetime_utils.now_utc()` — no naive datetimes.
- **HTTP caching** with ETag/Last‑Modified; correct 200/304 behavior.
- **Stable dedupe** via `item_identity_hash()` and `item_seen` unique key.
- **Two-line INFO logs** per feed; stale/no‑date warnings are suppressed once/24h.
- **Centralized DB factory** (`utils/db.py`) sets `foreign_keys=ON`, WAL, timeouts, and schema checks.
- **Integrity tools**: `scripts/verify_schema_integrity.py --strict` (FK check, schema v2, required indexes).
- **Telemetry hooks** via `utils/telemetry_manager.py`.

## Data model (schema v2)
- `feeds(id PK, …)`  
- `episodes(id PK, episode_id TEXT, status TEXT, …)`  
- `feed_metadata(feed_id FK→feeds.id, etag, last_modified_http, last_warning_ts, last_no_date_ts, …)`  
- `item_seen(id PK, feed_id FK→feeds.id, item_hash, first_seen_utc, UNIQUE(feed_id, item_hash))`  
- `episode_failures(id PK, episode_pk INTEGER NOT NULL FK→episodes.id ON DELETE CASCADE, failure_reason, created_at)`

> **All** DB access goes through `utils.db.get_connection(db_path)`.

## Logging
- Centralized helpers in `utils/logging_setup.py`, including `format_feed_stats(...)`.
- Two-line INFO per feed with counts, durations, caching flags, and order detection.

## CI & quality gates
- Full test suite must pass.
- **No direct `sqlite3.connect(`** outside `utils/db.py` (CI enforced).
- **No `datetime.utcnow(`/bare `datetime.now(`)** — must use `now_utc()` (CI enforced).

## Common commands
```bash
# Lint/tests
pytest -q
# Integrity
python scripts/verify_schema_integrity.py --all --strict
# Double-run smoke (use a DB copy)
python feed_monitor.py --dry-run && python feed_monitor.py --dry-run
```

## Release process
1. Ensure tests + integrity checks are green.
2. Run a double-run smoke (expect 304s and zero dupes).
3. Tag: `git tag v4-complete && git push --tags`.
4. (Optional) Build an artifact:
   ```bash
   python scripts/make_release_zip.py  # excludes .git, *.zip, *.mp3, *.wav, etc.
   ```

## Roadmap (Phase 5 preview)
- **Queue gating** to prevent mis-ordered processing and empty digests.
- Deterministic pre-download queue and backpressure.
- Stronger retries with jitter and max-attempt caps.
- Metrics for queue depth, age, and throughput.

## Contributing
- Use the connection factory for **all** DB access.
- Use `now_utc()` for **all** time reads.
- Keep RFC‑5322 for RSS pubDate.
- Update tests with regex matchers for logs to avoid brittleness.

---

**Questions?** Check `PHASED_REMEDIATION_TASKS.md` and the scripts under `scripts/` for migrations and integrity verification.
