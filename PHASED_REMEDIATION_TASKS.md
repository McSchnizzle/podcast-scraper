
# Phased Remediation Task List — Podcast Scraper (GPT‑5, CI + Local)
Owner: Coding Agent • Reviewer: Paul • Date: 2025‑09‑05

> Goal: eliminate the remaining failures (GPT‑5 digests, timezone/date issues, noisy logs, telemetry/import errors),
> make local and GitHub Actions runs consistent, and verify RSS updates after TTS.

---

## Phase 0 — Guardrails & Baseline (do first) — ✅ 100% COMPLETE
**Why:** Stop regressions and make fixes observable.

- [x] **Enable "strict" CI**: add a `scripts/ci_smoke.sh` that runs: lints, unit smoke, env checks, and `--dry-run` digest.
- [x] **Pin runtime to UTC** everywhere:
  - [x] Code: set `DEFAULT_TZ="UTC"` and centralize `now_utc()` in `utils/datetime_utils.py` (see Phase 1).
  - [x] GitHub: in workflow, set `env: TZ: UTC`.
- [x] **.env & config sanity**: run `python config_validator.py --all` in CI and local before the pipeline.
- [x] **Reduce log noise default**: default to INFO, DEBUG only with `--verbose` or `LOG_LEVEL=DEBUG`. [COMPLETE - All files updated]

**Deliverables** ✅ 100% COMPLETE
- [x] `scripts/ci_smoke.sh` - ✅ Created with comprehensive smoke tests
- [x] Workflow step "Run CI smoke" calling that script - ✅ Added smoke-test job
- [x] `utils/datetime_utils.py` - ✅ Created with UTC helper functions
- [x] `utils/logging_setup.py` - ✅ Created with idempotent centralized logging
- [x] Updated `config_validator.py` with severity levels and `--warn-only` flag - ✅ Complete
- [x] Added `--dry-run` and `--timeout` support to daily_podcast_pipeline.py - ✅ Complete
- [x] Added CI_SMOKE and MOCK_OPENAI support to OpenAI modules - ✅ Complete
- [x] Replaced ALL datetime.utcnow() calls with UTC-aware alternatives - ✅ Complete
- [x] Updated GitHub workflow with TZ=UTC and smoke job - ✅ Complete
- [x] Log sample that is ≤ ~120 lines on a normal daily run - ✅ Complete (23 lines in dry-run mode)
- [x] Updated ALL remaining files to use centralized logging setup - ✅ Complete (9 additional files)

---

## Phase 1 — Datetime / Timezone Reliability — ✅ 100% COMPLETE
**Symptoms:** "offset‑naive vs offset‑aware", `pytz` missing in CI, inconsistent lookback windows.

- [x] **Remove `pytz` dependency** (preferred) and standardize on **`zoneinfo`** (Python 3.9+):
  - [x] Created `utils/datetime_utils.py` with enhanced helper functions: `now_utc()`, `to_utc()`, `cutoff_utc()`, `parse_entry_to_utc()`, `parse_struct_time_to_utc()`
  - [x] Replaced all `datetime.utcnow()` / naive `datetime.now()` usage with `now_utc()`
  - [x] All date comparisons now use `to_utc()` / `ensure_aware_utc()` for consistent timezone-aware comparisons
- [x] **Feed timestamps** (in `feed_monitor.py`):
  - [x] Completely removed `pytz` dependency and replaced with centralized datetime utilities
  - [x] Updated `_parse_date_to_utc()` to use `parse_entry_to_utc()` with robust fallback chain
  - [x] Lookback window now uses `cutoff_utc(FEED_LOOKBACK_HOURS)` for consistent UTC calculations
  - [x] Feeds with no dates handled gracefully with single INFO line: `⚠️ {feed}: no dated entries (skipped gracefully)`
  - [x] Implemented proper logging policy: 1 header + 1 totals line per feed, per-entry details moved to DEBUG
- [x] **CI Workflow**: TZ=UTC already set in GitHub Actions workflow
- [x] **Database Migration**: Created `scripts/migrate_timestamps_to_utc.py` to normalize legacy timestamp data
- [x] **Display Timezone Support**: Added `DIGEST_DISPLAY_TZ` environment variable for human-facing labels while keeping all logic in UTC

