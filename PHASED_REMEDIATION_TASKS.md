
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

## Phase 2 — GPT‑5 Digest Generation (EpisodeSummaryGenerator + Scorer)
**Symptoms:** HTTP 400 “temperature not supported”, empty content, map‑reduce ends with zero summaries.

- [ ] **Responses API**: migrate summary + scoring calls to `client.responses.create(...)`.
- [ ] **No `temperature`** for GPT‑5 reasoning models. Use:
  - `reasoning={"effort": os.getenv("SCORER_REASONING_EFFORT","minimal")}`
  - `max_completion_tokens` (not `max_tokens`).
- [ ] **Structured output**: replace `response_format={"type":"json_object"}` with **`json_schema` + `"strict": True`**.
- [ ] **Parsing**: read `resp.output_text` (not `choices[0].message.content`). Persist the raw response for debugging.
- [ ] **Config**: add to production config:
  ```python
  OPENAI_SETTINGS = {
      "model": os.getenv("SCORER_MODEL","gpt-5-mini"),
      "max_completion_tokens": int(os.getenv("SCORER_MAX_COMPLETION_TOKENS","700")),
      "reasoning_effort": os.getenv("SCORER_REASONING_EFFORT","minimal"),
      "relevance_threshold": float(os.getenv("RELEVANCE_THRESHOLD","0.65")),
      # optional: "verbosity": "low"
  }
  ```
- [ ] **Backoff**: wrap all OpenAI calls with 4‑retry exponential backoff + jitter.
- [ ] **Map‑Reduce**: if fewer than N summaries are produced for a topic due to API errors, **retry once** before aborting topic.

**Deliverables**
- Diffs for `episode_summary_generator.py`, `openai_scorer.py`
- Local smoke test proving JSON is returned and parsed
- No more 400 “temperature” errors

---

## Phase 3 — Import/Telemetry Fixes
**Symptoms:** `cannot import name 'OpenAIScorer'`, `TelemetryManager` missing `record_metric`.

- [ ] **Import alias** for backward compatibility in `openai_scorer.py`:
  ```python
  class OpenAIRelevanceScorer(...):
      ...

  # Back-compat export
  OpenAIScorer = OpenAIRelevanceScorer
  __all__ = ["OpenAIRelevanceScorer","OpenAIScorer"]
  ```
- [ ] **Telemetry**:
  - Add `def record_metric(self, name: str, value: float=1.0, **labels): ...` to `telemetry_manager.py`.
  - Internally route to existing counters/histograms or no‑op with logged DEBUG (“metric recorded”).

**Deliverables**
- Retry queue no longer fails imports
- No AttributeError on `record_metric`

---

## Phase 4 — Feed Ingestion Robustness
**Symptoms:** “No new episodes”, offset errors, feeds with no dates, excessive per‑entry logging.

- [ ] **Lookback controls**: add `FEED_LOOKBACK_HOURS` env (default 48) already referenced; ensure it’s respected.
- [ ] **No‑date feeds**: treat as informational
  - Count and log one line: `⚠️  <feed>: no dated entries (skipped gracefully)`
  - Store a feed‑level flag so CI doesn’t repeatedly log noise every run.
- [ ] **Logging reduction**: for per‑feed processing, log:
  - One header line (feed name, entries seen, cutoff)
  - One totals line (`new/dup/older/no_date`) only
  - DEBUG (not INFO) for per‑entry reasons (duplicate/older).

**Deliverables**
- A single INFO line per feed + one totals line
- New episodes actually discovered when available

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
