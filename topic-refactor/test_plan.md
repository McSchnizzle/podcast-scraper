# End-to-End Test Plan — Multi-Topic Digest Refactor
**Last updated:** 2025-09-01 19:51 UTC

This document describes how to **locally** and **via GitHub Actions** test the refactored multi-topic digest pipeline. It biases toward **2 YouTube episodes** and **1 RSS episode** so that only **one** audio file needs real-time transcription and the others can use existing transcripts.

---

## 0) Pre-Reqs & Assumptions
- You have the **final refactor branch** checked out locally.
- You have working API keys:
  - `OPENAI_API_KEY` (scoring + digest generation)
  - `ELEVENLABS_API_KEY` (TTS)
  - (Optional) Eleven **Music** API if you’re generating intro/outro/bed dynamically
- Databases:
  - `podcast_monitor.db` — RSS-side episodes (used by GH Actions too)
  - `youtube_transcripts.db` — YouTube episodes (local machine)
- Topic config + instructions exist:
  - `topics.json` with at least **two topics** (e.g., `ai`, `tech_culture`) and thresholds.
  - `digest_instructions/ai.md`, `digest_instructions/tech_culture.md` (prose-only guidance included).
- TTS voices mapped for those topics (either in code or `topics.json`).
- The pipeline supports **prose-only validation** (bullets/numbered lists are rejected/re-written).
- The pipeline will **stamp** episodes included in a digest with `digest_topic` and `digest_date`.

---

## 1) Safety: Backup Databases
Before pruning for tests, **backup** both DBs.

```bash
cp podcast_monitor.db podcast_monitor.backup.$(date +%F).db
cp youtube_transcripts.db youtube_transcripts.backup.$(date +%F).db
```

To **restore** later:
```bash
cp podcast_monitor.backup.YYYY-MM-DD.db podcast_monitor.db
cp youtube_transcripts.backup.YYYY-MM-DD.db youtube_transcripts.db
```

---

## 2) Prepare Minimal Test Data (2 YouTube + 1 RSS)
We’ll keep **2 YouTube episodes** and **1 RSS episode** in a **transcribed** state, and remove/disable everything else so the pipeline runs the full flow quickly.

> Adjust table/column names if your schema differs. Use `sqlite3` CLI from project root.

### 2.1 Identify target episode IDs
Open each DB and list recent episodes:

```bash
sqlite3 youtube_transcripts.db "
.headers on
.mode column
SELECT id, title, status, published_date FROM episodes ORDER BY published_date DESC LIMIT 10;
"

sqlite3 podcast_monitor.db "
.headers on
.mode column
SELECT id, title, status, published_date FROM episodes ORDER BY published_date DESC LIMIT 10;
"
```

Choose:
- **YouTube**: 2 episode `id`s to **keep**
- **RSS**: 1 episode `id` to **keep**

### 2.2 Prune other episodes (soft delete / disable)
> Option A (recommended): **Disable** all other episodes by setting `status='archived'` so they’re ignored by the pipeline.

```bash
# YOUTUBE: disable all except 2 chosen IDs
sqlite3 youtube_transcripts.db "
UPDATE episodes SET status='archived'
WHERE id NOT IN ('YID_1','YID_2');
"

# RSS: disable all except 1 chosen ID
sqlite3 podcast_monitor.db "
UPDATE episodes SET status='archived'
WHERE id NOT IN ('RID_1');
"
```

> Option B: **Delete** other episodes entirely (only if you’re comfortable with data loss)
```bash
sqlite3 youtube_transcripts.db "
DELETE FROM episodes WHERE id NOT IN ('YID_1','YID_2');
"
sqlite3 podcast_monitor.db "
DELETE FROM episodes WHERE id NOT IN ('RID_1');
"
```

### 2.3 Ensure minimal episodes are **transcribed** (so only 1 needs real-time transcription)
Set **two** episodes as `transcribed` with valid `transcript_path` and **one** episode as `downloaded` (so it will transcribe now).

```bash
# Example: set states for YouTube
sqlite3 youtube_transcripts.db "
UPDATE episodes SET status='transcribed', transcript_path='transcripts/Y1.txt'
WHERE id='YID_1';
UPDATE episodes SET status='transcribed', transcript_path='transcripts/Y2.txt'
WHERE id='YID_2';
"

# Example: set one RSS episode to downloaded (will be transcribed real-time)
sqlite3 podcast_monitor.db "
UPDATE episodes SET status='downloaded', transcript_path=NULL
WHERE id='RID_1';
"
```

> If you don’t have transcript files for the two pre-transcribed episodes, you can copy any short text files into `transcripts/` and point `transcript_path` to them for testing.

### 2.4 Clear digest stamps for a clean run
```bash
sqlite3 youtube_transcripts.db "
UPDATE episodes SET digest_topic=NULL, digest_date=NULL;
"
sqlite3 podcast_monitor.db "
UPDATE episodes SET digest_topic=NULL, digest_date=NULL;
"
```

---

## 3) Local Test (Daily Run)
### 3.1 Set environment
```bash
export OPENAI_API_KEY=sk-...
export ELEVENLABS_API_KEY=...
# optional music config, if in use
export ELEVEN_MUSIC_API_KEY=...
```

### 3.2 Run pipeline
```bash
python3 daily_podcast_pipeline.py --log-level=INFO
```

