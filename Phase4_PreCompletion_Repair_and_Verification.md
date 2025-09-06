# Phase 4 — Pre‑Completion Repair & Verification Overview

**Audience:** Architect, coding agent  
**Goal:** Clearly enumerate what must be repaired before Phase 4 can be called “complete,” and define a verification plan that proves both Phase 4 functionality **and** data‑model integrity.

---

## 1) Executive Summary

Phase 4 delivered the intended ingestion features (per‑feed lookback, HTTP caching, deterministic handling for date‑less items, enhanced duplicate detection, concise logging, and telemetry). However, the **database layer is structurally unsafe** due to referential‑integrity problems and inconsistent foreign‑key enforcement. The most critical issue is a **foreign‑key mismatch between `episode_failures` and `episodes`**. Integration tests only passed because **foreign keys were disabled**, which masks real defects and risks.  

**Bottom line:** Phase 4 is *functionally close* but **not complete** until the schema is aligned, orphaned data is reconciled, and FK enforcement is consistently enabled and verified in CI and local runs.

---

## 2) What Must Be Repaired (High‑Level)

1. **Fix the `episode_failures` → `episodes` relationship**
   - Current state: `episode_failures.episode_id` (TEXT) references `episodes.episode_id` (TEXT) while **the true PK** is `episodes.id` (INTEGER).  
   - Required: choose **one** of the two valid models and refactor consistently:
     - **Option A (preferred):** `episode_failures.episode_id` → **rename to `episode_pk` (INTEGER)**, with `FOREIGN KEY (episode_pk) REFERENCES episodes(id)`.  
     - **Option B:** Keep `episode_failures.episode_id` (TEXT) **but make `episodes.episode_id` `UNIQUE NOT NULL`** and index it, then reference that unique column explicitly.
   - Update all code paths, queries, and tests accordingly.

2. **Enforce foreign keys across *all* DB connections**
   - Centralize DB access via a single **connection factory** that runs `PRAGMA foreign_keys=ON` immediately after connect.  
   - Remove any call sites that leave FK enforcement off.  
   - Add a startup self‑test that fails fast if `PRAGMA foreign_keys` isn’t enabled.

3. **Reconcile Phase 4 tables with existing schema**
   - Validate relationships for newly added tables (`feed_metadata`, `item_seen`).  
   - Ensure `feeds.id` is `INTEGER PRIMARY KEY` and that referencing tables use the correct type and FK constraints.  
   - Add/confirm **indexes & uniqueness** that Phase 4 relies on for performance/correctness (see §3.3).

4. **Audit & clean existing data**
   - Identify and resolve **orphaned rows** in `episode_failures`, `item_seen`, and any tables referencing `feeds` or `episodes`.  
   - Decide on policy for handling orphans (delete, migrate to placeholder, or fix mapping).

5. **Make integrity verifiable in CI**
   - Add a CI step that runs `PRAGMA foreign_key_check;` and **fails** if violations exist.  
   - Add a schema‑integrity test that verifies required indexes/uniques are present.

---

## 3) Concrete Repair Plan

### 3.1 Schema Correction (DDL)

Pick **Option A (preferred)** or **Option B** below and apply consistently.

**Option A — Reference the real PK (`episodes.id`)**

```sql
-- 1) New column on episode_failures that references episodes.id
ALTER TABLE episode_failures ADD COLUMN episode_pk INTEGER;

-- 2) Backfill using current text link
UPDATE episode_failures ef
SET episode_pk = (
  SELECT e.id
  FROM episodes e
  WHERE e.episode_id = ef.episode_id
);

-- 3) Enforce not null where mapping succeeded
UPDATE episode_failures SET episode_pk = NULL WHERE episode_pk IS NULL; -- (diagnostic)
-- Decide policy for NULLs: delete or fix mapping. Assuming delete:
DELETE FROM episode_failures WHERE episode_pk IS NULL;

-- 4) Rebuild table to enforce FK (SQLite requires table rebuild for FK/constraints)
CREATE TABLE episode_failures_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  episode_pk INTEGER NOT NULL,
  failure_reason TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (episode_pk) REFERENCES episodes(id) ON DELETE CASCADE
);

INSERT INTO episode_failures_new (id, episode_pk, failure_reason, created_at)
SELECT id, episode_pk, failure_reason, created_at
FROM episode_failures;

DROP TABLE episode_failures;
ALTER TABLE episode_failures_new RENAME TO episode_failures;

-- 5) Index for join performance
CREATE INDEX IF NOT EXISTS idx_episode_failures_episode_pk ON episode_failures(episode_pk);
```

