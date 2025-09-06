You’re on the right track. Here’s exactly how to instruct Claude to finish this cleanly, without thrashing code.

# Instructions to proceed (fix the critical blocker)

## 0) Guardrails (once, up front)

* **Scope freeze:** Only modify the **3 critical production files** now:

  * `daily_podcast_pipeline.py`
  * `openai_scorer.py`
  * `openai_digest_integration.py`
* **Do not** touch scripts/tests/legacy in this pass. We’ll ticket those after green.

## 1) Replace direct connections with the factory (surgical edits)

### 1.1 Exact patterns to change

* Add:

  ```python
  from utils.db import get_connection
  ```
* Replace each:

  ```python
  conn = sqlite3.connect(<path_or_var>)
  ```

  with:

  ```python
  conn = get_connection(<path_or_var>)
  ```
* Remove any `conn.execute("PRAGMA foreign_keys=ON")`—the factory enforces this.

> If a module relies on `row_factory` or similar connection options, **move those into** `get_connection()` so behavior is consistent everywhere.

### 1.2 Patch examples (show Claude the exact diff style)

**daily\_podcast\_pipeline.py**

```diff
- import sqlite3
+ import sqlite3
+ from utils.db import get_connection
...
- conn = sqlite3.connect(self.db_path)
+ conn = get_connection(self.db_path)
  cursor = conn.cursor()
```

**openai\_scorer.py**

```diff
- import sqlite3
+ import sqlite3
+ from utils.db import get_connection
...
- with sqlite3.connect(db_path) as conn:
+ with get_connection(db_path) as conn:
    cur = conn.cursor()
```

**openai\_digest\_integration.py**

```diff
- conn = sqlite3.connect(db_path)
+ conn = get_connection(db_path)
  cur = conn.cursor()
```

> Important: **context managers** (`with ... as conn:`) must wrap `get_connection(db_path)` exactly as they did `sqlite3.connect`.

### 1.3 Remove/disable any fallback code paths that recreate old schemas

* Ensure none of these three files declare or recreate tables. DDL lives **only** in migrations.
* If they still contain DDL helpers, strip them out or have them **import** the canonical migration/DDL.

## 2) Re-run the static scan and enforce in CI

### 2.1 Local static scan (critical path only)

Run (from repo root):

```bash
echo "=== CRITICAL PRODUCTION FILES (must be clean) ==="
grep -Hn "sqlite3\.connect" \
  daily_podcast_pipeline.py \
  openai_scorer.py \
  openai_digest_integration.py || echo "OK: No direct connections found"
```

Expect: **no matches**.

### 2.2 Keep the global scan for visibility (non-blocking this pass)

```bash
find . -name "*.py" -not -path "./utils/db.py" -not -path "./.github/*" \
  -exec grep -Hn "sqlite3\.connect" {} \; | sort
```

* If other files show up: **do not fix now**. Create a ticket “Replace direct DB connections with factory (non-critical files)”.

### 2.3 CI gate (tighten it slightly)

In the workflow step that enforces factory usage, add a **positive allowlist** to block only critical paths for this pass:

```bash
# Fail if any direct connect in critical production files
BAD=$(grep -Hn "sqlite3\.connect" daily_podcast_pipeline.py openai_scorer.py openai_digest_integration.py || true)
if [ -n "$BAD" ]; then
  echo "Direct sqlite3.connect usage found in critical files:"
  echo "$BAD"
  exit 1
fi
```

(We’ll expand this to the whole repo in a later ticket.)

## 3) Re-run the green-light checklist (only the items affected)

1. **Static scan critical files** — must be clean (above).
2. **Schema integrity** (both DBs):

```bash
python scripts/verify_schema_integrity.py path/to/podcast_monitor.db --strict
python scripts/verify_schema_integrity.py path/to/youtube_transcripts.db --strict
```

Expect: `foreign_keys=1`, `foreign_key_check` empty, required indexes/uniques present, zero orphans.

3. **Functional double-run** (proves Phase 4 features under enforced FKs):

* Run ingestion **twice** back-to-back on a test copy:

  * 2nd run shows **304** via ETag/Last-Modified,
  * no duplicate processing (dedupe holds),
  * “2-line per feed” INFO logs,
  * stale/no-date warnings are suppressed after the first appearance.

4. **Drop-and-recreate guard** (you already passed this—no need to repeat unless the changes touched DDL paths).

5. **Startup preflight logs** confirm: `user_version=2`, `journal_mode=WAL`, `foreign_keys=1`.

## 4) Acceptance to move on

* The three critical files are factory-only ✔
* Integrity scripts pass on both DBs ✔
* Functional double-run behaves as expected ✔
* CI gate passes ✔

Once these are all green, you can confidently call **Phase 4 complete** and move to Phase 5.
(Then open a follow-up ticket to replace direct connections in the remaining non-critical files and to widen the CI block beyond these three files.)

---

If you want, I can also generate a tiny patch bundle (unified diffs) for those three files so Claude can apply them verbatim.
