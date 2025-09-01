# Incomplete / Misaligned Items – Multi-Topic Digest Refactor

This document lists the remaining gaps found in the feature branch that must be fixed to complete the refactor.

---

## 1) Digest selection logic is not using relevance scores
- Current: `openai_digest_integration.py` queries by `digest_topic`, but no code ever sets this field.
- Effect: No episodes will be selected for digest generation.
- Fix:
  - Query by `topic_relevance_json` scores (≥ threshold).
  - After digest creation, stamp included episodes:
    ```sql
    UPDATE episodes
    SET digest_topic = ?, digest_date = ?
    WHERE id IN ( ... )
    ```

## 2) Weekly & Monday catch-up logic missing
- Current: Pipeline does not branch behavior by weekday.
- Needed:
  - **Friday**: Normal dailies + weekly digests (7-day window, quotes).
  - **Monday**: Catch-up digests covering Fri 06:00 → Mon run.

## 3) RSS & Deployment assume single MP3
- Current: `rss_generator.py` and `deploy_episode.py` look for `complete_topic_digest_*.mp3`.
- Needed:
  - Discover all per-topic MP3s (`{topic}_digest_{timestamp}.mp3`).
  - Emit one RSS item per MP3.
  - Deploy all MP3s created in the run.

## 4) Per-topic instructions are not file-based
- Current: Prompts are embedded in code.
- Needed:
  - `digest_instructions/<topic>.md` for each topic.
  - `topics.json` with thresholds, TTS voice, music prompts.
  - Code should read these at runtime.

## 5) Music integration missing
- Current: TTS only.
- Needed:
  - Eleven Music generation (or static intro/outro/bed files).
  - ffmpeg mix: intro → narration+bed → outro.
  - Cache per topic.

## 6) Retention config inconsistent
- Current: `retention_cleanup.py` enforces 14 days, but `daily_podcast_pipeline.py` still has `RETENTION_DAYS = 7`.
- Fix: Remove or align the constant to avoid confusion.

## 7) Feed topics still exposed in CLI
- Current: `manage_feeds.py` and `config.py` still prompt/use `topic_category`.
- Needed: Selection must be 100% score-based.
- Optional: Mark feed categories as informational only, or remove prompts.

---
