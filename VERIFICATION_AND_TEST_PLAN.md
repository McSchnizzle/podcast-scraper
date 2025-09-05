
# Verification & Test Plan — Post‑Fix Validation
Owner: Coding Agent • Reviewer: Paul • Date: 2025‑09‑05

> This plan validates fixes across local macOS and GitHub Actions, including GPT‑5 digests, ingestion, TTS, and RSS.

---

## Pre‑flight
- [ ] `git pull && pip install -r requirements.txt`
- [ ] Ensure `.env` has:
  - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`
  - `SCORER_MODEL=gpt-5-mini`
  - `SCORER_MAX_COMPLETION_TOKENS=700`
  - `SCORER_REASONING_EFFORT=minimal`
  - `RELEVANCE_THRESHOLD=0.65`
  - `FEED_LOOKBACK_HOURS=48`
  - `PODCAST_BASE_URL`, `AUDIO_BASE_URL`
- [ ] Confirm **UTC** is used: `python -c "from utils.datetime_utils import now_utc; print(now_utc())"`

---

## Test 1 — Datetime/Timezone
**Local & CI**

- [ ] Run `python - <<'PY'
from utils.datetime_utils import now_utc; print('UTC:',now_utc())
PY`
- [ ] Run feed check dry‑run: `python feed_monitor.py --dry-run --limit 10 --verbose`
  - Expect: no “offset‑naive vs aware” errors; if a feed has zero dates, see one INFO line: `no dated entries`.
- [ ] In CI, verify no `pytz` ImportError.

**Pass if:** no tz errors; lookback cutoff printed with `Z UTC` once per run.

---

## Test 2 — GPT‑5 Scoring & Summary (Unit Smoke)
**Local**

- [ ] `python - <<'PY'
from openai import OpenAI; import json
c=OpenAI(); schema={"name":"Scores","strict":True,"schema":{"type":"object","properties":{"AI News":{"type":"number"}},"required":["AI News"],"additionalProperties":False}}
r=c.responses.create(model="gpt-5-mini", input=[{"role":"user","content":"Score AI relevance 0..1 for: NVIDIA Blackwell"}], response_format={"type":"json_schema","json_schema":schema}, max_completion_tokens=60, reasoning={"effort":"minimal"}); print('OK:', r.output_text)
PY`
- [ ] Run scorer against a short transcript fixture: `python openai_scorer.py --file tests/fixtures/short.txt`
  - Expect valid JSON, no temperature/max_tokens errors.

**Pass if:** both commands return JSON and no HTTP 400.

---

## Test 3 — End‑to‑End Daily Digest (Local)
- [ ] Prepare: ensure at least 2 **transcribed** episodes exist (one RSS, one YouTube) within lookback.
- [ ] Run: `python daily_podcast_pipeline.py --run --verbose`
- [ ] Expect:
  - Backfill OK, feed scan OK.
  - `EpisodeSummaryGenerator` uses `gpt-5-mini` and **no temperature** errors.
  - At least one topic digest saved: `daily_digests/<topic>_digest_YYYYMMDD_HHMMSS.md` + `.json`.

**Pass if:** ≥1 topic digest created without 400 errors.

---

## Test 4 — TTS Generation Scoping
- [ ] Run TTS for **today only**: `python multi_topic_tts_generator.py --since $(date -u +%Y%m%d)`
- [ ] Expect: MP3s for **today’s** digests only; logs say `✅ No new digests today` if none.
- [ ] Verify files: `ls -l daily_digests/*_$(date -u +%Y%m%d)_*.mp3`

**Pass if:** MP3s exist for each digest created in Test 3.

---

## Test 5 — RSS Update
- [ ] Run: `python rss_generator_multi_topic.py --update`
- [ ] Expect: “RSS updated” **only** if new MP3s exist for today.
- [ ] Validate feed:
  - `xmllint --noout daily-digest-production.xml`
  - Check items: GUID stability, `enclosure` `length` and `type`, pubDate in UTC, count matches created MP3s.

**Pass if:** XML valid; items correspond 1:1 to today’s MP3s.

---

## Test 6 — Retry Queue & Telemetry
- [ ] Simulate one scoring failure (set temp bad key or mock) and run `python daily_podcast_pipeline.py --retry-failed`.
- [ ] Expect: no `ImportError: OpenAIScorer`; telemetry `record_metric` present; failures recorded once.

**Pass if:** retry loop runs, logs a concise failure summary, and continues.

---

## Test 7 — Feed Edge Cases
- [ ] Pick feed with sparse dates; run `python feed_monitor.py --feeds "<name>" --limit 50`.
- [ ] Expect one informational line: `no dated entries (skipped)` and totals line.

**Pass if:** no exceptions; totals include `no_date` count.

---

## Test 8 — GitHub Actions Run
- [ ] Push branch `ci-verify`.
- [ ] Verify workflow output:
  - No `pytz` ImportError.
  - No “offset‑naive vs aware” errors.
  - Digest generation uses GPT‑5 (see EpisodeSummaryGenerator logs).
  - If digests created, TTS produces MP3s and RSS updates, otherwise clean skip.
  - Artifact `podcast-digest-*.zip` contains today’s new files.

**Pass if:** job completes successfully; artifact has expected files; logs concise.

---

## Test 9 — Weekly (Friday) Mode
- [ ] Trigger Friday mode locally: `FORCE_DAY=Friday python daily_podcast_pipeline.py --run`
- [ ] Expect: daily + weekly digests OR clean skip if transcripts unavailable.

**Pass if:** no special-case failures; RSS only updates if new weekly MP3 exists.

---

## Test 10 — Logging Policy
- [ ] Run daily pipeline **without** `--verbose`.
  - Expect ≤ ~150 lines; no per-file directory dumps.
- [ ] Run with `--verbose` to confirm DEBUG shows chunking details and per‑entry feed reasons.

**Pass if:** INFO logs are succinct; DEBUG shows detail as needed.
