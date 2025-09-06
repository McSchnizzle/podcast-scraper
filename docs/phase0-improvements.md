# Phase 0 Improvements: Hardened Operating Model

**Implementation Date:** 2025-09-06  
**Status:** Complete  

This document describes the Phase 0 improvements that harden the existing hybrid operating model with enterprise-grade reliability, atomicity, and observability.

## Overview of Changes

Phase 0 maintains the existing architecture while adding crucial safeguards:
- **Local YouTube cron job** continues running every 6 hours
- **GitHub Actions** continues handling daily digest pipeline
- **SQLite databases** remain as primary storage (no PostgreSQL migration)
- **Host OS runtime** preserved (Docker remains optional)

## 1. SQLite Hardening

### Database Configuration Improvements
- **WAL Mode**: Already enabled, provides better concurrency
- **Busy Timeout**: Added 30-second timeout for concurrent access in `utils/db.py`
- **Connection Standards**: Enforced through `DatabaseConnectionFactory`

### Verification
```bash
# Test database configuration
python3 utils/db.py podcast_monitor.db

# Check busy timeout
python3 -c "from utils.db import get_db_connection; 
with get_db_connection('podcast_monitor.db') as conn:
    print('Busy timeout:', conn.execute('PRAGMA busy_timeout').fetchone()[0], 'ms')"
```

**Result**: 30-second busy timeout active on all connections

## 2. YouTube Cron Job Hardening

### New Atomic Push System
- **File Locking**: Prevents concurrent executions using `.yt_push.lock`
- **Atomic Commits**: Single commit per cycle with proper staging
- **Retry Logic**: 3-attempt push with rebase on conflicts
- **State Tracking**: Watermark file for CI handoff

### Key Files
- `scripts/yt_push_atomic.sh` - Atomic Git push script
- `youtube_cron_job.sh` - Updated to use atomic push
- `state/yt_last_push.json` - Watermark file for traceability

### Watermark File Format
```json
{
  "run_id": "20250906T120000Z",
  "commit_sha": "abc123...",
  "pushed_at": "2025-09-06T12:00:00Z",
  "status": "success",
  "episodes_processed": 15,
  "duration_seconds": 45
}
```

### Verification
```bash
# Test atomic push (dry run)
./scripts/yt_push_atomic.sh

# Check watermark
cat state/yt_last_push.json | jq .
```

## 3. CI/CD Hardening

### Concurrency Control
```yaml
concurrency:
  group: daily-digest-${{ github.ref }}
  cancel-in-progress: false
```

### Fast-Fail Environment Checks
- Validates all required secrets before processing
- Exits early on critical missing configuration
- Provides clear error messages

### Watermark Integration
- Reads `state/yt_last_push.json` for traceability
- Displays YouTube sync status in job summary
- Alerts if watermark is stale (>8 hours)

### Enhanced Monitoring
- **Job Summaries**: Markdown reports with episode counts and status
- **Failure Artifacts**: Uploads logs and databases on failure (14-day retention)
- **Step Timeouts**: Individual step timeouts prevent runaway processes

## 4. Backup Strategy

### Automated SQLite Backups
- **Script**: `scripts/backup_sqlite.sh`
- **Schedule**: Run nightly (to be added to cron)
- **Retention**: 14 days compressed backups
- **Location**: `~/.podcast-scraper-backups/`

### Features
- **Integrity Checks**: Pre-backup validation
- **Atomic Backup**: Using `.backup` command
- **Compression**: Gzip for space efficiency
- **Manifest Files**: JSON metadata for each backup run
- **Restore Testing**: Weekly smoke tests

### Usage
```bash
# Create backup
./scripts/backup_sqlite.sh backup

# Test restore
./scripts/backup_sqlite.sh restore-test

# View backups
ls -la ~/.podcast-scraper-backups/
```

## 5. Healthcheck Integration

### Healthchecks.io Integration
- **YouTube Cron**: Pings `HEALTHCHECK_URL_YT` on success/failure
- **Daily Digest**: Pings `HEALTHCHECK_URL_RSS` with metrics
- **Failure Handling**: Separate fail endpoints for immediate alerts

### Payload Format
```json
{
  "episodes_processed": 20,
  "duration_seconds": 300,
  "status": "success",
  "github_run_id": "123456"
}
```

### Setup Required
Add these secrets to GitHub Actions and local `.env`:
- `HEALTHCHECK_URL_RSS` - Daily digest healthcheck
- `HEALTHCHECK_URL_YT` - YouTube cron healthcheck

## 6. Security Improvements

### File Permissions
- **`.env` file**: Set to 600 (owner read/write only)
- **No shell exports**: Removed from documentation and processes

### Secret Management
- **Local**: `.env` file with restricted permissions
- **CI**: GitHub Actions secrets with validation
- **Logging**: Secrets never logged or exposed

## 7. Logging Enhancements

### Structured Logging
- **Format**: `YYYY-MM-DDTHH:MM:SSZ [LEVEL] message`
- **Location**: `~/Library/Logs/podcast-scraper/`
- **Rotation**: 10 files for YouTube cron, 14 days for backups

### Log Files
- `youtube_cron_YYYYMMDD_HHMMSS.log` - YouTube processing
- `youtube-push.log` - Atomic push operations  
- `backup.log` - Database backup operations

## Validation Checklist

- ✅ SQLite busy timeout configured (30 seconds)
- ✅ WAL mode active and working
- ✅ YouTube cron job hardened with locking
- ✅ Atomic push script working
- ✅ Watermark file created and updated
- ✅ CI workflow updated with concurrency control
- ✅ Fast-fail environment validation added
- ✅ Healthcheck integration ready
- ✅ Backup script tested and working
- ✅ Restore functionality verified
- ✅ .env permissions set to 600
- ✅ No secrets in logs or documentation

## Next Steps

1. **Add cron job for backups**:
   ```bash
   # Add to crontab -e
   0 2 * * * /Users/paulbrown/Desktop/podcast-scraper/scripts/backup_sqlite.sh backup
   ```

2. **Set up Healthchecks.io**:
   - Create two checks (RSS and YouTube)
   - Add URLs to `.env` and GitHub secrets

3. **Run for one week** to validate all systems

4. **Proceed to Phase 5** for enhanced observability and idempotency

## Troubleshooting

### Common Issues

**YouTube cron lock issues**:
```bash
# Check for stale locks
ls -la .yt_push.lock
# Remove if stale (>1 hour)
rm -f .yt_push.lock
```

**Backup failures**:
```bash
# Check backup logs
tail -f ~/Library/Logs/podcast-scraper/backup.log
# Manual backup test
./scripts/backup_sqlite.sh backup
```

**Watermark issues**:
```bash
# Reset watermark if corrupted
echo '{"run_id":"manual","status":"reset"}' > state/yt_last_push.json
```

## Files Changed/Added

### New Files
- `state/yt_last_push.json` - YouTube sync watermark
- `scripts/yt_push_atomic.sh` - Atomic Git push script  
- `scripts/backup_sqlite.sh` - Database backup script
- `docs/phase0-improvements.md` - This documentation

### Modified Files
- `utils/db.py` - Added busy_timeout configuration
- `youtube_cron_job.sh` - Complete rewrite with atomicity
- `.github/workflows/daily-podcast-pipeline.yml` - Added concurrency control, fast-fail, healthchecks
- `.env` - Permissions changed to 600

### Directories Created
- `state/` - For watermark and state files
- `scripts/` - For operational scripts
- `docs/` - For documentation
- `~/.podcast-scraper-backups/` - For database backups
- `~/Library/Logs/podcast-scraper/` - For structured logs