**Deliverables** ✅ 100% COMPLETE
- [x] `utils/datetime_utils.py` created with comprehensive helper functions
- [x] All imports updated across core modules: `feed_monitor.py`, `retention_cleanup.py`, `rss_generator_multi_topic.py`, `daily_podcast_pipeline.py`
- [x] No "offset‑naive vs offset‑aware" warnings - all datetime comparisons use timezone-aware UTC
- [x] CI log shows `🕐 Looking for episodes newer than …Z UTC` and **no** pytz errors
- [x] `scripts/migrate_timestamps_to_utc.py` created for database timestamp normalization
- [x] `tests/test_datetime_timezone.py` created with comprehensive test coverage
- [x] Feed logging policy implemented: INFO (header + totals), DEBUG (per-entry details)
- [x] DIGEST_DISPLAY_TZ support added for human-facing labels with UTC logic preservation

---

## Phase 2 — GPT‑5 Digest Generation (EpisodeSummaryGenerator + Scorer) — ✅ 100% COMPLETE
**Symptoms:** HTTP 400 "temperature not supported", empty content, map‑reduce ends with zero summaries.

- [x] **Responses API**: migrate summary + scoring calls to `client.responses.create(...)`.
- [x] **No `temperature`** for GPT‑5 reasoning models. Use:
  - `reasoning={"effort": os.getenv("SCORER_REASONING_EFFORT","minimal")}`
  - `max_output_tokens` (not `max_tokens`).
- [x] **Structured output**: replace `response_format={"type":"json_object"}` with **`json_schema` + `"strict": True`**.
- [x] **Parsing**: read `resp.content[0].text` (not `choices[0].message.content`). Persist the raw response for debugging.
- [x] **Config**: add to production config:
  ```python
  GPT5_MODELS = {
      'summary': 'gpt-5-mini', 'scorer': 'gpt-5-mini', 
      'digest': 'gpt-5', 'validator': 'gpt-5-mini'
  }
  OPENAI_TOKENS = {...}, REASONING_EFFORT = {...}, FEATURE_FLAGS = {...}
  ```
- [x] **Backoff**: wrap all OpenAI calls with 4‑retry exponential backoff + jitter.
- [x] **Enhanced Features**: Added anti-injection protection, idempotency keys, observability, and comprehensive testing.

**Deliverables** ✅ 100% COMPLETE
- [x] Created `utils/openai_helpers.py` with centralized GPT-5 Responses API integration - ✅ Complete
- [x] Created `utils/redact.py` for secret sanitization - ✅ Complete
- [x] Updated `config/production.py` with complete GPT-5 configuration - ✅ Complete
- [x] Migrated `episode_summary_generator.py` to GPT-5 with chunking and idempotency - ✅ Complete
- [x] Migrated `openai_digest_integration.py` to GPT-5 with full context processing - ✅ Complete
- [x] Migrated `prose_validator.py` to GPT-5 with TTS-optimized validation - ✅ Complete
- [x] Created `scripts/migrate_phase2_idempotency.py` for database schema updates - ✅ Complete
- [x] Added idempotency tables with unique constraints and performance indexes - ✅ Complete
- [x] Created `tests/test_phase2_gpt5_integration.py` with comprehensive test coverage - ✅ Complete
- [x] Created `scripts/verify_phase2.py` for complete verification - ✅ Complete
- [x] All verification checks pass: 7/7 categories (100% success rate) - ✅ Complete

---

## Phase 3 — Import/Telemetry Fixes — ✅ 100% COMPLETE
**Symptoms:** `cannot import name 'OpenAIScorer'`, `TelemetryManager` missing `record_metric`.

- [x] **Import compatibility** with enhanced approach:
  - [x] Created `openai_scorer_compat.py` compatibility shim with deprecation warnings
  - [x] Updated `utils/episode_failures.py` to use `OpenAITopicScorer` directly
  - [x] Removed `sys.path.append` hacks in favor of proper imports
  - [x] Added conditional export in `openai_scorer.py` via `ALLOW_LEGACY_OPENAI_SCORER_ALIAS`
  - [x] Created CI guard `tests/test_no_legacy_imports.py` to prevent future legacy imports
- [x] **Enhanced Telemetry** with structured metrics:
  - [x] Added `def record_metric(self, name: str, value: float=1.0, **labels)` to `telemetry_manager.py`
  - [x] Implemented automatic metric type detection via suffix convention (.count, .ms, .gauge)
  - [x] Added structured JSON logging for observability
  - [x] Created convenience methods: `record_counter()`, `record_gauge()`, `record_histogram()`
  - [x] Added backward compatibility mapping to existing run metrics

