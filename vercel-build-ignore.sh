#!/bin/bash

# Vercel build ignore script
# This script determines whether Vercel should build based on what files changed

echo "🔍 Checking if Vercel build should be skipped..."

# Get the list of changed files
CHANGED_FILES=$(git diff HEAD^ HEAD --name-only)
echo "Changed files: $CHANGED_FILES"

# Files that should trigger a Vercel build
BUILD_TRIGGERS="api/ vercel.json package.json requirements.txt"

# Check if any build-triggering files were changed
SHOULD_BUILD=false
for trigger in $BUILD_TRIGGERS; do
    if echo "$CHANGED_FILES" | grep -q "$trigger"; then
        echo "✅ Found changes in $trigger - build needed"
        SHOULD_BUILD=true
        break
    fi
done

# Files that should NOT trigger a build (daily pipeline outputs)
SKIP_PATTERNS="daily_digests/ transcripts/ podcast_monitor.db youtube_transcripts.db daily-digest.xml"

if [ "$SHOULD_BUILD" = "false" ]; then
    echo "🚫 No API or config changes detected - skipping build"
    exit 0  # Exit 0 = skip build
else
    echo "🏗️ Build-triggering changes detected - proceeding with build"
    exit 1  # Exit 1 = proceed with build
fi