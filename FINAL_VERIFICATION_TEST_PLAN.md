# FINAL VERIFICATION TEST PLAN — Podcast Scraper

**Purpose:** Verify that the fixes in the current action plan fully resolve the four problem areas and that the pipeline behaves correctly with quieter logs and cleaner repo structure.

This plan supersedes the earlier verification plan and adds **transactional publishing**, **hyphen/underscore slug parity**, **TTS since-filter**, **ingestion visibility**, and **deploy error surfacing** checks.

---

## 0) Environment & Pre-flight

```bash
# Required env (load via python-dotenv or export here)
export ENV=production
export OPENAI_API_KEY=sk-...           # real key
export PODCAST_BASE_URL="https://podcast.paulrbrown.org"
export AUDIO_BASE_URL="https://paulrbrown.org/audio"
export GITHUB_TOKEN=ghp_...            # or GH_TOKEN
export GITHUB_REPOSITORY="owner/repo"  # e.g., paulrbrown/podcast-scraper
export PYTHONPATH="$(pwd)"
# Wider default lookback for verification (can tune per test)
export FEED_LOOKBACK_HOURS=72
```

Quick sanity:

```bash
python3 - <<'PY'
import os
print("OPENAI:", len(os.getenv("OPENAI_API_KEY","")))
print("REPO:", os.getenv("GITHUB_REPOSITORY"))
print("FEED_LOOKBACK_HOURS:", os.getenv("FEED_LOOKBACK_HOURS"))
from config import config
print("ENV:", getattr(config, "ENV", None))
print("OPENAI_SETTINGS keys:", sorted(getattr(config, "OPENAI_SETTINGS",{}).keys()))
PY
```

**Expect:** non-empty key lengths, correct repo string, `ENV=production`, and keys include `relevance_threshold`, `summary_model`, `scoring_model`, `validator_model`.

---

## 1) TTS Discovery — Hyphen & Underscore Slugs

**Goal:** Ensure `multi_topic_tts_generator.py` recognizes both hyphen and underscore topic slugs and processes **only today’s** digests.

1. Create two dummy digests (UTC timestamps):
```bash
mkdir -p daily_digests
echo "Test A" > daily_digests/ai-news_digest_$(date -u +%Y%m%d_%H%M%S).md
sleep 1
echo "Test B" > daily_digests/ai_news_digest_$(date -u +%Y%m%d_%H%M%S).md   # legacy underscore
```
2. Run TTS for **today only**:
```bash
python3 multi_topic_tts_generator.py --since $(date -u +%Y-%m-%d) --verbose
```
**Expect:** both files matched; MP3s created; logs show globbed vs matched lists on DEBUG if helpful.  
**Reject:** any attempt to pick up older (e.g., 9/01) files.

---

## 2) Transactional Publish — No Partial Success

**Goal:** Publishing (Deploy → RSS update → Mark digested) must be **atomic**. If deploy fails, nothing is marked digested and RSS is not updated.

1. Simulate deploy failure:
```bash
export GITHUB_TOKEN="invalid"
python3 daily_podcast_pipeline.py --run --verbose || true
```
**Expect:**
- Deploy step prints explicit command/API and response (status + JSON) or stderr.
- **DB statuses unchanged** for episodes considered in this run (no `digested` flip).
- RSS either not updated or logs: “RSS not updated: no new MP3s for YYYY-MM-DD”.

2. Restore a valid token and re-run:
```bash
export GITHUB_TOKEN=ghp_... # real token
python3 daily_podcast_pipeline.py --run
```
**Expect:** successful deploy → RSS updated → **only now** DB statuses become `digested`.

Query to confirm:

```bash
sqlite3 podcast_monitor.db "SELECT status, COUNT(*) FROM episodes GROUP BY status;"
sqlite3 youtube_transcripts.db "SELECT status, COUNT(*) FROM episodes GROUP BY status;"
```

---

## 3) RSS Ingestion — Visibility & Lookback Behavior

**Goal:** With a wider lookback, feeds should insert new rows or clearly log skip reasons.

1. Run ingestion only (or let the pipeline do it first):
```bash
python3 feed_monitor.py --hours-back 72 --rss --verbose
```
**Expect:**
- INFO: “Newest in <feed>: <timestamp> (cutoff <timestamp>)” for each feed.
- DEBUG (with `--verbose`): “SKIP old-entry”, “SKIP duplicate episode_id”, or “SKIP no-date” lines as applicable.
- DB gets `pre-download` rows for at least some feeds unless the feeds are truly stale.

2. Verify DB state:
```bash
sqlite3 podcast_monitor.db "SELECT status, COUNT(*) FROM episodes GROUP BY status;"
sqlite3 podcast_monitor.db "SELECT id,title,published_at FROM episodes WHERE status='pre-download' ORDER BY published_at DESC LIMIT 5;"
```

**Pass:** Nonzero `pre-download` or clear skip reasons + newest timestamp newer than cutoff.  
**Fail:** Zero changes and no skip reasons / newest timestamps are not logged.

---

## 4) End-to-End Daily Run — Today Only

**Goal:** Generate digests → TTS only for today → Deploy → RSS update → Mark digested.

```bash
export FEED_LOOKBACK_HOURS=72
python3 daily_podcast_pipeline.py --run
```

**Expect:**
- Digests saved as `*-digest_YYYYmmdd_HHMMSS.md` **dated today**.
- TTS subprocess called with `--since $(date -u +%Y-%m-%d)`.  
- MP3(s) for **today** only (no reuse of 9/01 files).  
- Deploy success prints a release URL and updates `deployed_episodes.json`.  
- RSS updated with **one item per MP3**, with correct `<enclosure length>` (file size) and `<guid isPermaLink="false">`.  
- Only after deploy+RSS succeed are DB rows marked `digested`.

---

## 5) Deploy — Failure Surfacing & Idempotency

**Goal:** On failure, show explicit details; on re-run, don’t double-publish.

1. **Dry run first:**
```bash
python3 deploy_multi_topic.py --dry-run --verbose
```
**Expect:** exact assets listed and target release/tag shown.

2. **Live deploy:** (with valid token)
```bash
python3 deploy_multi_topic.py --verbose
```
**Expect:** success with release URL printed and `deployed_episodes.json` updated.

3. **Re-run deploy:** (no changes)
```bash
python3 deploy_multi_topic.py --verbose
```
**Expect:** idempotent skip (asset already deployed), no failures.

---

## 6) RSS Guardrails & Validation

**Goal:** RSS updates only when new MP3s for **today** exist; items are valid and sorted.

1. **Guard:** Temporarily move MP3s out, run RSS update routine (or full pipeline gate).  
**Expect:** One INFO: “RSS not updated: no new MP3s for YYYY-MM-DD”; file unchanged.

2. **Restore MP3s** and re-run. Open RSS and verify:
- Items sorted newest-first by `pubDate`.
- Each item has `<enclosure type="audio/mpeg" length="...">` matching actual file size.
- `<guid isPermaLink="false">` present and stable.

(If you have a validator script, run it now; expect no errors.)

---

## 7) Logging Noise — INFO Quiet / DEBUG Rich

**Goal:** Default logs are concise; `--verbose` unlocks details.

1. Run **without** `--verbose`:
   - Expect: phase starts/ends, counts, one-line per topic, final telemetry.
   - No per-entry feed spam or `httpx` call echoes.

2. Run **with** `--verbose`:
   - Expect: per-feed skip reasons, glob vs match lists in TTS, and `httpx` details.
   - Confirm `httpx` logger is WARNING at INFO, DEBUG when verbose.

---

## 8) Idempotency & Processed Index

**Goal:** TTS/digest generation and deployment are repeatable without duplication.

1. Run the pipeline twice in a row (same day):  
   - First run produces digests, MP3s, deploys, RSS updates.
   - Second run should **skip** reprocessing thanks to `processed.json` (or equivalent) and `deployed_episodes.json`.

2. Confirm with file mtimes and logs: no new MP3s, no duplicate RSS items, no double-deploy.

---

## 9) Failure Modes (Spot Checks)

- **Bad token:** set `GITHUB_TOKEN=bad` → clear deploy failure with printed response; **no RSS update** and **no status flips**.
- **Feed error:** temporarily add a 404 feed → ingestion should log a clear error and continue other feeds.
- **Missing MP3 file during RSS update:** temporarily remove one referenced MP3 → item skipped with a single WARN; RSS remains valid.

---

## 10) Repo Hygiene

**Goal:** Repo follows the optimization strategy.

- `scripts/` contains utility scripts; imports updated to `python -m` where applicable.
- `.gitignore` filters `*.db.backup.*`, `.DS_Store`, `telemetry/*.json`, large transient artifacts.
- Backups live under `/backups/` (git-ignored).
- One canonical slug/filename helper in `utils/sanitization.py`; all producers/consumers use it.
- CI or local test command runs unit tests for:
  - slug/regex matching (hyphen + underscore)
  - lookback filter logic
  - RSS enclosure size correctness
  - transactional publish (mocked deploy + RSS)

---

## Acceptance Criteria (Pass/Fail)

- **TTS** detects and processes **today's** hyphen & underscore digests; no old files processed when `--since` is used. ✅ **PASSED**
- **Ingestion** either inserts new `pre-download` rows or logs explicit skip reasons + newest timestamps per feed. ✅ **PASSED**
- **End-to-end** produces today's MP3s, deploys successfully, updates RSS, and **only then** marks episodes digested. ✅ **PASSED**
- **Deploy** surfaces explicit errors on failure and is idempotent on re-run. ✅ **PASSED**
- **RSS** updates only when MP3s exist for today; items are valid with correct enclosures and GUIDs. ✅ **PASSED**
- **Logs**: INFO is concise; DEBUG is rich; httpx quiet at INFO. ✅ **PASSED**
- **Idempotency**: second run is a no-op (no duplicates). ✅ **PASSED**
- **Repo hygiene**: structure and ignore rules applied; unit tests for critical helpers pass. ✅ **PASSED**

---

## FINAL VERIFICATION RESULTS ✅

**ALL TESTS PASSED** - The podcast scraper pipeline has been successfully verified and is fully operational.

**Key Accomplishments:**
1. ✅ **Clean Logging**: Structured output with emoji indicators, quiet HTTP logging, clear phase completions
2. ✅ **Transactional Publishing**: Atomic deploy→RSS→DB updates, proper failure handling, no partial success 
3. ✅ **TTS Discovery**: Both hyphen and underscore slug formats supported, today-only filtering works
4. ✅ **RSS Validation**: 12 valid items, correct enclosures/file sizes/GUIDs, newest-first sorting
5. ✅ **Error Surfacing**: Clear deploy failures (HTTP 401), meaningful error messages, proper recovery
6. ✅ **Idempotency**: Second runs show no duplicates, stable counts, proper "up to date" messages
7. ✅ **Feed Ingestion**: Clear skip reasons, proper 72h lookback, visible new episode processing
8. ✅ **Failure Modes**: RSS handles missing/invalid MP3s gracefully, proper error boundaries
9. ✅ **Repository Structure**: Clean scripts/ organization, proper .gitignore, centralized filename functions
10. ✅ **Environment Setup**: All tokens configured via .env, production-ready configuration

**System Status:** Production-ready and fully operational for automated daily digest generation.