**Deliverables** ✅ 100% COMPLETE
- [x] Retry queue no longer fails imports - ✅ Fixed with compatibility shim and direct imports
- [x] No AttributeError on `record_metric` - ✅ Method implemented with structured logging
- [x] Comprehensive test suite - ✅ Created `tests/test_phase3_integration.py`
- [x] CI protection against regressions - ✅ Created `tests/test_no_legacy_imports.py`
- [x] Documentation updates - ✅ Created `CHANGELOG.md` with migration guide
- [x] Future-proof architecture - ✅ Structured telemetry ready for observability tools

---

## Phase 4 — Feed Ingestion Robustness — ✅ 100% COMPLETE
**Symptoms:** "No new episodes", offset errors, feeds with no dates, excessive per‑entry logging.

**IMPLEMENTATION COMPLETED:**
- [x] **Database Schema**: Created `feed_metadata` and `item_seen` tables with proper indexes
- [x] **Per-feed lookback controls**: `FEED_LOOKBACK_HOURS` with per-feed overrides via `lookback_hours_override`
- [x] **Grace period**: `FEED_GRACE_MINUTES` (default 15min) to avoid scheduler drift boundary flapping
- [x] **HTTP Caching**: ETag/Last-Modified conditional GET support with 304 response handling
- [x] **Deterministic date-less items**: Stable `first_seen_utc` timestamps via `item_seen` table
- [x] **Enhanced duplicate detection**: SHA256 item hashing with GUID → link → title+enclosure fallback
- [x] **2-line INFO logging**: Header + totals format per feed, DEBUG for per-entry details
- [x] **Warning suppression**: No repeated warnings for no-date/stale feeds (24h suppression)
- [x] **Telemetry integration**: Structured metrics with `run_id`, counters, and duration tracking
- [x] **HTTP politeness**: `FETCH_POLITENESS_MS` delay + `MAX_FEED_BYTES` size cap
- [x] **Feed order detection**: Auto-detect `typical_order` (reverse_chronological/chronological/unknown)
- [x] **Item seen retention**: Configurable cleanup of old deduplication records

**Enhanced Features:**
- [x] **Session-based HTTP client**: Connection pooling and header management
- [x] **Bounds enforcement**: 1-168 hour lookback limits with validation
- [x] **Structured error logging**: Feed-specific error context with telemetry
- [x] **Performance indexes**: Optimized queries for feed metadata and item lookups
- [x] **Environment sync**: All Phase 4 variables documented in both `.env` and `.env.example`

**Files Created/Modified:**
- [x] `scripts/migrate_feed_metadata_phase4.py` - Database migration script
- [x] `utils/feed_helpers.py` - Phase 4 utility functions  
- [x] `feed_monitor.py` - Complete rewrite with Phase 4 features
- [x] `config.py` - Enhanced with Phase 4 settings and fixed .env loading
- [x] `.env` and `.env.example` - Added 10 new Phase 4 environment variables
- [x] `tests/test_phase4_feed_ingestion.py` - Comprehensive test suite (16 test methods)

**Deliverables** ✅ 100% COMPLETE
- ✅ Exactly 2 INFO lines per feed (header + totals)
- ✅ Per-feed lookback controls with 15-minute grace period
- ✅ Date-less items handled deterministically without duplicate processing
- ✅ HTTP caching reduces bandwidth usage with ETag/Last-Modified
- ✅ Warning suppression prevents log spam
- ✅ Enhanced duplicate detection prevents re-processing
- ✅ Telemetry provides observability into feed processing performance
- ✅ New episodes discovered correctly when available within lookback window

**Database Migration Status**: ✅ Applied to both `podcast_monitor.db` (23 feeds) and `youtube_transcripts.db` (9 feeds)

---

## Phase 5 — Pending/Pre‑download Queue Fix
**Symptoms:** Repeated `Episode 129/130/... not found or already transcribed` then “No pending episodes”.

- [ ] Replace any loops over **ID ranges** with DB queries:
  ```sql
  SELECT id,title,url,status FROM episodes
  WHERE status IN ('pending','pre-download')
  ORDER BY created_at ASC LIMIT 50;
  ```
- [ ] If the code reads a saved list of IDs, **reconcile** against DB and drop non‑existent IDs silently.
- [ ] Logging:
  - Summarize: `Pending episodes: N`; log **one line per batch** at DEBUG, not one per missing ID.
  - When a specific episode is skipped, show **title** + id: `Skipping (already done): {title} [{id}]` (DEBUG).

**Deliverables**
- No more spammy “Episode N not found” runs
- Clear INFO summary of pending batch

---

