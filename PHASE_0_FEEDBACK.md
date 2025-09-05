
# Phase 0 Feedback — Guardrails & Baseline (Single Document)

**Scope:** Feedback only for Phase 0 in `PHASED_REMEDIATION_TASKS.md` — make CI smoke fast/cost-safe, enforce UTC everywhere, tighten config validation, and quiet logs by default.

---

## 1) CI Smoke Script — deterministic, fast, and cost‑safe

Create `scripts/ci_smoke.sh` with strict bash and mocks to avoid real API cost/flake:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "❌ Smoke failed at line $LINENO"; exit 1' ERR

# CI flags: forbid networked API calls during smoke
export CI_SMOKE=1
export MOCK_OPENAI=1
export PYTHONUNBUFFERED=1

echo "▶ Python syntax compile check"
python - <<'PY'
import compileall, sys
ok = compileall.compile_dir('.', quiet=1)
sys.exit(0 if ok else 1)
PY

echo "▶ Import critical modules"
python - <<'PY'
import daily_podcast_pipeline, feed_monitor, rss_generator_multi_topic
print("ok: imports")
PY

echo "▶ Config validation (warn-only in smoke)"
python config_validator.py --all --warn-only

echo "▶ DB quick checks (if DBs exist)"
for db in podcast_monitor.db youtube_transcripts.db; do
  if [[ -f "$db" ]]; then
    sqlite3 "$db" "PRAGMA quick_check;"
    sqlite3 "$db" "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('episodes');"
  fi
done

echo "▶ Dry-run pipeline (must be time-boxed)"
python daily_podcast_pipeline.py --dry-run --timeout 120 || true

echo "✅ Smoke passed"
```

**Notes**
- The app should **honor** `CI_SMOKE=1`/`MOCK_OPENAI=1` to skip real OpenAI calls and use tiny fixtures.
- Keep the smoke run under **2 minutes**.
- In smoke, config validator should **warn** rather than fail; main pipeline will **fail** on critical.

---

## 2) UTC Everywhere — utilities and workflow env

Create `utils/datetime_utils.py` and replace all `datetime.utcnow()` / naive `datetime.now()` usage.

```python
# utils/datetime_utils.py
from datetime import datetime, timezone, timedelta

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def cutoff_utc(hours: int) -> datetime:
    return now_utc() - timedelta(hours=hours)
```

**GitHub workflow:** set environment and unbuffered output.

```yaml
# .github/workflows/daily-podcast-pipeline.yml
env:
  TZ: UTC
  PYTHONUNBUFFERED: "1"
```

If any code mutates `TZ` at runtime on Linux, call `time.tzset()` guarded with `hasattr(time, "tzset")`.

---

## 3) Config Validator — split critical vs optional

Enhance `config_validator.py` to support severity and `--warn-only`:

**Critical (fail job in main pipeline; warn in smoke):**
- `OPENAI_API_KEY`
- `PODCAST_BASE_URL`, `AUDIO_BASE_URL`
- DB paths writeable (e.g., `daily_digests/`, `transcripts/`)
- `ENV` in allowed set (`production`, etc.)

**Optional (warn):**
- `FEED_LOOKBACK_HOURS`
- Deploy token/env for GitHub
- Voice/music config

**Redaction:** When logging secrets, show only length or last 4 chars. Never print full keys.

---

## 4) Logging Defaults — idempotent setup, quiet noisy libs

Create `utils/logging_setup.py` and call it **once** at process start (main entry points; not in imported modules).

```python
# utils/logging_setup.py
import logging, os

def configure_logging():
    root = logging.getLogger()
    if getattr(root, "_configured", False):
        return  # idempotent
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(levelname)s:%(name)s:%(message)s")
    for noisy in ("httpx", "urllib3", "openai", "requests"):
        logging.getLogger(noisy).setLevel(os.getenv("HTTP_LOG_LEVEL", "WARNING"))
    root._configured = True
```

**CLI behavior**
- Default INFO; `--verbose` just sets `LOG_LEVEL=DEBUG`.
- Keep directory listings and per-entry feed logs at **DEBUG**.

---

## 5) GitHub Workflow Wiring — cheap smoke first, strict validator in main job

- Add a **smoke job** that runs on every push/PR (no TTS/deploy), uses `scripts/ci_smoke.sh` and pip cache.
- In the **main pipeline job**, run `config_validator.py --all` **without** `--warn-only` (fail on missing criticals) **before** heavy steps.

---

## 6) Define “dry‑run digest” precisely

Update the app to support `--dry-run` (no external costs) and document what it does:

- Ingest feeds (no audio download), compute UTC **cutoff** and candidate list.
- Skip transcription/ASR; use small fixtures for scoring/summarization when `MOCK_OPENAI=1`.
- Skip TTS, deploy, and RSS; instead write a compact JSON summary of “would-be” actions.
- Auto-timeout with `--timeout 120` to keep smoke fast.

---

## 7) Phase 0 Success Criteria (measurable)

- ⏱️ Smoke runtime **< 2 minutes**.
- 🕐 No timezone warnings; cutoff is printed in **UTC** once per run.
- 🧪 Config validator: **0 critical**, optional may WARN in smoke.
- 🔇 Default INFO log length **≤ ~120 lines** on a typical `--dry-run` daily run.
- 💸 No networked OpenAI calls during smoke (verified by `MOCK_OPENAI=1`).

---

## Quick Checklist for the Coding Agent

- [ ] Implement `utils/datetime_utils.py`; refactor all naive datetimes.
- [ ] Add `utils/logging_setup.py`; call it **once** in main entry points.
- [ ] Extend `config_validator.py` with severities and `--warn-only`.
- [ ] Implement `--dry-run` and `--timeout` in `daily_podcast_pipeline.py`.
- [ ] Honor `CI_SMOKE`/`MOCK_OPENAI` flags across scorer/summarizer.
- [ ] Create `scripts/ci_smoke.sh` exactly as above; mark executable.
- [ ] Update workflow with `TZ=UTC`, smoke job first, strict validator in main job.
- [ ] Verify INFO logs are concise; DEBUG has detail.
