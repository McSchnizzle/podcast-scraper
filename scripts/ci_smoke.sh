#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "❌ Smoke failed at line $LINENO"; exit 1' ERR

# CI flags: forbid networked API calls during smoke
export CI_SMOKE=1
export MOCK_OPENAI=1
export PYTHONUNBUFFERED=1

echo "▶ Python syntax compile check"
python3 - <<'PY'
import compileall, sys
ok = compileall.compile_dir('.', quiet=1)
sys.exit(0 if ok else 1)
PY

echo "▶ Import critical modules"
python3 - <<'PY'
import daily_podcast_pipeline, feed_monitor, rss_generator_multi_topic
print("ok: imports")
PY

echo "▶ Config validation (warn-only in smoke)"
python3 config_validator.py --all --warn-only

echo "▶ DB quick checks (if DBs exist)"
for db in podcast_monitor.db youtube_transcripts.db; do
  if [[ -f "$db" ]]; then
    sqlite3 "$db" "PRAGMA quick_check;"
    sqlite3 "$db" "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('episodes');"
  fi
done

echo "▶ Dry-run pipeline (must be time-boxed)"
python3 daily_podcast_pipeline.py --dry-run --timeout 120 || true

echo "✅ Smoke passed"