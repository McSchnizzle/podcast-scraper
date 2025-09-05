# Verification Plan for Podcast Scraper Fixes

## 1) Database hygiene
- List failed items:
```sql
SELECT episode_id, title, fail_reason FROM rss_episodes WHERE status='failed';
```
- Reset them:
```sql
UPDATE rss_episodes SET status='pending', fail_reason=NULL WHERE status='failed';
```

---

## 2) Run pipeline with defaults (quiet)
- Expect: few dozen lines total.
- No per-item SKIP logs.
- One INFO summary per feed.
- One line per file for ASR.
- Post-transcription scoring shows RSS≥1.

---

## 3) Confirm scoring after transcription
- Check DB: newly transcribed episode should have non-NULL `score`, `topic`, and eligible status.

---

## 4) Digest generation
- Expect digest artifacts (md/mp3).
- RSS updated.

---

## 5) Logging volume check
- Total `run.log` < ~5,000 lines.
- Console < ~200 lines.
- With `LOG_VERBOSE=1`, detailed logs appear.

---

## 6) Feed crawl efficiency
- Vergecast summary shows older-than-cutoff count and early break engaged.
- No per-item spam.

---

## 7) Repo size
- `.gitignore` working.
- Heavy files removed from git.
- Run `git count-objects -vH` before/after to confirm shrinkage.

---
