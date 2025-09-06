#!/bin/bash
# YouTube Transcript Processing Cron Job with Atomic Push
# Runs every 6 hours to process YouTube episodes and push atomically to Git

set -euo pipefail

# Configuration
PROJECT_DIR="/Users/paulbrown/Desktop/podcast-scraper"
PYTHON_EXE="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
LOG_DIR="$HOME/Library/Logs/podcast-scraper"

# Ensure directories exist
mkdir -p "$LOG_DIR"

# Load environment variables if .env exists
if [[ -f "$PROJECT_DIR/.env" ]]; then
    # Source .env file securely (only export what we need)
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# Change to project directory
cd "$PROJECT_DIR"

# Set up logging with rotation
LOG_FILE="$LOG_DIR/youtube_cron_$(date +%Y%m%d_%H%M%S).log"

# Logging function
log() {
    local level="$1"
    shift
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [$level] $*" | tee -a "$LOG_FILE"
}

# Error handling with cleanup
cleanup() {
    local exit_code=$?
    log "INFO" "YouTube cron job finished with exit code $exit_code"
    
    # Keep only last 10 log files
    find "$LOG_DIR" -name "youtube_cron_*.log" -type f | sort -r | tail -n +11 | xargs rm -f 2>/dev/null || true
    
    # Send healthcheck ping on failure
    if [[ $exit_code -ne 0 && -n "${HEALTHCHECK_URL_YT:-}" ]]; then
        curl -m 10 -fsS "$HEALTHCHECK_URL_YT/fail" >/dev/null 2>&1 || true
    fi
    
    exit $exit_code
}

trap cleanup EXIT INT TERM

main() {
    log "INFO" "YouTube cron job started"
    log "INFO" "Project Directory: $PROJECT_DIR"
    log "INFO" "Python Executable: $PYTHON_EXE"
    log "INFO" "Log Directory: $LOG_DIR"
    
    # Process YouTube episodes from last 7 days (168 hours)
    log "INFO" "Starting YouTube transcript processing (168 hours lookback)"
    
    if "$PYTHON_EXE" youtube_processor.py --process-new --hours-back 168; then
        log "INFO" "YouTube processing completed successfully"
        
        # Run atomic push script
        log "INFO" "Running atomic Git push"
        if "$PROJECT_DIR/scripts/yt_push_atomic.sh"; then
            log "INFO" "Atomic push completed successfully"
        else
            log "ERROR" "Atomic push failed"
            exit 1
        fi
    else
        log "ERROR" "YouTube processing failed"
        exit 1
    fi
    
    log "INFO" "YouTube cron job completed successfully"
}

# Run main function
main "$@"
