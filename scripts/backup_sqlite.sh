#!/usr/bin/env bash
# SQLite Database Backup Script
# Creates compressed backups with 14-day retention
set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$HOME/.podcast-scraper-backups"
LOG_DIR="$HOME/Library/Logs/podcast-scraper"

# Database files to backup
DATABASES=("podcast_monitor.db" "youtube_transcripts.db")

# Create directories
mkdir -p "$BACKUP_DIR" "$LOG_DIR"

# Logging function
log() {
    local level="$1"
    shift
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [$level] $*" | tee -a "$LOG_DIR/backup.log"
}

# Error handling
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        log "ERROR" "Backup script failed with exit code $exit_code"
    fi
    exit $exit_code
}

trap cleanup EXIT INT TERM

main() {
    cd "$PROJECT_DIR"
    
    local timestamp=$(date -u +%Y%m%d_%H%M%S)
    local backup_date=$(date -u +%Y-%m-%d)
    
    log "INFO" "Starting SQLite backup (timestamp: $timestamp)"
    
    local success_count=0
    local total_size=0
    
    # Backup each database
    for db in "${DATABASES[@]}"; do
        if [[ ! -f "$db" ]]; then
            log "WARN" "Database file not found: $db"
            continue
        fi
        
        local backup_name="${db%.db}_${timestamp}.db"
        local backup_path="$BACKUP_DIR/$backup_name"
        local compressed_path="${backup_path}.gz"
        
        log "INFO" "Backing up $db"
        
        # Check database integrity first
        if ! sqlite3 "$db" "PRAGMA integrity_check;" | grep -q "ok"; then
            log "ERROR" "Integrity check failed for $db"
            continue
        fi
        
        # Create backup using .backup command (atomic)
        if sqlite3 "$db" ".backup '$backup_path'"; then
            # Verify backup integrity
            if sqlite3 "$backup_path" "PRAGMA integrity_check;" | grep -q "ok"; then
                # Compress backup
                if gzip "$backup_path"; then
                    local file_size=$(stat -f%z "$compressed_path" 2>/dev/null || echo "0")
                    total_size=$((total_size + file_size))
                    
                    log "INFO" "Successfully backed up $db ($file_size bytes)"
                    success_count=$((success_count + 1))
                else
                    log "ERROR" "Failed to compress backup for $db"
                    rm -f "$backup_path" 2>/dev/null || true
                fi
            else
                log "ERROR" "Backup integrity check failed for $db"
                rm -f "$backup_path" 2>/dev/null || true
            fi
        else
            log "ERROR" "Failed to create backup for $db"
        fi
    done
    
    # Clean up old backups (14-day retention)
    log "INFO" "Cleaning up old backups (14-day retention)"
    local cleaned_count=0
    
    # Find and remove backups older than 14 days
    while IFS= read -r -d '' old_backup; do
        if rm -f "$old_backup"; then
            cleaned_count=$((cleaned_count + 1))
            log "INFO" "Removed old backup: $(basename "$old_backup")"
        fi
    done < <(find "$BACKUP_DIR" -name "*.db.gz" -mtime +14 -print0 2>/dev/null)
    
    # Log backup statistics
    local backup_count=$(find "$BACKUP_DIR" -name "*.db.gz" | wc -l | tr -d ' ')
    local backup_size=$(find "$BACKUP_DIR" -name "*.db.gz" -exec stat -f%z {} + 2>/dev/null | awk '{sum += $1} END {print sum+0}')
    
    log "INFO" "Backup completed: $success_count/${#DATABASES[@]} databases backed up"
    log "INFO" "Current backup set: $backup_count files, total size: $backup_size bytes"
    log "INFO" "Cleaned up $cleaned_count old backups"
    
    # Create backup manifest for verification
    local manifest_file="$BACKUP_DIR/backup_manifest_${timestamp}.json"
    jq -n \
        --arg timestamp "$timestamp" \
        --arg date "$backup_date" \
        --arg success_count "$success_count" \
        --arg total_databases "${#DATABASES[@]}" \
        --arg total_size "$total_size" \
        --arg backup_count "$backup_count" \
        --arg backup_dir "$BACKUP_DIR" \
        '{
            timestamp: $timestamp,
            date: $date,
            databases_backed_up: ($success_count | tonumber),
            total_databases: ($total_databases | tonumber),
            backup_size_bytes: ($total_size | tonumber),
            total_backups: ($backup_count | tonumber),
            backup_directory: $backup_dir,
            status: (if ($success_count | tonumber) == ($total_databases | tonumber) then "success" else "partial" end)
        }' > "$manifest_file"
    
    # Ensure at least one database was backed up
    if [[ $success_count -eq 0 ]]; then
        log "ERROR" "No databases were successfully backed up"
        exit 1
    fi
    
    log "INFO" "Backup manifest created: $manifest_file"
    
    # Optional: Upload to GitHub Artifacts if in CI
    if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
        log "INFO" "Running in GitHub Actions, artifacts will be uploaded by workflow"
    fi
}

# Weekly restore test function
restore_test() {
    log "INFO" "Running weekly restore smoke test"
    
    local latest_backup
    latest_backup=$(find "$BACKUP_DIR" -name "podcast_monitor_*.db.gz" | sort | tail -1)
    
    if [[ -z "$latest_backup" ]]; then
        log "ERROR" "No backup found for restore test"
        return 1
    fi
    
    local test_dir="/tmp/backup_restore_test_$$"
    mkdir -p "$test_dir"
    
    # Extract and test latest backup
    if gunzip -c "$latest_backup" > "$test_dir/test.db"; then
        if sqlite3 "$test_dir/test.db" "PRAGMA integrity_check;" | grep -q "ok"; then
            local row_count
            row_count=$(sqlite3 "$test_dir/test.db" "SELECT COUNT(*) FROM episodes;" 2>/dev/null || echo "0")
            log "INFO" "Restore test passed: $row_count episodes in restored database"
        else
            log "ERROR" "Restore test failed: integrity check failed"
            return 1
        fi
    else
        log "ERROR" "Restore test failed: could not extract backup"
        return 1
    fi
    
    # Cleanup
    rm -rf "$test_dir"
    log "INFO" "Restore test completed successfully"
}

# Parse command line arguments
case "${1:-backup}" in
    "backup")
        main "$@"
        ;;
    "restore-test")
        restore_test
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [backup|restore-test|help]"
        echo ""
        echo "Commands:"
        echo "  backup       Create backups of SQLite databases (default)"
        echo "  restore-test Run restore smoke test on latest backup"
        echo "  help         Show this help message"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac