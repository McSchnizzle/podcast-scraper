#!/bin/bash
# YouTube Cron Job Log Checker
# Shows the most recent YouTube processing logs

LOG_DIR="$HOME/Library/Logs/podcast-scraper"

echo "🔍 YouTube Cron Job Log Checker"
echo "=================================="

# Check if log directory exists
if [[ ! -d "$LOG_DIR" ]]; then
    echo "❌ Log directory not found: $LOG_DIR"
    exit 1
fi

# Find recent YouTube logs
echo "📁 Checking logs in: $LOG_DIR"
echo

# Show last 3 YouTube cron job logs
echo "📊 Recent YouTube cron job runs:"
ls -la "$LOG_DIR"/youtube_cron_*.log 2>/dev/null | tail -3 | while read -r line; do
    echo "  $line"
done

echo

# Show the most recent log content
LATEST_LOG=$(ls -t "$LOG_DIR"/youtube_cron_*.log 2>/dev/null | head -1)

if [[ -n "$LATEST_LOG" ]]; then
    echo "📝 Latest YouTube cron log: $(basename "$LATEST_LOG")"
    echo "=========================================="
    tail -50 "$LATEST_LOG"
else
    echo "❌ No YouTube cron logs found"
    echo
    echo "💡 Expected log pattern: youtube_cron_YYYYMMDD_HHMMSS.log"
    echo "📁 Log directory: $LOG_DIR"
    echo
    echo "📋 All logs in directory:"
    ls -la "$LOG_DIR"/*.log 2>/dev/null || echo "  (no .log files found)"
fi

echo
echo "✅ Log check complete"
