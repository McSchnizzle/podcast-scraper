# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Daily Podcast Digest System that automatically monitors podcast RSS feeds and YouTube channels, processes audio content using Apple Silicon-optimized transcription, and generates AI-powered daily digests using Claude integration.

**Core Architecture**: Pipeline-based processing with SQLite database tracking episodes through status workflows:
- RSS Audio: `pre-download` → `downloaded` → `transcribed` → `digested`  
- YouTube: `pre-download` → `transcribed` → `digested`

**Key Technologies**:
- **Parakeet MLX**: Apple Silicon-optimized ASR with 10-minute chunking
- **Faster-Whisper**: Cross-platform ASR (4x faster than OpenAI Whisper) for non-Apple Silicon
- **Claude Code Integration**: Headless CLI mode for content analysis
- **SQLite**: Episode database with status tracking
- **ffmpeg**: Audio processing pipeline
- **GitHub API**: Automated deployment and RSS publishing

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

# Generate Claude-powered digest
python3 claude_headless_integration.py

# Generate TTS audio digest
python3 claude_tts_generator.py

# Deploy to GitHub releases
python3 deploy_episode.py

# Update RSS feed
python3 rss_generator.py
```

### Requirements Management
```bash
# Install dependencies
pip install -r requirements.txt

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
1. **Feed Monitoring** (`feed_monitor.py`): RSS/YouTube discovery → database with `pre-download` status
2. **Content Processing** (`content_processor.py`): Audio download/transcription → `downloaded`/`transcribed` status  
3. **Claude Analysis** (`claude_headless_integration.py`): Process `transcribed` episodes → content analysis
4. **Publishing Pipeline**: TTS generation → GitHub deployment → RSS updates → `digested` status

### Database Schema
**Episodes table** tracks processing workflow:
- `episode_id`: 8-character hash identifier
- `status`: Workflow state (`pre-download`, `downloaded`, `transcribed`, `digested`, `failed`)
- `transcript_path`: Path to generated transcript file
- `priority_score`: Content importance (0.0-1.0)
- `content_type`: Classification (discussion, news, tutorial)

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
- Processes ONLY episodes with `status='transcribed'`
- Generates topic-organized daily digest
- Moves processed transcripts to `transcripts/digested/`
- Updates episode status to `digested`

### File Structure Logic
- `audio_cache/`: Downloaded audio files (cleaned after processing)
- `transcripts/`: Active transcript files ready for digest
- `transcripts/digested/`: Processed transcript files (archived)  
- `daily_digests/`: Generated audio digest files
- `api/`: Vercel deployment endpoints

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

## Common Issues

### Database Status Mismatches
Episodes may exist in `audio_cache` but not be marked `downloaded` in database. Use audio cache processing in main pipeline to reconcile.

### Transcription Performance
Parakeet MLX performance varies by file. Use `RobustTranscriber.estimate_transcription_time()` for planning. Large files automatically chunked into 10-minute segments.

### Claude Integration Requirements
- Claude Code CLI must be installed and available in PATH
- Episodes must have `status='transcribed'` to be included in digest
- Digest instructions in `claude_digest_instructions.md` control output format

### Environment Dependencies
- macOS: Use `./fix_malloc_warnings.sh` for Python malloc warnings
- ffmpeg required for audio format conversion  
- GitHub token required for deployment features
- ElevenLabs API key optional (TTS features only)