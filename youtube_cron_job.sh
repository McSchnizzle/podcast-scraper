#!/bin/bash
# YouTube Transcript Processing Cron Job
# Runs every 6 hours to process YouTube episodes from last 7 days

# Change to project directory
cd "/Users/paulbrown/Desktop/podcast-scraper"

# Set up logging
LOG_FILE="/Users/paulbrown/Desktop/podcast-scraper/logs/youtube_cron_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "/Users/paulbrown/Desktop/podcast-scraper/logs"

# Run YouTube processor with comprehensive logging
echo "=== YouTube Cron Job Started: $(date) ===" >> "$LOG_FILE"
echo "Project Directory: /Users/paulbrown/Desktop/podcast-scraper" >> "$LOG_FILE"
echo "Python Executable: /Library/Frameworks/Python.framework/Versions/3.13/bin/python3" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Process YouTube episodes from last 7 days (168 hours)
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 youtube_processor.py --process-new --hours-back 168 >> "$LOG_FILE" 2>&1

# Log completion
echo "" >> "$LOG_FILE"
echo "=== YouTube Cron Job Completed: $(date) ===" >> "$LOG_FILE"
echo "Exit Code: $?" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Keep only last 10 log files to prevent disk space issues (macOS compatible)
find "/Users/paulbrown/Desktop/podcast-scraper/logs" -name "youtube_cron_*.log" -type f | sort -r | tail -n +11 | xargs rm -f

# Optional: Send notification on failure (uncomment if needed)
# if [ $? -ne 0 ]; then
#     echo "YouTube transcript processing failed at $(date)" | mail -s "Podcast Scraper Alert" your-email@domain.com
# fi
