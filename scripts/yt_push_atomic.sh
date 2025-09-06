#!/usr/bin/env bash
# YouTube Transcript Atomic Push Script
# Ensures atomic commits and state tracking for CI handoff
set -euo pipefail

REPO_DIR="$HOME/Desktop/podcast-scraper"
LOCK_FILE="$REPO_DIR/.yt_push.lock"
STATE_DIR="$REPO_DIR/state"
WATERMARK="$STATE_DIR/yt_last_push.json"
LOG_DIR="$HOME/Library/Logs/podcast-scraper"

# Create directories
mkdir -p "$STATE_DIR" "$LOG_DIR"

# Logging function
log() {
    local level="$1"
    shift
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [$level] $*" | tee -a "$LOG_DIR/youtube-push.log"
}

# Error handling
cleanup() {
    local exit_code=$?
    if [[ -f "$LOCK_FILE" ]]; then
        rm -f "$LOCK_FILE" 2>/dev/null || true
    fi
    if [[ $exit_code -ne 0 ]]; then
        log "ERROR" "Script failed with exit code $exit_code"
    fi
    exit $exit_code
}

trap cleanup EXIT INT TERM

main() {
    cd "$REPO_DIR"
    
    # Simple file-based locking
    if [[ -f "$LOCK_FILE" ]]; then
        local lock_age=$(($(date +%s) - $(stat -f %m "$LOCK_FILE" 2>/dev/null || echo 0)))
        if [[ $lock_age -lt 3600 ]]; then  # 1 hour stale lock timeout
            log "INFO" "Another push is in progress or recent lock exists, exiting"
            exit 0
        else
            log "WARN" "Removing stale lock file (age: ${lock_age}s)"
            rm -f "$LOCK_FILE"
        fi
    fi
    
    # Create lock
    echo $$ > "$LOCK_FILE"
    log "INFO" "Acquired lock for PID $$"
    
    # Start timer
    local start_time=$(date +%s)
    local run_id=$(date -u +%Y%m%dT%H%M%SZ)
    
    log "INFO" "Starting YouTube push (run_id: $run_id)"
    
    # Ensure repo is clean and up to date
    log "INFO" "Pulling latest changes"
    git config pull.ff only
    if ! git pull; then
        log "ERROR" "Failed to pull latest changes"
        exit 1
    fi
    
    # Check for changes to push
    local changes=$(git status --porcelain)
    if [[ -z "$changes" ]]; then
        log "INFO" "No changes to push, updating watermark with no-op status"
        # Update watermark even for no-op to show script is running
        local duration=$(($(date +%s) - start_time))
        jq -n \
            --arg run_id "$run_id" \
            --arg sha "$(git rev-parse HEAD)" \
            --arg pushed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            --arg status "no-changes" \
            --arg duration "$duration" \
            --argjson episodes 0 \
            '{
                run_id: $run_id,
                commit_sha: $sha,
                pushed_at: $pushed_at,
                status: $status,
                episodes_processed: $episodes,
                duration_seconds: ($duration | tonumber)
            }' > "$WATERMARK"
        exit 0
    fi
    
    log "INFO" "Found changes to commit:"
    git status --porcelain | while read -r line; do
        log "INFO" "  $line"
    done
    
    # Count episodes processed (rough estimate from transcript files)
    local episodes_count=0
    if [[ -d "transcripts" ]]; then
        episodes_count=$(find transcripts -name "*.txt" -newer "$WATERMARK" 2>/dev/null | wc -l | tr -d ' ')
    fi
    
    # Stage all intended changes
    log "INFO" "Staging changes"
    git add transcripts/ youtube_transcripts.db
    
    # Create atomic commit
    local commit_msg="YouTube sync: $run_id - $episodes_count episodes processed"
    log "INFO" "Creating commit: $commit_msg"
    
    if ! git commit -m "$commit_msg"; then
        log "ERROR" "Failed to create commit"
        exit 1
    fi
    
    # Push with retry
    local push_attempts=0
    local max_attempts=3
    while [[ $push_attempts -lt $max_attempts ]]; do
        push_attempts=$((push_attempts + 1))
        log "INFO" "Pushing changes (attempt $push_attempts/$max_attempts)"
        
        if git push; then
            log "INFO" "Successfully pushed changes"
            break
        else
            if [[ $push_attempts -lt $max_attempts ]]; then
                log "WARN" "Push failed, retrying in 10 seconds"
                sleep 10
                # Try to pull and rebase if there were remote changes
                git pull --rebase || {
                    log "ERROR" "Failed to rebase, manual intervention required"
                    exit 1
                }
            else
                log "ERROR" "Failed to push after $max_attempts attempts"
                exit 1
            fi
        fi
    done
    
    # Update watermark file
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local commit_sha=$(git rev-parse HEAD)
    
    log "INFO" "Updating watermark file"
    jq -n \
        --arg run_id "$run_id" \
        --arg sha "$commit_sha" \
        --arg pushed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg status "success" \
        --arg duration "$duration" \
        --argjson episodes "$episodes_count" \
        '{
            run_id: $run_id,
            commit_sha: $sha,
            pushed_at: $pushed_at,
            status: $status,
            episodes_processed: $episodes,
            duration_seconds: ($duration | tonumber)
        }' > "$WATERMARK"
    
    # Commit and push watermark
    git add "$WATERMARK"
    if git commit -m "YouTube watermark: $run_id"; then
        git push || log "WARN" "Failed to push watermark, continuing"
    fi
    
    log "INFO" "YouTube push completed successfully (duration: ${duration}s, episodes: $episodes_count)"
    
    # Send healthcheck ping if configured
    if [[ -n "${HEALTHCHECK_URL_YT:-}" ]]; then
        local payload=$(jq -n \
            --arg episodes "$episodes_count" \
            --arg duration "$duration" \
            --arg status "success" \
            '{episodes_processed: ($episodes | tonumber), duration_seconds: ($duration | tonumber), status: $status}')
        
        if curl -m 10 -fsS "$HEALTHCHECK_URL_YT" \
            -H "Content-Type: application/json" \
            -d "$payload" >/dev/null 2>&1; then
            log "INFO" "Healthcheck ping sent successfully"
        else
            log "WARN" "Failed to send healthcheck ping"
        fi
    fi
}

# Run main function
main "$@"