**Expected:**  
- The **downloaded** RSS episode is transcribed.  
- All 3 episodes get **topic relevance scores** (`topic_relevance_json`, `scores_version`).  
- For each topic:
  - Episodes with `score ≥ relevance_threshold_daily` are included.
  - A **prose-only** digest text is generated. If bullets are detected, the validator rewrites it.
  - TTS is generated; per-topic MP3 is produced (e.g., `daily_digests/ai/2025-09-01_ai_daily.mp3`).  
  - Each included episode is stamped with `digest_topic` + `digest_date`.

### 3.3 Verify DB and outputs
```bash
# Check digests stamped
sqlite3 youtube_transcripts.db "
.headers on
.mode column
SELECT id, digest_topic, digest_date FROM episodes WHERE digest_date IS NOT NULL ORDER BY digest_date DESC;
"

sqlite3 podcast_monitor.db "
.headers on
.mode column
SELECT id, digest_topic, digest_date FROM episodes WHERE digest_date IS NOT NULL ORDER BY digest_date DESC;
"

# List outputs
ls -1 daily_digests/*/*_daily.mp3 || true
ls -1 daily_digests/*/*_daily.txt || true  # if you save text alongside
```

### 3.4 Validate RSS
```bash
python3 rss_generator.py  # or your wrapper
# Open generated RSS in a podcast app or a validator (e.g., https://podba.se/validate/)
```

---

## 4) Local Test (Friday Weekly + Monday Catch-Up)
### 4.1 Simulate a Friday run
Set your system date or pass a flag/env so the pipeline treats today as Friday. Alternatively, temporarily force the code path with a test parameter (e.g., `--force-weekly`):

```bash
python3 daily_podcast_pipeline.py --force-weekly
```

**Expected:**  
- Normal daily digests **plus** a **weekly** digest per topic.
- Weekly digest includes key quotes from episodes with `digest_date` in the last 7 days.
- Weekly files named like: `daily_digests/ai/2025-09-05_ai_weekly.mp3`.

### 4.2 Simulate a Monday catch-up
Either tweak system date or add a flag (e.g., `--force-monday-catchup`):
```bash
python3 daily_podcast_pipeline.py --force-monday-catchup
```
**Expected:**  
- Daily digests cover **Friday 06:00 → now**.

---

## 5) GitHub Actions Test
### 5.1 Prepare branch & secrets
- Push the feature branch to GitHub.
- In repo **Settings → Secrets and variables → Actions**, set:
  - `OPENAI_API_KEY`
  - `ELEVENLABS_API_KEY`
  - (Optional) `ELEVEN_MUSIC_API_KEY`
- Confirm workflow at `.github/workflows/daily-podcast-pipeline.yml` uses `cron: "0 6 * * 1-5"`.

### 5.2 Prepare minimal data on GH runner
Because the runner uses `podcast_monitor.db` (RSS side), ensure a minimal test scenario exists there (1 RSS episode):

Option A (preferred): Commit a **seeded DB** (small dev copy) under a path your workflow expects (if allowed).  
Option B: Add a workflow step to **prune** the DB on-run (use `sqlite3` commands from §2.2–2.4).

For YouTube (2 episodes), you can run the **YouTube processing locally** and then copy the minimal `transcripts/` outputs into the repo (if the workflow reads local transcripts), or you can modify the GH workflow to operate against a prepared `youtube_transcripts.db` artifact you upload as a workflow input.

> Keep in mind: GH runner is stateless; for a deterministic test, plan how the DB/transcripts land on the runner.

### 5.3 Dispatch workflow manually
In GitHub: **Actions → Daily Podcast Pipeline → Run workflow** (or wait for cron). Provide inputs/flags if your workflow supports **force-weekly** or **force-monday-catchup**.

### 5.4 Verify logs and artifacts
- Review job logs for:
  - Transcription (for the 1 RSS episode)
  - Scoring → selection (scores ≥ thresholds)
  - Prose validation / rewrites (if needed)
  - TTS MP3 creation for each topic
  - RSS update and/or GitHub Release upload
- Check uploaded artifacts (per-topic MP3s) and final RSS.

---

## 6) Troubleshooting Checklist
- **No episodes in digest** → Likely selection is still filtering by `digest_topic`. Switch to score-based selection and stamp after success.
- **Bullets in TTS** → Validator not called or rewrite failed. Ensure validator runs **before** TTS; if rewrite fails twice, fail the digest.
- **Weekly missing** → Friday code path not executed; add a flag or weekday branching.
- **Monday catch-up not widening window** → Ensure window calc is Fri 06:00 → now.
- **RSS shows only one item** → RSS generator still expects a single `complete_topic` artifact. Update to enumerate all per-topic MP3s from the current run.
- **Missing voices/music** → Check `topics.json` mapping and that the TTS/music env vars are set on runner and locally.
- **Retention not running** → Confirm the `_cleanup_old_files()` call executes at the end of the pipeline (and logs deletions).

---

## 7) Post-Test: Restore DBs (Optional)
If you used backups:
```bash
cp podcast_monitor.backup.YYYY-MM-DD.db podcast_monitor.db
cp youtube_transcripts.backup.YYYY-MM-DD.db youtube_transcripts.db
```

---

## 8) Success Criteria (Pass/Fail)
- **Daily local run** produces **two** topic MP3s (if both topics have ≥1 episode over threshold) and stamps episodes with `digest_topic` + `digest_date`.
- **Friday weekly** produces a weekly MP3 per topic (quotes included).
- **Monday catch-up** includes Fri 06:00 → Mon episodes.
- **RSS** contains **one item per digest** (daily + weekly) with correct titles.
- **TTS** inputs are validated as prose only (no bullets).
- **Retention** deletes transcripts older than 14 days (log evidence).
