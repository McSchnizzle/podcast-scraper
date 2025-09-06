# Phase 4 — Feed Ingestion Robustness (Critique, Changes, Additions, and Verification)

**Scope reviewed:** Claude’s “Phase 4: Feed Ingestion Robustness” plan (lookback controls, no‑date feed handling, and logging policy).  
**Goal:** Make feed ingestion resilient, quiet at INFO, and provably correct (no missed items, no duplicate processing), while keeping UTC invariants from Phase 1 and telemetry from Phase 3.

---

## 1) Quick Verdict

- ✅ The plan is directionally solid (lookback control, no‑date handling, log noise reduction).  
- ⚠️ However, a few important concerns are missing: **per‑feed overrides**, **correctness when feeds reorder or republish**, **HTTP caching (ETag/Last‑Modified)**, **robust heuristics for date‑less items**, **duplicate detection**, and **clear acceptance tests** that prove we don’t miss or double‑ingest episodes.  
- 🛠️ The additions below make Phase 4 production‑grade without bloating scope.

---

## 2) Suggested Enhancements (Design)

### 2.1 Lookback controls (correctness + flexibility)
- **Per‑feed override:** Some feeds need longer windows (sporadic posts) or shorter ones (high volume).  
  - Add `feed_metadata.lookback_hours_override INTEGER NULL` (NULL = use global default).  
- **Hard bounds:** Enforce `1 ≤ FEED_LOOKBACK_HOURS ≤ 168` (7 days) to prevent unbounded scans.  
- **UTC‑anchored windows:** Keep comparisons strictly in UTC (already your invariant). Log the resolved window per feed: `cutoff_utc=... lookback_hours=... (override|default)`.
- **Grace period:** Add `FEED_GRACE_MINUTES` (e.g., 15–30m) to “float” the cutoff to avoid flapping around the hour boundary when schedulers drift.

### 2.2 HTTP caching & polite crawling
- **ETag/Last‑Modified:** Store and send these for conditional GETs to reduce bandwidth and rate‑limit exposure. Add to metadata:  
  - `etag TEXT NULL`, `last_modified_http TEXT NULL`.  
- **Robust timeouts & retries:** Use exponential backoff + jitter for fetch; cap total retries and propagate telemetry counters.  
- **Politeness delay:** Optional per‑host delay (env: `FETCH_POLITENESS_MS`) to avoid tripping WAFs.  
- **Response size guard:** Cap XML/JSON response size (env: `MAX_FEED_BYTES`) to avoid accidental huge downloads.

### 2.3 No‑date item handling (determinism without pubDate)
For items missing RFC2822 dates:
- **Deterministic synthetic timestamp:**  
  - Use (a) explicit `<updated>`/`<published>` if Atom; else (b) fall back to `first_seen_utc` recorded at ingestion; else (c) synthesize from a **stable sort key**.  
- **Stable sort key:** Hash of `(guid|link|title|enclosure_url|author)`; combine with **feed typical order** to position consistently.
- **First‑seen tracking:** Add table `item_seen(feed_id, item_id_hash, first_seen_utc)` for dedupe + ordering.  
- **Dedup rules:** Prefer GUID; if absent, hash link; if absent, hash (title + enclosure). Keep an LRU of last N seen hashes per feed in memory for fast duplicates.

### 2.4 Feed ordering and republish quirks
- **typical_order enum:** Instead of free text, add a CHECK constraint:  
  - `typical_order TEXT CHECK(typical_order IN ('reverse_chronological','chronological','unknown')) DEFAULT 'reverse_chronological'`  
- **Auto‑detect on first scan:** If the last 10 dated items are strictly descending, mark reverse‑chronological; otherwise ‘unknown’. Store confidence level if desired.  
- **Repub detection:** If an item reappears with a newer date or modified content, treat as **update**, not a new item; record `last_seen_utc` and `content_hash` to decide whether to reprocess.