**Option B — Keep TEXT id but enforce uniqueness on `episodes.episode_id`**

```sql
-- 1) Ensure uniqueness
CREATE UNIQUE INDEX IF NOT EXISTS ux_episodes_episode_id ON episodes(episode_id);

-- 2) Rebuild episode_failures to reference that unique column explicitly
CREATE TABLE episode_failures_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  episode_id TEXT NOT NULL,
  failure_reason TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

INSERT INTO episode_failures_new (id, episode_id, failure_reason, created_at)
SELECT id, episode_id, failure_reason, created_at
FROM episode_failures;

DROP TABLE episode_failures;
ALTER TABLE episode_failures_new RENAME TO episode_failures;

-- 3) Index for join performance
CREATE INDEX IF NOT EXISTS idx_episode_failures_episode_id ON episode_failures(episode_id);
```

> **Recommendation:** Option A is more conventional and less error‑prone long‑term.

### 3.2 Consistent FK Enforcement

- Introduce `db.py` (or similar) that exposes `get_connection(db_path)`:
  - Opens SQLite connection
  - Executes `PRAGMA foreign_keys=ON`
  - Returns connection
- Replace all direct `sqlite3.connect(...)` calls with the factory.  
- Add a **startup preflight**:
  - `SELECT PRAGMA foreign_keys;` → expect `1`, else raise.

### 3.3 Indexes & Uniqueness (verify/create)

- `episodes`: ensure `id INTEGER PRIMARY KEY`. Consider `UNIQUE(episode_id)` if Option B.  
- `feeds`: ensure `id INTEGER PRIMARY KEY`.  
- `feed_metadata`: FK to `feeds(id)`; index `feed_id`.  
- `item_seen`: retain dedupe efficacy with **unique natural keys**, e.g.  
  - `UNIQUE (feed_id, item_guid_hash)` or `UNIQUE (feed_id, item_url_hash)` depending on the implementation.  
  - Index `first_seen_utc` if used for retention cleanup/performance.  
- `episode_failures`: index the FK column (`episode_pk` or `episode_id`).

### 3.4 Data Audit & Cleanup (DML)

Run these diagnostics **before** and **after** migration:

```sql
-- Orphans relative to episodes (Option A)
SELECT COUNT(*) AS orphans FROM episode_failures ef
LEFT JOIN episodes e ON e.id = ef.episode_pk
WHERE e.id IS NULL;

-- Orphans relative to episodes (Option B)
SELECT COUNT(*) AS orphans FROM episode_failures ef
LEFT JOIN episodes e ON e.episode_id = ef.episode_id
WHERE e.episode_id IS NULL;

-- Orphans in item_seen (assuming FK exists on feed_id)
SELECT COUNT(*) AS orphans FROM item_seen s
LEFT JOIN feeds f ON f.id = s.feed_id
WHERE f.id IS NULL;
```

If any orphans exist, choose policy:
- **Delete** orphaned rows, or
- **Fix** by mapping to the correct parent, or
- **Quarantine** to a separate table for manual review.

### 3.5 Transaction, Backup, and Rollback

- Take a **full backup** of the DB file(s) prior to schema changes.  
- Perform migration in a transaction where possible.  
- Keep a **rollback plan** (restore from backup) if migration asserts fail.  
- Log counts moved/affected per table for auditability.

---

## 4) Code Changes Required

- Update all SQL and helper functions to use the corrected FK model (Option A or B).  
- Replace ad‑hoc connections with the **connection factory** that turns FKs ON.  
- Ensure any code that creates temp tables or runs maintenance also uses FKs ON.  
- Verify any joins still work with the new FK column names/types.  
- Add defensive checks in `feed_monitor.py` where IDs are read/written, to ensure no TEXT/INT mismatches remain.

---

## 5) Verification Plan (Proves Functionality **and** Integrity)

