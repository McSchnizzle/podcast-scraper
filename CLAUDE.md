# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Multi-Topic Podcast Digest System that automatically monitors podcast RSS feeds and YouTube channels, processes audio content using Apple Silicon-optimized transcription, and generates AI-powered topic-specific daily digests with prose validation and comprehensive retention management.

**Core Architecture**: Multi-topic system with specialized processing per content area:
- **6 Topics**: AI News, Tech Product Releases, Tech News & Culture, Community Organizing, Social Justice, Societal Culture Change
- **RSS Episodes**: `podcast_monitor.db` → `pre-download` → `downloaded` → `transcribed` → `topic-scored` → `digested`  
- **YouTube Episodes**: `youtube_transcripts.db` → `transcribed` → `topic-scored` → `digested`
- **Multi-Topic Output**: Individual `{topic}_digest_{timestamp}.md/mp3` files per topic
- **Prose Validation**: Automatic rewriting to ensure TTS-suitable content (no bullet points/markdown)

**Key Technologies**:
- **OpenAI Integration**: GPT-5 for digest generation, GPT-5-mini for topic scoring
- **CRITICAL**: GPT-5 models are required - DO NOT revert to GPT-4 under any circumstances
- **Prose Validator**: Comprehensive validation and automatic rewriting for TTS optimization
- **Multi-Topic TTS**: Topic-specific voice configurations using ElevenLabs
- **Parakeet MLX**: Apple Silicon-optimized ASR with 10-minute chunking and cross-platform fallbacks
- **14-Day Retention**: Intelligent cleanup with database field optimization and VACUUM operations
- **Mon-Fri Scheduling**: Weekday-only processing with Friday weekly and Monday catch-up modes
- **Batch Deployment**: Multiple topic releases per day with enhanced RSS multi-episode support
- **Dual SQLite Databases**: Cross-database processing with synchronized status updates

**RSS Feed**: https://podcast.paulrbrown.org/daily-digest.xml
**GitHub Releases**: MP3 files hosted at https://github.com/McSchnizzle/podcast-scraper/releases
**Local Cron**: YouTube transcript downloads every 6 hours via `youtube_cron_job.sh`

## Development Commands

### Main Pipeline Operations
```bash
# Run complete daily workflow (main entry point)
python3 daily_podcast_pipeline.py --run

# Show current system status
python3 daily_podcast_pipeline.py --status

# Test all components
python3 daily_podcast_pipeline.py --test

# Run cleanup only
python3 daily_podcast_pipeline.py --cleanup
```

### Individual Component Operations
```bash
# Monitor feeds for new episodes
python3 feed_monitor.py

# Process pending transcriptions
python3 content_processor.py

# Generate OpenAI-powered multi-topic digests
python3 openai_digest_integration.py

# Generate multi-topic TTS audio files
python3 multi_topic_tts_generator.py

# Deploy multiple topic episodes to GitHub releases
python3 deploy_multi_topic.py

# Update RSS feed with multi-topic support
python3 rss_generator_multi_topic.py

# Run 14-day retention cleanup
python3 retention_cleanup.py
```

### Requirements Management
```bash
# Install dependencies
pip install -r requirements-dev.txt

# Install Apple Silicon optimizations
pip install parakeet-mlx

# Fix macOS malloc warnings
./fix_malloc_warnings.sh

# Verify ffmpeg installation
brew install ffmpeg
```

### Environment Setup
```bash
# Required environment variables
export GITHUB_TOKEN="your_github_token"
export ELEVENLABS_API_KEY="your_elevenlabs_key"  # Optional for TTS

# Verify Claude Code CLI
claude --version
```

## System Architecture

### Core Processing Flow

**RSS Pipeline (GitHub Actions)**:
1. **Feed Monitoring** (`feed_monitor.py`): RSS discovery → `podcast_monitor.db` with `pre-download` status
2. **Content Processing** (`content_processor.py`): Audio download/transcription → `downloaded`/`transcribed` status  
3. **Claude Analysis** (`claude_headless_integration.py`): Process `transcribed` episodes → markdown digest with timestamp
4. **TTS Generation** (`claude_tts_generator.py`): Extract timestamp from markdown → generate matching MP3 filename
5. **Publishing Pipeline**: GitHub deployment → RSS updates → `digested` status