### 2.5 Logging policy (quiet, structured, helpful)
- **INFO budget per feed/run:** exactly 2 lines baseline:  
  1) Header: `feed="..." items=NN dated=MM nodate=KK cutoff=... lookback=... etag_hit=bool changed=bool`  
  2) Totals: `new=..., updated=..., skipped=..., errors=... duration_ms=...`  
- **WARN:** one line for stale/no‑date status per run (suppressed on subsequent items).  
- **DEBUG:** per‑item details (reason for skip, dedupe decisions, computed timestamp, hash).  
- **Structured JSON logs:** Emit one structured line per feed at end for easy analysis and Phase‑3 telemetry integration.

### 2.6 Telemetry integration (Phase‑3 alignment)
Emit counters/histograms with low‑cardinality labels:  
- `ingest.fetch.bytes.count`, `ingest.fetch.ms`, `ingest.http.status.count`, `ingest.etag_hit.count`  
- `ingest.items.total.count`, `ingest.items.new.count`, `ingest.items.updated.count`, `ingest.items.duplicate.count`  
- `ingest.items.nodate.count`, `ingest.items.parse_error.count`  
Labels: `{"feed_id": "...", "source":"rss"|"youtube"}` and global `run_id`.

---

## 3) Database Changes (Small, Safe, and Idempotent)

```sql
-- 3.1 Feed metadata (extend existing table if you already created it)
CREATE TABLE IF NOT EXISTS feed_metadata (
  feed_id INTEGER PRIMARY KEY,
  has_dates BOOLEAN DEFAULT 1,
  typical_order TEXT CHECK(typical_order IN ('reverse_chronological','chronological','unknown')) DEFAULT 'reverse_chronological',
  last_no_date_warning TIMESTAMP NULL,
  lookback_hours_override INTEGER NULL,
  etag TEXT NULL,
  last_modified_http TEXT NULL,
  notes TEXT NULL,
  FOREIGN KEY (feed_id) REFERENCES feeds (id)
);

-- 3.2 First-seen / dedupe aid for date-less items (and for updates)
CREATE TABLE IF NOT EXISTS item_seen (
  feed_id INTEGER NOT NULL,
  item_id_hash TEXT NOT NULL,
  first_seen_utc TIMESTAMP NOT NULL,
  last_seen_utc TIMESTAMP NOT NULL,
  content_hash TEXT NULL,
  PRIMARY KEY (feed_id, item_id_hash),
  FOREIGN KEY (feed_id) REFERENCES feeds (id)
);
CREATE INDEX IF NOT EXISTS ix_item_seen_feed_last_seen ON item_seen(feed_id, last_seen_utc);
```

> **Note:** Keep migrations **idempotent** and add to your migration runner. Ensure UTC (`...Z`) for all timestamps.

---

## 4) Implementation Notes (Targeted)

- **Cutoff calculation:** `cutoff = now_utc() - timedelta(hours=effective_lookback)` where `effective_lookback` is `feed_metadata.lookback_hours_override or FEED_LOOKBACK_HOURS` (+ `FEED_GRACE_MINUTES/60`).  
- **No‑date timestamp:** compute `synthetic_dt_utc = first_seen_utc` (preferred); if first time seen, set it to `now_utc()` and persist in `item_seen`.  
- **Stable ID:** `item_id_hash = sha256(guid or link or (title + enclosure_url)).hexdigest()`; store in `item_seen`.  
- **Duplicate check:** if `(feed_id, item_id_hash)` exists, treat as duplicate/update (compare `content_hash` to decide).  
- **HTTP caching:** on fetch, send `If-None-Match`/`If-Modified-Since` when metadata available; if 304, short‑circuit item parsing and log `etag_hit=true`.

---

## 5) Tests & Verification (Additions to the Plan)

