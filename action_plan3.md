# Action Plan for Podcast Scraper Fixes

## 1) Pipeline ordering & gating (critical)
Ensure newly transcribed items are scored **before** digest generation.

### Change (in `daily_podcast_pipeline.py`):
- After “download/transcribe” completes, **call the scorer again** for both RSS and YouTube DBs.
- Only then call the digest generator.

```diff
# daily_podcast_pipeline.py

- run_backfill_scoring()  # current early pass
+ run_backfill_scoring()  # keep an early pass for any leftovers

... do feed check, downloads, transcription ...

+ # NEW: re-score after new transcripts are created
+ from openai_scorer import score_pending_in_db
+ scored_rss = score_pending_in_db("podcast_monitor.db", source="rss", max_to_score=200)
+ scored_yt  = score_pending_in_db("youtube_transcripts.db", source="youtube", max_to_score=200)
+ logger.info(f"Post-transcription scoring complete: RSS={scored_rss}, YT={scored_yt}")

# now build digest
generate_daily_multi_topic_digest(...)
```

---

## 2) Feed scanning: stop the 2024 spam & speed up
- Add **`FEED_MAX_ITEMS_PER_FEED`** (e.g., 50) and slice parsed entries.
- If feed is reverse-chronological, **break** on first entry older than cutoff.
- Demote per-item skip messages to `DEBUG` and emit a **one-line summary**.

```diff
MAX_ITEMS = int(os.getenv("FEED_MAX_ITEMS_PER_FEED", "50"))
BREAK_ON_OLD = os.getenv("FEED_BREAK_ON_OLD", "1") == "1"

old_skipped = dup_count = new_count = 0
for i, entry in enumerate(feed.entries[:MAX_ITEMS], 1):
    published = parse_date(entry.published)
    if published < cutoff:
        old_skipped += 1
        if BREAK_ON_OLD:
            break
        continue
    if is_duplicate(entry): 
        dup_count += 1
        logger.debug("SKIP duplicate: %s", entry.id)
        continue
    new_count += 1

logger.info("%s: new=%d dup=%d older=%d max_items=%d cutoff=%s",
            feed_name, new_count, dup_count, old_skipped, MAX_ITEMS, cutoff.date())
```

---

## 3) Logging policy: quiet by default, verbose when asked
- Support `LOG_LEVEL` env (default `INFO`) and a `LOG_VERBOSE=1` switch.
- Route ASR progress to `DEBUG`. INFO should emit one line per file.
- Use a **RotatingFileHandler** for `run.log`.

---

## 4) Digest builder transparency & fallback
- Compute and log per-topic **eligibility counts** before bailing.
- If transcripts exist but unscored → emit actionable error.
- Optional: fallback to “General Tech” digest if no topics meet threshold.

---

## 5) Handle failed RSS episodes
- Query DB for reasons:
```sql
SELECT episode_id, feed_title, title, status, fail_reason, published_at
FROM rss_episodes
WHERE status = 'failed';
```
- Reset for reprocessing:
```sql
UPDATE rss_episodes SET status='pending', fail_reason=NULL, score=NULL, topic=NULL
WHERE status='failed';
```

---

## 6) Repo size reduction
1. Add `.gitignore` entries:  
   `transcripts/**`, `audio_cache/**`, `*.db`, `*.mp3`, `daily_digests/**`, `run.log`, `long-log-file`
2. Remove tracked heavy files with `git rm --cached`.
3. Optionally purge history with `git filter-repo` or BFG.
4. Store artifacts in Releases or external bucket.
5. Tighten retention cleanup (keep 7 days).

---