**A. Pre‑Migration Baseline (on a copy of production DB)**  
1. Run feed ingestion with current Phase 4 to capture a baseline log/telemetry snapshot.  
2. Capture **row counts per table** and diagnostics from §3.4 (orphan counts).  
3. Confirm current tests pass **with FKs ON** (they should fail if integrity is broken — that’s expected at this stage).

**B. Migration Dry‑Run (test DB copy)**  
1. Apply the migration script (DDL + DML) on a **copy**.  
2. Re‑run diagnostics (§3.4) — expect **0 orphans**.  
3. Verify schema (`.schema` or `sqlite_master`) shows expected FKs, indexes, and uniques.  
4. Run **`PRAGMA foreign_key_check;`** — **must return no rows**.  
5. Run full test suite **with FKs ON** — all must pass.

**C. Functional Regression (Phase 4 features)**  
1. **HTTP caching**: verify conditional GETs hit 304s on second run.  
2. **Per‑feed lookback & grace**: simulate boundary times and confirm items within the window are discovered once.  
3. **Date‑less items**: confirm deterministic `first_seen_utc` behavior (no duplicate processing).  
4. **Duplicate detection**: confirm the SHA256/fallback logic prevents re‑processing.  
5. **Stale feed detection**: confirm warnings appear once (suppression working).  
6. **Logging/telemetry**: verify “2‑line per feed” INFO format and counters/durations are emitted.

**D. CI Gates (make it provable every run)**  
- Add a CI job that runs:
  - `python scripts/verify_schema_integrity.py` which executes:
    - `PRAGMA foreign_keys;` = 1 check
    - `PRAGMA foreign_key_check;` empty check
    - Required index/unique presence check
  - Full test suite with FKs ON.  
- Fail the build if any of the above checks fail.

**E. Production Cutover Checklist**  
1. Backup production DB(s).  
2. Stop writers / pause pipeline.  
3. Apply migration.  
4. Run `verify_schema_integrity.py` against production DB.  
5. Resume pipeline and monitor logs + telemetry for 24–48h.  
6. If issues appear, restore from backup and roll back code to Phase 3/early‑4 state.

---

## 6) Acceptance Criteria — “Phase 4 Complete”

1. **Schema integrity:** `PRAGMA foreign_key_check;` returns **no rows**; all intended FKs are present and enforced.  
2. **No orphans:** Diagnostics in §3.4 return zero orphans after migration.  
3. **Consistent connections:** All DB connections enable FKs (verified by preflight + CI).  
4. **Indexes in place:** Required indexes/uniques exist (`item_seen` dedupe key; FK indexes).  
5. **Functional regression‑free:** All Phase 4 feature tests pass (HTTP caching, lookback/grace, date‑less handling, dedupe, stale detection, logging format).  
6. **CI protection:** Schema integrity and FK enforcement checks run on every PR and push.  
7. **Runbook updated:** README/RUNBOOK documents the FK model and migration steps.

---

## 7) Task Breakdown (Agent‑Oriented)

- [ ] Implement **Option A** schema migration (preferred) and mapping logic.  
- [ ] Create **DB connection factory** with `foreign_keys=ON`; refactor call sites.  
- [ ] Add `scripts/verify_schema_integrity.py` and CI wiring.  
- [ ] Add/verify required indexes & uniques (episodes, feeds, item_seen, episode_failures).  
- [ ] Write diagnostics for orphans and include in CI (warn on 0, fail if >0).  
- [ ] Update code paths and tests to the corrected FK model.  
- [ ] Run full verification plan on a copy of production data; produce a short report.  
- [ ] Execute production cutover with backup/rollback steps.

---

## 8) Risk & Mitigation

- **Risk:** Data that cannot be mapped from `episode_failures.episode_id` → `episodes.id`.  
  - **Mitigation:** Pre‑compute mapping report; decide delete/fix/quarantine policy; do not proceed until policy executed.  
- **Risk:** Hidden sites creating connections without FKs ON.  
  - **Mitigation:** Central factory + CI static search to forbid direct `sqlite3.connect` usage.  
- **Risk:** Performance regressions after adding constraints.  
  - **Mitigation:** Index FK columns and dedupe keys; capture before/after timings in verification.

---

**Recommendation:** Proceed with **Option A** (FK to integer PK) for simplicity and durability. Treat this as a one‑time schema correction with strong CI gates so future phases aren’t forced to disable constraints again.