**YouTube Pipeline (Local + GitHub Actions)**:
1. **Local Cron Job** (every 6 hours): `youtube_cron_job.sh` → downloads transcripts → `youtube_transcripts.db`
2. **Local Processing**: Commits transcripts and database to GitHub repository 
3. **GitHub Actions**: Pulls latest changes → processes YouTube episodes alongside RSS episodes
4. **Synchronized Processing**: Both RSS and YouTube episodes processed together in digest generation

### Database Architecture

**Dual Database System**:
- **`podcast_monitor.db`**: RSS episodes with full audio processing workflow
- **`youtube_transcripts.db`**: YouTube episodes with transcript-only workflow

**Episodes table schema** (both databases):
- `episode_id`: 8-character hash identifier
- `status`: Workflow state (`pre-download`, `downloaded`, `transcribed`, `digested`, `failed`)
- `transcript_path`: Path to generated transcript file
- `priority_score`: Content importance (0.0-1.0)
- `content_type`: Classification (discussion, news, tutorial)

**Critical Database Workflow**:
1. Always `git pull` before local processing to capture GitHub Actions changes
2. Local changes to `youtube_transcripts.db` must be committed and pushed
3. GitHub Actions processes both databases simultaneously

### Configuration System
**Centralized config** in `config.py`:
- Processing settings (10-minute chunks, priority thresholds)
- Status workflows (RSS vs YouTube paths)  
- Directory management (audio_cache, transcripts, daily_digests)
- Environment validation (Claude CLI, ffmpeg, API keys)

### Audio Processing Pipeline
```
RSS Audio: Download → ffmpeg conversion → 10min chunks → ASR Engine → transcript
YouTube: Direct transcript API → duration filter (>3min) → transcript
```

**ASR Engine Selection**:
- **Apple Silicon + Local**: Parakeet MLX (optimal performance, ~0.18x RTF)
- **Non-Apple Silicon**: Faster-Whisper (4x faster than OpenAI Whisper, ~0.08x RTF)
- **Fallback**: OpenAI Whisper (cross-platform compatibility)

**Processing Features**:
- Automatic chunking into 10-minute segments for optimal performance
- Voice Activity Detection (VAD) to skip silence regions  
- Rich progress logging with time estimation and performance metrics
- Cross-platform compatibility with environment detection

### Claude Integration Architecture
**Headless Mode**: Uses `claude` CLI with digest instructions from `claude_digest_instructions.md`
- Processes ONLY episodes with `status='transcribed'` from BOTH databases
- Generates topic-organized daily digest with embedded timestamp
- Moves processed transcripts to `transcripts/digested/`
- Updates episode status to `digested` in both databases

**TTS Integration with Perfect Timestamp Synchronization**:
1. Claude generates markdown file: `daily_digest_YYYYMMDD_HHMMSS.md`
2. TTS script extracts timestamp using regex: `r'daily_digest_(\d{8}_\d{6})\.md'`
3. TTS generates MP3 with identical timestamp: `complete_topic_digest_YYYYMMDD_HHMMSS.mp3`
4. Both files deployed to GitHub release with matching filenames
5. RSS feed links to MP3 files via `https://paulrbrown.org/audio/` URLs

### File Structure Logic
- `audio_cache/`: Downloaded RSS audio files (cleaned after processing)
- `transcripts/`: Active transcript files ready for digest (RSS + YouTube)
- `transcripts/digested/`: Processed transcript files (archived after digest generation)
- `daily_digests/`: Generated digest files with timestamp synchronization:
  - `daily_digest_YYYYMMDD_HHMMSS.md`: Claude-generated digest
  - `claude_digest_full_YYYYMMDD_HHMMSS.txt`: Full script for TTS
  - `claude_digest_tts_YYYYMMDD_HHMMSS.txt`: TTS-optimized script
  - `complete_topic_digest_YYYYMMDD_HHMMSS.mp3`: Generated audio with matching timestamp
  - `complete_topic_digest_YYYYMMDD_HHMMSS.json`: Audio metadata
