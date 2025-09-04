#!/bin/bash
# Production Cron Job Setup for Daily Tech Digest Pipeline

echo "Setting up Daily Tech Digest Pipeline cron job..."

# Create log directory
mkdir -p logs

# Add cron job for daily execution at 6 AM
CRON_JOB="0 6 * * * cd /Users/paulbrown/Desktop/podcast-scraper && python3 daily_podcast_pipeline.py --run >> logs/pipeline.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "daily_podcast_pipeline.py"; then
    echo "✅ Cron job already exists"
else
    # Add the cron job
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✅ Cron job added: Daily execution at 6 AM"
fi

echo "📅 Current cron jobs:"
crontab -l | grep -E "(daily_podcast|podcast_scraper)" || echo "No podcast-related cron jobs found"

echo ""
echo "🚀 Production Setup Complete"
echo "📋 To manually run: python3 daily_podcast_pipeline.py --run"
echo "📊 To check status: python3 daily_podcast_pipeline.py --status"
echo "📝 Logs will be saved to: logs/pipeline.log"