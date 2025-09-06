# Operations Runbook - Daily Podcast Digest

**Version:** 1.0  
**Updated:** 2025-09-06  

## Quick Status Check

```bash
# Check both databases
python3 -c "
import sqlite3
for db in ['podcast_monitor.db', 'youtube_transcripts.db']:
    try:
        conn = sqlite3.connect(db)
        count = conn.execute('SELECT COUNT(*) FROM episodes').fetchone()[0]
        print(f'{db}: {count} episodes')
        conn.close()
    except Exception as e:
        print(f'{db}: ERROR - {e}')
"

# Check YouTube watermark
cat state/yt_last_push.json | jq .

# Check recent backups
ls -la ~/.podcast-scraper-backups/ | head -5
```

## Daily Operations

### Morning Check (9 AM local)
1. **Verify CI ran successfully**:
   - Check GitHub Actions: https://github.com/McSchnizzle/podcast-scraper/actions
   - Look for green checkmarks on daily digest workflow

2. **Check RSS feed**:
   - Verify feed loads: https://podcast.paulrbrown.org/daily-digest.xml
   - Confirm latest episodes are present

3. **Review healthchecks** (if configured):
   - Check Healthchecks.io dashboard
   - Verify both YouTube and RSS pings are green

### Weekly Operations (Mondays)

1. **Backup verification**:
   ```bash
   ./scripts/backup_sqlite.sh restore-test
   ```

2. **Log cleanup**:
   ```bash
   # Logs auto-rotate, but check sizes
   du -sh ~/Library/Logs/podcast-scraper/
   ```

3. **Database health check**:
   ```bash
   python3 utils/db.py podcast_monitor.db
   python3 utils/db.py youtube_transcripts.db
   ```

## Troubleshooting Guide

### YouTube Cron Job Issues

**Symptoms**: No new YouTube episodes, stale watermark
```bash
# Check cron job status
ps aux | grep youtube

# Check recent logs  
ls -la ~/Library/Logs/podcast-scraper/youtube_cron_*

# Manual run (for testing)
./youtube_cron_job.sh

# Check for lock issues
ls -la .yt_push.lock
# Remove stale lock (if >1 hour old)
rm -f .yt_push.lock
```

### CI Pipeline Failures

**Symptoms**: Red X on GitHub Actions, no new digest

1. **Check failure artifacts**:
   - Go to failed workflow run
   - Download "failure-artifacts" zip
   - Review logs and database snapshots

2. **Common fixes**:
   ```bash
   # Fix environment secrets
   # - Check GitHub repo secrets are set
   # - Verify .env file has correct values
   
   # Reset watermark if corrupted
   echo '{"run_id":"manual","status":"reset","pushed_at":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > state/yt_last_push.json
   git add state/yt_last_push.json
   git commit -m "Reset watermark"
   git push
   ```

### Database Issues

**Symptoms**: SQLite errors, corrupted data

```bash
# Check database integrity
sqlite3 podcast_monitor.db "PRAGMA integrity_check;"
sqlite3 youtube_transcripts.db "PRAGMA integrity_check;"

# If corrupted, restore from backup
cd ~/.podcast-scraper-backups/
LATEST_BACKUP=$(ls -t podcast_monitor_*.db.gz | head -1)
gunzip -c "$LATEST_BACKUP" > ~/Desktop/podcast-scraper/podcast_monitor.db.restored

# Test restored database
sqlite3 ~/Desktop/podcast-scraper/podcast_monitor.db.restored "PRAGMA integrity_check;"

# If good, replace (MAKE SURE TO BACKUP CURRENT FIRST)
mv ~/Desktop/podcast-scraper/podcast_monitor.db ~/Desktop/podcast-scraper/podcast_monitor.db.corrupted
mv ~/Desktop/podcast-scraper/podcast_monitor.db.restored ~/Desktop/podcast-scraper/podcast_monitor.db
```

### Feed/RSS Issues

**Symptoms**: RSS feed not updating, missing episodes

```bash
# Check recent digest files
ls -la daily_digests/*digest*.md

# Manually regenerate RSS
python3 rss_generator_multi_topic.py

# Check feed validity
curl -s https://podcast.paulrbrown.org/daily-digest.xml | head -20
```

## Emergency Procedures

### Complete System Recovery

1. **Stop all processes**:
   ```bash
   # Kill any running jobs
   pkill -f youtube_processor
   pkill -f daily_podcast_pipeline
   ```

2. **Restore databases from backup**:
   ```bash
   cd ~/.podcast-scraper-backups/
   
   # Find latest good backups
   ls -t *_*.db.gz | head -4
   
   # Restore both databases
   gunzip -c $(ls -t podcast_monitor_*.db.gz | head -1) > ~/Desktop/podcast-scraper/podcast_monitor.db
   gunzip -c $(ls -t youtube_transcripts_*.db.gz | head -1) > ~/Desktop/podcast-scraper/youtube_transcripts.db
   ```

3. **Verify restoration**:
   ```bash
   python3 utils/db.py podcast_monitor.db
   python3 utils/db.py youtube_transcripts.db
   ```

4. **Reset state and restart**:
   ```bash
   # Reset watermark
   echo '{"run_id":"recovery","status":"restored","pushed_at":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > state/yt_last_push.json
   
   # Commit state
   git add podcast_monitor.db youtube_transcripts.db state/yt_last_push.json
   git commit -m "Emergency recovery: restored databases"
   git push
   ```

### Healthcheck Reset

If healthchecks are firing false alarms:
```bash
# Send manual success ping
curl -m 10 -fsS "$HEALTHCHECK_URL_RSS" -d '{"status":"manual_reset"}'
curl -m 10 -fsS "$HEALTHCHECK_URL_YT" -d '{"status":"manual_reset"}'
```

## Monitoring Metrics

### Key Performance Indicators
- **YouTube Cron**: Should run every 6 hours (±30 minutes acceptable)
- **Daily Digest**: Should complete within 90 minutes
- **RSS Feed**: Should update within 2 hours of digest completion
- **Database Size**: Growth should be <1MB per day
- **Backup Success**: 100% success rate over 7 days

### Alert Thresholds
- **YouTube stale**: >8 hours since last watermark update
- **CI failure**: Any failed workflow run
- **Backup failure**: Any backup run with <100% success
- **Database corruption**: Any PRAGMA integrity_check failure

## Maintenance Schedule

### Daily (Automated)
- Database backups at 2 AM
- Log rotation for YouTube cron
- CI digest pipeline at 6 AM UTC

### Weekly (Manual)
- Backup restore test (Mondays)
- Log size review
- Database health check

### Monthly (Manual)  
- Review backup retention (should be ~30 files per database)
- Check disk space usage
- Update dependencies if needed

### Quarterly (Manual)
- Full disaster recovery drill
- Review and update documentation
- Evaluate monitoring and alerting effectiveness

## Contact Information

- **Primary**: Check GitHub Issues for system-wide problems
- **Logs**: `~/Library/Logs/podcast-scraper/`
- **Backups**: `~/.podcast-scraper-backups/`  
- **Status**: GitHub Actions workflow history
- **Feed**: https://podcast.paulrbrown.org/daily-digest.xml