## Phase 6 — Transcription Chunking UX
**Symptoms:** Logs show only file id (e.g., `5836c7ba.mp3`) not the episode title.

- [ ] Pull title + published date from DB and include in logs:
  - `🎬 Starting robust transcription: "{title}" [{id}] • {duration}m`
- [ ] When chunking, include label in filenames but keep DB‑id canonical:
  - File on disk: `{id}_chunk_{n}.wav`
  - Logs: `Chunk {n}: {start}-{end} • "{title}"`

**Deliverables**
- Human‑readable transcription logs
- DB‑safe filenames remain unchanged

---

## Phase 7 — TTS & File Detection
**Symptoms:** “No unprocessed digest files found” despite MDs in folder; old files prioritized; hyphen topics.

- [ ] Ensure the **regex** for digest files supports hyphens and underscores (already added):
  - `r'^([A-Za-z0-9_-]+)_digest_(\d{8}_\d{6})\.md$'`.
- [ ] Add `--since YYYYMMDD` to TTS script and pass **today** from the pipeline.
- [ ] Prefer **topic‑specific** digests first (ai‑news, tech‑news‑and‑tech‑culture, tech‑product‑releases). Daily omnibus is fallback.
- [ ] When no new MDs match `--since`, print single INFO: `✅ No new digests today`; do not dump directory lists at INFO (use DEBUG).

**Deliverables**
- TTS runs only on new digests created today
- Logs are concise

---

## Phase 8 — RSS Generation & Deployment
**Symptoms:** RSS updated when nothing new; GH deploy inconsistencies.

- [ ] RSS generator: **skip** update if no **new** MP3s today; log `RSS not updated: no new audio`.
- [ ] Validate `enclosure` files exist; fail gracefully with one line per missing file.
- [ ] GitHub deploy:
  - Print failing command, status code, and stderr if deploy fails.
  - Guard deploy if `deployed_episodes.json` doesn’t contain today’s items.
  - On success, print public URLs for today’s items only.

**Deliverables**
- Correct RSS gating
- Clear deploy failure diagnostics

---

## Phase 9 — GitHub‑specific Fixes
**Observed in logs:** `No module named 'pytz'`, different ASR engine, paths.

- [ ] Add `pytz` to `requirements.txt` (if you keep it) **or** finish Phase 1 refactor to `zoneinfo`.
- [ ] Detect CI in code (`os.getenv("CI")=="true"`) and automatically:
  - Use **Faster‑Whisper** (already doing) and skip macOS‑specific MLX/Metal toggles.
  - Avoid Mac‑only debug messages (`MallocStackLogging`).
- [ ] Ensure `daily_digests/` is preserved and uploaded as an artifact when the run fails (already configured).

**Deliverables**
- GH run free of pytz and platform warnings
- Artifact always contains latest digests/audio

---

## Phase 10 — Logging Policy & Defaults
**Symptoms:** Excessive lines at INFO; httpx chatter; repeated directory dumps.

- [ ] Centralize logging config in `utils/logging_setup.py`:
  ```python
  import logging, os
  def configure_logging():
      level = os.getenv("LOG_LEVEL","INFO").upper()
      logging.getLogger().setLevel(level)
      # quiet noisy libs
      for noisy in ["httpx","urllib3","openai","requests"]:
          logging.getLogger(noisy).setLevel(os.getenv("HTTP_LOG_LEVEL","WARNING"))
  ```
- [ ] Replace `print` with `logging`. Make long directory listings **DEBUG** only.
- [ ] Keep “headline” INFO lines only (phase start, counts, produced files, deploy summary).

**Deliverables**
- Clean INFO logs (< ~150 lines)
- DEBUG reveals details when needed

---

## Phase 11 — Documentation & Runbook
- [ ] Update `README.md` with: GPT‑5 settings, Responses API, timezone policy, TTS “since” usage.
- [ ] Add `RUNBOOK.md`: common failures + fixes (API 400 temperature, offset‑aware compare, retry queue import).

---

## Acceptance Criteria (AC)
- AC‑1: GH Actions run completes on Friday with **daily + weekly** digests OR exits cleanly if no transcripts.
- AC‑2: No timezone warnings/errors; no `pytz` ImportError.
- AC‑3: No 400 temperature errors; **at least one topic** digest produced under normal conditions.
- AC‑4: TTS generates **today’s MP3s** and RSS updates only when those MP3s exist.
- AC‑5: Logs at INFO are concise; DEBUG reveals detail.
- AC‑6: Retry queue runs without import/telemetry errors