- `api/`: Vercel deployment endpoints with intelligent build skipping
- `podcast_monitor.db`: RSS episodes database
- `youtube_transcripts.db`: YouTube episodes database

## Critical Operational Patterns

### Local Development Workflow
**ALWAYS follow this sequence when working locally**:
```bash
# 1. MANDATORY: Pull latest changes from GitHub Actions
git pull

# 2. Check both database states  
python3 -c "import sqlite3; conn=sqlite3.connect('podcast_monitor.db'); print('RSS Episodes:', conn.execute('SELECT status, COUNT(*) FROM episodes GROUP BY status').fetchall()); conn.close()"
python3 -c "import sqlite3; conn=sqlite3.connect('youtube_transcripts.db'); print('YouTube Episodes:', conn.execute('SELECT status, COUNT(*) FROM episodes GROUP BY status').fetchall()); conn.close()"

# 3. If making local changes to YouTube processing:
# - Process YouTube transcripts locally
# - Commit both transcript files AND youtube_transcripts.db
# - Push changes before GitHub Actions runs

git add transcripts/ youtube_transcripts.db
git commit -m "Update YouTube transcripts and database"
git push
```

### YouTube Cron Job System
**Local Machine Setup** (runs every 6 hours):
```bash
# Cron job entry (crontab -e):
0 */6 * * * /path/to/podcast-scraper/youtube_cron_job.sh

# The cron job:
1. Downloads new YouTube transcripts via youtube-transcript-api
2. Updates youtube_transcripts.db with new episodes
3. Commits and pushes both transcript files and database to GitHub
4. GitHub Actions workflow processes both RSS and YouTube episodes together
```

### TTS Timestamp Synchronization System
**Perfect timestamp matching process**:
1. **Claude Digest Generation**: Creates `daily_digest_20250901_115502.md` with embedded timestamp
2. **TTS Script Processing**: 
   - Extracts timestamp using regex: `r'daily_digest_(\\d{8}_\\d{6})\\.md'`
   - Generates identical timestamp: `20250901_115502`
   - Creates matching MP3: `complete_topic_digest_20250901_115502.mp3`
3. **Deployment**: Both files deployed to GitHub release with synchronized names
4. **RSS Feed**: Links to MP3 using timestamp-matched URLs

**CRITICAL**: The TTS script `claude_tts_generator.py` uses `find_most_recent_digest()` to locate markdown files and extract timestamps for perfect synchronization.

### Vercel Integration Management
**Intelligent Build Skipping**:
- **Script**: `vercel-build-ignore.sh` prevents unnecessary Vercel builds
- **Triggers BUILD**: Changes to `api/`, `vercel.json`, `package.json`, `requirements.txt`  
- **SKIPS BUILD**: Changes to `daily_digests/`, `transcripts/`, `*.db`, `daily-digest.xml`
- **Configuration**: `vercel.json` with `deploymentEnabled: false` and `ignoreCommand`

## Development Patterns

### Adding New Podcast Feeds
Modify feed configuration in `config.py`:
```python
feeds = [
    {
        'title': 'Podcast Name',
        'url': 'https://example.com/rss',
        'type': 'rss',  # or 'youtube' 
        'topic_category': 'technology'  # or 'business', 'news'
    }
]
```

### Status Workflow Management
Use `config.get_next_status(current_status, episode_type)` for proper status transitions:
- Always validate status changes through configuration
- RSS and YouTube have different workflows
- Failed episodes marked with `status='failed'`

### Transcription System
**Performance characteristics**:
- **Parakeet MLX** (Apple Silicon): ~0.18x RTF (Real-Time Factor)
- **Faster-Whisper** (Cross-platform): ~0.08x RTF (4x faster than OpenAI Whisper)
- **OpenAI Whisper** (Fallback): ~0.25x RTF (cross-platform compatibility)

