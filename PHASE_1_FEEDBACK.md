# Phase 1 (Datetime/Timezone) — Review of Agent Plan
Reviewer: Paul’s Architect • Date: 2025‑09‑05

**Verdict:** Good start, but **too narrow**. The plan focuses only on `feed_monitor.py` + removing `pytz`. Phase 1 should cover **all code paths that read/compare/store datetimes**, normalize legacy DB values, and lock down logging behavior. Below are precise corrections and additions.

---

## A) Corrections to the Agent Plan

1) **Function naming mismatch**
- Agent references `parse_rss_datetime()`; our standard is `parse_entry_to_utc()` and `parse_struct_time_to_utc()` (or equivalent).  
**Action:** Use the helper names defined in Phase 1 spec to avoid drift.

2) **Scope limited to `feed_monitor.py`**
- The naive/aware comparison bug can surface in **other modules** (e.g., `retention_cleanup.py`, `rss_generator_multi_topic.py`, `daily_podcast_pipeline.py`, and any ad‑hoc datetime writes to DB).  
**Action:** Update these modules to use `now_utc()`, `to_utc()`, `cutoff_utc()`, and the entry parsing helpers.

3) **Missing DB normalization**
- Plan omits migrating legacy timestamps already stored as naive strings. This will keep producing edge cases later.  
**Action:** Add `scripts/migrate_timestamps_to_utc.py` to normalize stored values and emit a summary.

4) **INFO log policy not enforced**
- Agent plans changes but doesn’t codify the logging goals (1 header + 1 totals line per feed, reasons at DEBUG).  
**Action:** Constrain INFO logs explicitly and keep per‑entry details at DEBUG to prevent future noise regressions.

5) **No explicit behavior for feeds with no dates**
- The Vergecast issue (offset compare) and “no dated entries” need a **single INFO line** and non‑fatal flow.  
**Action:** Implement a single INFO line: `⚠️ <feed>: no dated entries (skipped gracefully)` and avoid repeated spam (cache last notice).

6) **Monday/Friday labeling policy not stated**
- All comparisons should be UTC; labeling may use a **display TZ**.  
**Action:** Add `DIGEST_DISPLAY_TZ` (default `UTC`) for labeling only; keep RSS pubDate and comparisons in UTC.

---

## B) Additions Required for Phase 1

### 1) Helper Functions (augment `utils/datetime_utils.py`)
Add these and **use them everywhere**:
```python
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def cutoff_utc(hours: int) -> datetime:
    return now_utc() - timedelta(hours=hours)

def parse_struct_time_to_utc(st) -> datetime | None:
    if not st:
        return None
    # feedparser *_parsed is effectively UTC
    return datetime(*st[:6], tzinfo=timezone.utc)

def parse_entry_to_utc(entry):
    # Use *_parsed first when present
    for key in ("published_parsed", "updated_parsed"):
        st = getattr(entry, key, None) or (entry.get(key) if hasattr(entry, "get") else None)
        dt = parse_struct_time_to_utc(st)
        if dt:
            return to_utc(dt), key
    # Fallback to strings (RFC2822, ISO8601)
    for key in ("published", "updated", "date"):
        s = getattr(entry, key, None) or (entry.get(key) if hasattr(entry, "get") else None)
        if not s:
            continue
        try:
            return to_utc(parsedate_to_datetime(s)), key
        except Exception:
            pass
        try:
            return to_utc(datetime.fromisoformat(s.replace("Z", "+00:00"))), key
        except Exception:
            pass
    return None, "none"
```

### 2) Modules to Update
- `feed_monitor.py`: remove `pytz`, use helpers, calculate once: `cutoff = cutoff_utc(FEED_LOOKBACK_HOURS)`.
- `retention_cleanup.py`: any dates used for cutoff → helpers; keep UTC.
- `rss_generator_multi_topic.py`: ensure **pubDate** is RFC2822 in UTC; validate `enclosure` times if used.
- `daily_podcast_pipeline.py`: all date checks / labels go through helpers; add `DIGEST_DISPLAY_TZ` only for **labels**, not comparisons.
- `bootstrap_databases.py` and any ad‑hoc writers: store ISO8601 UTC strings (`...+00:00`).

