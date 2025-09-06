# Podcast Scraper & Daily Digest — Product Requirements (PRD)
**Version:** v4-complete (post Phase 0–4 remediation)  
**Last updated:** 2025-09-05

## 1) Overview
The Podcast Scraper system ingests podcast RSS feeds (and YouTube transcripts), normalizes and deduplicates items, transcribes audio where needed, scores content, and generates a daily, human‑readable digest. Phases 0–4 focused on reliability, correctness, and data integrity. This PRD reflects the current, working system and defines expectations going into Phase 5 and beyond.

### Primary objectives
- Ingest and process new items from a curated feed list in a **reliable, idempotent, and efficient** way.
- Ensure **UTC-only time handling** and deterministic processing (Phase 1).
- Provide **stable GPT-5 integration** for topic scoring and summaries (Phase 2).
- Maintain **system stability** with clear telemetry and retry semantics (Phase 3).
- Enforce **database integrity** (FKs, schema versioning, caching metadata) across all components (Phase 4).

### Out of scope (for now)
- Full web UI, user auth, workflow approvals.
- Personalized, per-user digests and distribution pipelines.
- Multi-tenant separation guarantees.

## 2) Personas & Jobs-to-be-done
- **Operator** (you): run the pipeline, monitor ingestion, and publish daily digest.
- **Developer**: extend feed list, adjust scoring rules, maintain pipelines, monitor CI and integrity.
- **Reader** (downstream): consume concise daily digest without duplicates or junk.

## 3) System overview (current architecture)
- **Feed ingestion** (`feed_monitor.py`): fetch RSS, honor HTTP caching (ETag / Last-Modified), detect feed order, parse date-less items deterministically, and write metadata.
- **Transcription**: ASR when needed (local/MLX path supported; optional).
- **Scoring** (`openai_scorer.py`): topic/quality scoring via GPT-5.
- **Digest assembly** (`openai_digest_integration.py`, `rss_generator.py`): produce daily digest content with RFC‑5322 timestamps.
- **Pipeline orchestrator** (`daily_podcast_pipeline.py`): orchestrates end-to-end flow and post-run updates.
- **Telemetry** (`utils/telemetry_manager.py`): structured counters/gauges/timers.
- **DB layer**: centralized connection factory with enforced integrity (`utils/db.py`).

## 4) Functional requirements
1. **Ingestion & caching**
   - Send conditional GETs when metadata exists; persist `etag` and `last_modified_http` per feed.
   - On 304: do not mutate cache fields.
   - Respect `max_feed_bytes` and `politeness_delay_ms`.
2. **Item parsing & order detection**
   - Detect chronological vs reverse-chronological vs unknown over the first N items.
   - For date-less items, compute deterministic `first_seen_utc` to prevent double-processing.
3. **Lookback & grace**
   - `lookback_hours` default **72** with optional per-feed override; apply `grace_minutes` at the boundary only.
4. **Deduplication**
   - Stable `item_identity_hash()` with GUID → normalized URL → title+enclosure fallback chain.
   - `item_seen` enforces `UNIQUE(feed_id, item_hash)`.
5. **Logging policy**
   - Two-line INFO per feed: counts, timing, etag_hit, order, and warnings (suppressed once per 24h).
6. **Telemetry**
   - Expose metrics for fetch duration, items_new, items_cached, failures, cache_hits, cache_misses.
7. **Digest generation**
   - RFC‑5322 dates via `email.utils.format_datetime(now_utc())`.
   - Human-facing times derive from a **display TZ** only for labels; internal storage is UTC.
8. **Error handling**
   - Failures are captured in `episode_failures` with FK to `episodes(id)` and `ON DELETE CASCADE`.

## 5) Non‑functional requirements
- **Time handling**: UTC everywhere via `utils/datetime_utils.now_utc()`.
- **Database integrity**: SQLite **schema v2** with FK enforcement (`PRAGMA foreign_keys=ON`) and WAL mode.
- **Performance**: Conditional HTTP caching; indexed FKs and dedupe keys.
- **Operability**: Integrity verification script; double-run smoke; CI gates (no direct sqlite3.connect).
- **Idempotency**: Safe re-runs; deterministic hashing and timestamps.

## 6) Data model (schema v2 summary)
- `feeds (id INTEGER PRIMARY KEY, ... )`
- `episodes (id INTEGER PRIMARY KEY, episode_id TEXT, status TEXT, ... )`
- `feed_metadata (feed_id INTEGER FK→feeds.id, etag TEXT, last_modified_http TEXT, last_warning_ts TIMESTAMP, last_no_date_ts TIMESTAMP, ... INDEXES)`
- `item_seen (id INTEGER PK, feed_id INTEGER FK→feeds.id, item_hash TEXT, first_seen_utc TIMESTAMP, UNIQUE(feed_id, item_hash))`
- `episode_failures (id INTEGER PK, episode_pk INTEGER NOT NULL FK→episodes.id ON DELETE CASCADE, failure_reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)`

> All connections are created via `utils.db.get_connection(db_path)` which sets FK=ON, WAL, timeouts, and validates schema version.

## 7) Configuration (env + config/production.py)
- `LOOKBACK_HOURS` (default **72**)
- `GRACE_MINUTES` (default **15**)
- `MAX_FEED_BYTES` (default **5242880**)
- `POLITENESS_DELAY_MS` (default **250**)
- `ENABLE_HTTP_CACHING` (default **true**)
- `DETECT_FEED_ORDER` (default **true**)
- `ITEM_SEEN_RETENTION_DAYS` (default **30**)
- `DIGEST_DISPLAY_TZ` (labels only; storage remains UTC)

## 8) CI & quality gates
- Test suite (unit + integration) must pass.
- Integrity check: `scripts/verify_schema_integrity.py --strict` on all DBs (FK=1, `foreign_key_check` empty, `user_version=2`, indexes present).
- Static scan denies `sqlite3.connect(` outside `utils/db.py` (post‑Phase‑4 expansion).
- Grep gate against `datetime.utcnow(` / naked `datetime.now(` calls (must use `now_utc()`).

## 9) Operations & runbook
- **Double-run smoke** (pre-release): run ingestion twice on a copy DB; verify 304s, no dupes, clean two-line logs, and one-time warnings.
- **Backups**: take DB backups prior to migrations; retain last 7.
- **Nightly integrity** (optional cron): run `verify_schema_integrity.py --strict` and alert on failure.

## 10) Release notes for v4‑complete
- Adopted centralized DB factory; removed 100% of direct `sqlite3.connect` calls.
- Migrated `episode_failures` to **Option A** FK; enabled FK enforcement and WAL system‑wide.
- Standardized UTC via `now_utc()`; removed deprecation warnings.
- Stabilized dedupe hash; hardened HTTP cache header storage.
- Two-line INFO logging with suppression and centralized formatting.
- Test suite updated; schema integrity tools added.

## 11) Phase 5 (next)
**Theme:** Pipeline gating and queue hygiene (pre-download/processing order).  
**Goals:**
- Ensure transcripts/scoring/ingestion sequencing is correct and gated (no empty digests, no skipped episodes).
- Add a “pending queue” with deterministic ordering and backpressure.
- Strengthen retry behavior with jitter and max-attempt policies.
- Expand metrics for queue depth, age, and throughput.

**Deliverables:**
- Queue data model & migration (if needed) with integrity checks.
- Orchestrator updates with gates and idempotent transitions.
- Tests: ordering, backpressure, retry caps, and failure visibility.