**Features**:
- 10-minute chunking for optimal performance across all engines
- Voice Activity Detection (VAD) for silence skipping in Faster-Whisper
- Rich progress logging with chunk-by-chunk progress tracking
- Automatic episode matching for cached audio files
- Environment detection: Apple Silicon vs non-Apple Silicon systems

### Error Handling Patterns  
- Database operations use transactions with rollback
- Audio processing has retry mechanisms with exponential backoff
- Claude integration validates transcript availability before processing
- Status tracking prevents duplicate processing

## Common Issues & Troubleshooting

### Database Synchronization Issues
**Symptoms**: Episodes processed locally not appearing in GitHub Actions
**Solution**: Always `git pull` before local work, commit both transcript files AND database changes
```bash
# Check database states
sqlite3 podcast_monitor.db "SELECT status, COUNT(*) FROM episodes GROUP BY status;"
sqlite3 youtube_transcripts.db "SELECT status, COUNT(*) FROM episodes GROUP BY status;"

# Reconcile if needed
git add transcripts/ *.db
git commit -m "Sync transcript files and databases"
git push
```

### TTS Timestamp Mismatch
**Symptoms**: MP3 files with different timestamps than digest markdown files
**Root Cause**: TTS script not finding correct digest file or timestamp extraction failure
**Solution**: Check `claude_tts_generator.py` timestamp extraction:
```python
# Verify regex pattern matches digest filename format
pattern = r'daily_digest_(\d{8}_\d{6})\.md'
```

### YouTube Cron Job Failures  
**Symptoms**: Missing YouTube transcripts, stale youtube_transcripts.db
**Check**: Cron job status and logs
```bash
crontab -l  # Verify cron job exists
tail -f /var/log/cron.log  # Check execution logs
./youtube_cron_job.sh  # Manual test run
```

### Vercel Deployment Issues
**250MB Function Size Error**: Heavy dependencies causing deployment failures
**Solution**: Use `api/requirements.txt` with minimal deps (requests, python-dateutil only)
- Root `requirements-dev.txt` excluded via `.vercelignore` 
- Serverless functions optimized to <1MB vs 250MB+ limit

### GitHub Actions Database Caching
**Symptoms**: Database changes not reflected in workflow
**Root Cause**: Old caching was overwriting repo database state  
**Fixed**: Database caching removed from workflow - always uses repo state

### Transcription Performance
Parakeet MLX performance varies by file. Use `RobustTranscriber.estimate_transcription_time()` for planning. Large files automatically chunked into 10-minute segments.

### Claude Integration Requirements
- Claude Code CLI must be installed and available in PATH
- Episodes must have `status='transcribed'` in BOTH databases to be included in digest
- Digest instructions in `claude_digest_instructions.md` control output format
- TTS generation requires ElevenLabs API key for MP3 creation

### GPT-5 Implementation
- **CRITICAL**: See `gpt5-implementation-learnings.md` for complete GPT-5 API migration guide
- GPT-5 models require Responses API, not Chat Completions API
- Use `max_output_tokens` instead of `max_tokens` for Responses API
- Full transcript processing without truncation (400K token context)
- Structured JSON output via `text.format.json_schema`

### Environment Dependencies
- macOS: Use `./fix_malloc_warnings.sh` for Python malloc warnings
- ffmpeg required for RSS audio format conversion  
- GitHub token required for deployment and release features
- ElevenLabs API key required for TTS MP3 generation

### macOS Timeout Command
**CRITICAL**: macOS does not have native `timeout` command. Must use GNU coreutils:
```bash
# Install coreutils for timeout functionality
brew install coreutils

# Use gtimeout instead of timeout on macOS
gtimeout 600 python3 script.py  # 10-minute timeout
gtimeout 30s command            # 30-second timeout
gtimeout 5m command            # 5-minute timeout

# Syntax: gtimeout [DURATION] [COMMAND] [ARGS...]
# Duration formats: s (seconds), m (minutes), h (hours)
```