### 3) DB Migration (`scripts/migrate_timestamps_to_utc.py`)
- For each DB (`podcast_monitor.db`, `youtube_transcripts.db`):  
  - Add new `_utc` columns (or migrate in place) for `published_at`, `created_at`, `updated_at`.
  - For naive strings, assume they were UTC; convert to aware UTC string.
  - For raw `published` text, attempt `parse_entry_to_utc` and store normalized UTC.
  - Emit JSON summary of rows updated.

### 4) Logging Policy
- INFO per feed: **one header** + **one totals** line, e.g.:
  - `▶ FeedName (entries=50, limit=50, cutoff=2025-09-05 12:00:00Z)`
  - `   totals: new=7 dup=40 older=2 no_date=1`
- Edge case line (once per run per feed): `⚠️ FeedName: no dated entries (skipped gracefully)`.
- Reasons for skipping (older/dup) → **DEBUG** only.

### 5) Env & CI
- Keep `TZ=UTC` in workflow.
- If any `pytz` usage remains, either add to requirements **or** refactor to stdlib (`zoneinfo`/helpers). Prefer removal.
- Ensure Linux runner has `tzdata` (usually present).

### 6) Monday/Friday Labeling
- Add `DIGEST_DISPLAY_TZ` env (default `UTC` or `America/Halifax` per your preference). Use it **only for human‑facing labels**.  
- All comparisons (lookback, retention, selection) remain in UTC.

---

## C) Tests & Verification (Phase 1)

**Unit tests (`tests/test_datetime_timezone.py`):**
- Naive vs aware → `to_utc` returns aware UTC.
- Entry parsing fixtures: with `published_parsed`, RFC2822 only, ISO only, and none → expected `(dt, source)` or `(None, "none")`.
- Cutoff comparison with frozen `now_utc()` → entries older than cutoff excluded.

**Manual checks:**
- `python3 feed_monitor.py --dry-run --limit 20 --verbose`  
  Expect no naive/aware warnings; one header + one totals line per feed; optional one‑time “no dated entries” INFO.
- `python3 scripts/migrate_timestamps_to_utc.py --dry-run` → JSON summary. Then run live.
- Pipeline dry‑run remains quiet; UTC timestamps in logs.

**CI:**
- Smoke still < 2 min; no timezone warnings; no `pytz` ImportError; cutoff printed with `Z`.

---

## D) Acceptance Criteria

- **AC‑1:** No `offset‑naive vs offset‑aware` exceptions in local & CI.
- **AC‑2:** Newly persisted timestamps are ISO8601 UTC strings; legacy rows normalized by migration.
- **AC‑3:** Feed scan INFO logs: header + totals only; per‑entry reasons at DEBUG.
- **AC‑4:** Feeds with no dates are skipped gracefully with a single INFO line.
- **AC‑5:** Monday/Friday labels computed in `DIGEST_DISPLAY_TZ`, all comparisons remain UTC.
- **AC‑6:** CI succeeds with `TZ=UTC`; no `pytz` ImportError.

---

## E) Quick Checklist for the Agent

- [ ] Remove `pytz` in `feed_monitor.py`; adopt helpers.
- [ ] Update `retention_cleanup.py`, `rss_generator_multi_topic.py`, `daily_podcast_pipeline.py`, writers.
- [ ] Implement `parse_entry_to_utc()` + `parse_struct_time_to_utc()` and call from all ingestion points.
- [ ] Implement DB migration to normalize timestamps to UTC.
- [ ] Enforce INFO/DEBUG logging policy for feeds.
- [ ] Add/adjust tests; run smoke; verify CI is quiet and green.