### 5.1 Unit tests
- **Lookback:** boundary cases (1h, 48h default, 168h); per‑feed override wins over global.  
- **No‑date items:** synthetic timestamp determinism; first‑seen persisted; idempotent re‑ingestion.  
- **Duplicate detection:** GUID present, GUID missing (link fallback), title+enclosure fallback.  
- **Ordering:** ‘reverse_chronological’ and ‘unknown’ behave consistently; re‑publish updates don’t double‑count.  
- **HTTP caching:** ETag/Last‑Modified roundtrip logic; 304 short‑circuit.  
- **Logging:** INFO has exactly 2 lines; WARN once per condition; DEBUG provides per‑item reasons.

### 5.2 Integration tests
- **Fixture feeds:**  
  1) Normal dated feed (descending).  
  2) No‑date feed (GUIDs + links only).  
  3) Mixed feed with malformed dates and a republished item (changed description).  
  4) Large feed (size cap hit) → verify graceful skip.  
  5) Conditional GET cycle: first fetch 200 w/ ETag, second fetch 304.
- **Assertions:**  
  - No missed new items when inside lookback.  
  - No duplicate records after reruns.  
  - Correct counts in telemetry (new/updated/duplicate).  
  - INFO output compact; DEBUG contains expected keys.

### 5.3 Performance & reliability
- **Throughput:** N feeds × M items with rate limit simulators; verify polite delay honored.  
- **Chaos:** injected network errors → retries/backoff → eventual success; errors counted and logged once per feed.

---

## 6) Acceptance Criteria (Phase 4)

- ✅ Ingestion respects **per‑feed** or global **lookback** with UTC cutoff + grace.  
- ✅ Items with **no dates** get deterministic synthetic timestamps and **are not missed** nor **double‑processed**.  
- ✅ **HTTP caching** via ETag/Last‑Modified reduces fetch volume; 304 path verified.  
- ✅ Logging at **INFO** limited to header + totals; warnings once per run; structured JSON summary present.  
- ✅ Telemetry counters/histograms emitted with `run_id`, low‑cardinality labels.  
- ✅ Integration tests pass for dated, no‑date, malformed, republish, and 304 scenarios.  
- ✅ Migration scripts are idempotent; DB timestamps remain UTC with `Z` suffix.

---

## 7) Minimal Code Skeletons (for clarity)

**Computing item hash:**
```python
def item_identity_hash(guid, link, title, enclosure_url):
    key = (guid or link or f"{title}|{enclosure_url or ''}").strip()
    return hashlib.sha256(key.encode('utf-8')).hexdigest()
```

**Synthetic timestamp for no‑date items:**
```python
first_seen = get_or_set_first_seen(feed_id, item_hash, now_utc())
synthetic_dt = first_seen  # deterministic
```

**Effective lookback:**
```python
hours = feed_meta.lookback_hours_override or FEED_LOOKBACK_HOURS
cutoff = now_utc() - timedelta(hours=hours) + timedelta(minutes=FEED_GRACE_MINUTES)
```

---

## 8) .env.example Additions

```
# Feed ingestion
FEED_LOOKBACK_HOURS=48
FEED_GRACE_MINUTES=15
MAX_FEED_BYTES=5242880          # 5 MB safety cap
FETCH_POLITENESS_MS=250         # polite delay between host requests
```

---

## 9) Rollout & Risk

- **Low risk** DB additions (new tables/columns). Test migrations on a copy first.  
- Default behaviors unchanged unless envs set; per‑feed overrides are opt‑in.  
- Reversible: removing ETag/Last‑Modified or item_seen only reduces efficiency, not correctness.

---

## 10) Summary

Claude’s plan is a good start. With **per‑feed lookback**, **ETag/Last‑Modified**, **deterministic handling for date‑less items**, **duplicate detection**, and **tight INFO logging + telemetry**, Phase 4 becomes robust and measurable. The verification steps ensure we neither **miss** items nor **double‑ingest**, and the system stays quiet and predictable in production.
