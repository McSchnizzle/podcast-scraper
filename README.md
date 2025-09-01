# Daily Podcast Digest System

An automated system for monitoring, processing, and analyzing podcast content with AI-powered transcription, Claude-based content analysis, TTS generation with timestamp synchronization, and dual-database architecture.

## Overview

The Daily Podcast Digest System continuously monitors podcast RSS feeds and YouTube channels, automatically processes episodes using Apple Silicon optimized transcription, and generates comprehensive daily digests using Claude AI integration.

### Key Features

- **Dual-Database Architecture**: Separate SQLite databases for RSS (`podcast_monitor.db`) and YouTube (`youtube_transcripts.db`) episodes
- **TTS Timestamp Synchronization**: Perfect filename matching between digest markdown and generated MP3 files
- **Local YouTube Processing**: 6-hour cron job for YouTube transcript downloads with GitHub sync
- **Advanced Transcription**: Parakeet MLX ASR with Apple Silicon optimization (10-minute chunking)
- **Claude AI Integration**: Headless CLI mode for content analysis with embedded timestamps
- **ElevenLabs TTS**: High-quality audio generation with timestamp-matched filenames
- **GitHub Actions Automation**: RSS pipeline processing with intelligent Vercel build skipping
- **Smart Filtering**: Length-based filtering for YouTube content (>3 minutes)
- **Automated Publishing**: GitHub releases with MP3 hosting and RSS feed generation
- **Web API**: Vercel endpoints optimized for serverless deployment (<1MB functions)

## 📡 RSS Feed

**Daily Tech Digest RSS Feed**: https://podcast.paulrbrown.org/daily-digest.xml

Subscribe to receive automated daily digests featuring:
- AI-powered analysis of tech podcast content from RSS and YouTube sources
- High-quality TTS audio with ElevenLabs synthesis
- Perfect timestamp synchronization between digest files and MP3 episodes
- Cross-episode synthesis and trend identification
- GitHub-hosted MP3 files with CDN delivery

## System Architecture

### Phase 1: Feed Monitoring ✅ COMPLETE
- **RSS**: GitHub Actions pipeline with `podcast_monitor.db` tracking
- **YouTube**: Local cron job (6-hour intervals) with `youtube_transcripts.db` tracking
- **Database Sync**: Local processing commits transcripts and database to GitHub
- **GitHub Integration**: Actions workflow pulls latest changes before processing

### Phase 2: Content Processing Pipeline ✅ COMPLETE
- **YouTube**: Direct transcript API access with duration filtering
- **RSS Audio**: Advanced transcription using Parakeet MLX (10-minute chunks)
- **Content Analysis**: Priority scoring and content type classification
- **Quality Gates**: Processing validation and error handling

### Phase 3: Claude AI Analysis ✅ COMPLETE
- **Claude Code Integration**: Headless CLI mode processing both RSS and YouTube episodes
- **Timestamp Embedding**: Claude generates digest files with embedded timestamps
- **Daily Digest Generation**: Topic-based content summarization from dual databases
- **TTS Synchronization**: Claude timestamp extraction for perfect MP3 filename matching
- **Cross-Reference Analysis**: Episode correlation across RSS and YouTube sources

### Phase 4: Publishing Pipeline ✅ COMPLETE
- **TTS Generation**: ElevenLabs synthesis with timestamp-synchronized filenames
- **GitHub Releases**: MP3 and markdown files with matching timestamps
- **RSS Generation**: Links to GitHub-hosted MP3 files via paulrbrown.org URLs
- **Vercel Integration**: Intelligent build skipping prevents unnecessary deployments
- **Web API**: Audio streaming and RSS serving with smart caching

## Technical Stack

### Core Dependencies
- **Python 3.10+**: Core runtime environment
- **Dual SQLite Databases**: `podcast_monitor.db` (RSS) and `youtube_transcripts.db` (YouTube)
- **ffmpeg**: Audio format conversion and processing (RSS audio only)
- **Parakeet MLX**: Apple Silicon optimized ASR for RSS episodes
- **MLX Framework**: Apple Silicon native acceleration
- **Claude Code CLI**: Headless AI content analysis with timestamp extraction
- **ElevenLabs API**: High-quality TTS generation with timestamp synchronization
- **YouTube Transcript API**: Direct YouTube transcript access (local cron processing)
- **GitHub Actions**: Automated RSS pipeline and deployment
- **Vercel**: RSS serving with intelligent build skipping

### Processing Architecture
```
RSS Pipeline (GitHub Actions):
Feed Monitor → Audio Download → ffmpeg → Parakeet MLX (10min chunks) → 
podcast_monitor.db → Claude Analysis → TTS + Timestamp Sync → GitHub Release

YouTube Pipeline (Local + GitHub):
Local Cron (6h) → YouTube API → youtube_transcripts.db → Git Push →
GitHub Actions → Claude Analysis (combined) → TTS + Timestamp Sync
```

## Installation

### Prerequisites
```bash
# Install system dependencies (macOS)
brew install ffmpeg

# Install Python dependencies
pip install -r requirements-dev.txt

# Install Parakeet MLX for Apple Silicon optimization
pip install parakeet-mlx

# Install additional dependencies
pip install feedparser youtube-transcript-api python-dotenv

# Fix Python malloc warnings (optional)
./fix_malloc_warnings.sh
```

### Quick Setup
```bash
git clone https://github.com/McSchnizzle/podcast-scraper.git
cd podcast-scraper
pip install -r requirements-dev.txt

# Set environment variables  
export GITHUB_TOKEN="your_github_token"           # Required for releases
export ANTHROPIC_API_KEY="your_anthropic_key"     # Required for Claude CLI
export ELEVENLABS_API_KEY="your_elevenlabs_key"   # Required for TTS MP3 generation

# Set up YouTube cron job (local machine)
crontab -e
# Add: 0 */6 * * * /path/to/podcast-scraper/youtube_cron_job.sh
```

## Usage

### Main Pipeline
```bash
# Run complete daily pipeline
python3 daily_podcast_pipeline.py

# Available options
python3 daily_podcast_pipeline.py --help
```

### Individual Components
```bash
# Monitor feeds only
python3 feed_monitor.py

# Process pending episodes
python3 content_processor.py

# Generate Claude digest (processes both databases)
python3 claude_headless_integration.py

# Generate TTS audio with timestamp synchronization
python3 claude_tts_generator.py

# Check database status
python3 -c "import sqlite3; conn=sqlite3.connect('podcast_monitor.db'); print('RSS:', conn.execute('SELECT status, COUNT(*) FROM episodes GROUP BY status').fetchall()); conn.close()"
python3 -c "import sqlite3; conn=sqlite3.connect('youtube_transcripts.db'); print('YouTube:', conn.execute('SELECT status, COUNT(*) FROM episodes GROUP BY status').fetchall()); conn.close()"
```

## Configuration

### Feed Configuration
Add new podcast feeds in `config.py`:
```python
feeds = [
    {
        'title': 'Your Podcast Name',
        'url': 'https://example.com/rss',
        'type': 'rss',  # RSS feeds processed by GitHub Actions
        'topic_category': 'technology'  # or 'business', 'news'
    },
    {
        'title': 'YouTube Channel',
        'url': 'https://youtube.com/channel/UC...',
        'type': 'youtube',  # YouTube processed by local cron job
        'topic_category': 'technology'
    }
]
```

### Processing Parameters
- **YouTube Minimum Duration**: 3.0 minutes (configurable)
- **YouTube Cron Schedule**: Every 6 hours (0 */6 * * *)
- **Audio Chunking**: 10 minutes per chunk for RSS episodes
- **TTS Timestamp Sync**: Regex extraction from `daily_digest_YYYYMMDD_HHMMSS.md`
- **Database Tracking**: Separate status workflows for RSS and YouTube
- **Audio Cache**: RSS downloads in `audio_cache/` (cleaned after processing)
- **Transcript Storage**: Combined RSS+YouTube in `transcripts/` and `transcripts/digested/`

## Performance Metrics

### Parakeet MLX Performance
- **Speed**: ~0.18x RTF (Real-Time Factor) - optimized for quality
- **Quality**: Superior podcast-specific accuracy
- **Apple Silicon**: Native Metal acceleration
- **Chunking**: 10-minute segments for optimal processing

### Processing Efficiency
- **YouTube**: Instant transcript access via API
- **RSS Audio**: High-quality transcription with 10-minute chunking
- **Claude Analysis**: Automated content analysis and digest generation
- **Database Operations**: Optimized SQLite queries with status tracking

## File Structure

```
podcast-scraper/
├── README.md                   # This file
├── CLAUDE.md                   # Technical documentation for Claude Code ⭐
├── podscraper_prd.md          # Product Requirements Document
├── requirements-dev.txt        # Python dependencies (development)
├── config.py                   # Centralized configuration management ⭐
├── fix_malloc_warnings.sh     # macOS malloc warning fix
├── daily_podcast_pipeline.py  # Main RSS pipeline orchestration ⭐
├── feed_monitor.py            # RSS feed monitoring (GitHub Actions)
├── content_processor.py       # RSS audio transcription pipeline
├── claude_headless_integration.py # Claude AI analysis (dual database)
├── robust_transcriber.py      # Advanced transcription engine
├── claude_tts_generator.py    # TTS with timestamp synchronization ⭐
├── youtube_processor.py       # YouTube transcript processing (local)
├── youtube_cron_job.sh        # 6-hour YouTube cron automation ⭐
├── deploy_episode.py          # GitHub release deployment
├── rss_generator.py           # RSS feed generation
├── vercel.json                # Vercel configuration with build skipping ⭐
├── vercel-build-ignore.sh     # Intelligent Vercel build skipping ⭐
├── .github/workflows/
│   └── daily-podcast-pipeline.yml # GitHub Actions automation ⭐
├── api/
│   ├── rss.py                 # RSS endpoint (Vercel)
│   └── audio/[episode].py     # Audio streaming endpoint (Vercel)
├── claude_digest_instructions.md # Claude AI digest generation instructions
├── podcast_monitor.db          # RSS episodes SQLite database ⭐
├── youtube_transcripts.db      # YouTube episodes SQLite database ⭐
├── daily-digest.xml           # Generated RSS feed
├── audio_cache/               # Downloaded RSS audio files (temporary)
├── transcripts/               # Active transcript files (RSS + YouTube)
├── transcripts/digested/      # Processed transcript files (archived)
└── daily_digests/            # Generated digest files with timestamp sync
    ├── daily_digest_YYYYMMDD_HHMMSS.md      # Claude-generated digest
    ├── claude_digest_full_YYYYMMDD_HHMMSS.txt # Full TTS script
    ├── claude_digest_tts_YYYYMMDD_HHMMSS.txt  # TTS-optimized script
    ├── complete_topic_digest_YYYYMMDD_HHMMSS.mp3 # Generated MP3 ⭐
    └── complete_topic_digest_YYYYMMDD_HHMMSS.json # Audio metadata
```

## Current Status

### ✅ Completed Features
- **Dual-Database Architecture**: Separate RSS and YouTube episode tracking
- **TTS Timestamp Synchronization**: Perfect filename matching between digest markdown and MP3 files
- **Local YouTube Processing**: 6-hour cron job with GitHub synchronization
- **GitHub Actions Integration**: Automated RSS pipeline with dual-database processing
- **ElevenLabs TTS**: High-quality audio generation with timestamp extraction
- **Vercel Intelligence**: Smart build skipping prevents unnecessary deployments
- **Advanced Transcription**: Parakeet MLX with 10-minute chunking for RSS episodes
- **Claude AI Integration**: Headless CLI mode processing both episode sources
- **GitHub Releases**: MP3 and markdown file hosting with CDN delivery
- **RSS Feed Generation**: Links to GitHub-hosted MP3 files via paulrbrown.org

### 🔄 Recent Updates
- **TTS Timestamp Fix**: Resolved timestamp mismatch between digest markdown and MP3 files
- **Dual-Database Implementation**: Separate tracking for RSS and YouTube episodes  
- **Local YouTube Cron**: 6-hour automated YouTube transcript processing
- **GitHub Actions Enhancement**: Added comprehensive TTS debugging and database sync
- **Vercel Decoupling**: Intelligent build skipping prevents unnecessary deployments
- **Database Sync Resolution**: Fixed GitHub Actions database caching issues
- **Perfect TTS Integration**: ElevenLabs generation with timestamp-synchronized filenames
- **Enhanced Error Handling**: Comprehensive debugging and troubleshooting workflows

### 📋 Future Enhancements
- Enhanced speaker diarization with timestamps
- Advanced topic extraction and categorization
- Web interface for content management
- Multi-language support
- Performance monitoring dashboard

## Development

### Core Files
1. **`daily_podcast_pipeline.py`** - Main orchestration and automation
2. **`feed_monitor.py`** - RSS/YouTube monitoring
3. **`content_processor.py`** - Transcription pipeline
4. **`claude_headless_integration.py`** - AI analysis
5. **`robust_transcriber.py`** - Transcription engine

### Episode Processing Workflow
```
RSS Workflow (GitHub Actions):
Feed Monitor → podcast_monitor.db → pre-download → downloaded → transcribed → digested

YouTube Workflow (Local + GitHub):
Local Cron → youtube_transcripts.db → transcribed → Git Push → GitHub Actions → digested

TTS Synchronization:
Claude: daily_digest_YYYYMMDD_HHMMSS.md → TTS: complete_topic_digest_YYYYMMDD_HHMMSS.mp3
```

## Troubleshooting

### Common Issues

**Database Sync Issues**: Always `git pull` before local work
```bash
git pull
sqlite3 podcast_monitor.db "SELECT status, COUNT(*) FROM episodes GROUP BY status;"
sqlite3 youtube_transcripts.db "SELECT status, COUNT(*) FROM episodes GROUP BY status;"
```

**TTS Timestamp Mismatch**: Check digest filename format and TTS extraction
```bash
# Verify digest files exist with correct naming
ls daily_digests/daily_digest_*.md
# Check TTS script for timestamp extraction
python3 claude_tts_generator.py
```

**YouTube Cron Failures**: Verify cron job and execution
```bash
crontab -l  # Check cron job exists
./youtube_cron_job.sh  # Test manual execution
```

**Vercel Build Issues**: Configure ignore script in Vercel dashboard
- Settings → Git → Ignored Build Step: `./vercel-build-ignore.sh`

**macOS Malloc Warnings**: Run `./fix_malloc_warnings.sh`

**Missing Dependencies**: 
```bash
pip install parakeet-mlx feedparser youtube-transcript-api anthropic
```

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- **ASR Technology**: NVIDIA Parakeet models via MLX framework
- **AI Integration**: Claude Code for content analysis
- **Apple Silicon Optimization**: `parakeet-mlx` framework
- **Inspiration**: Modern podcast processing and AI content analysis

---

**Production-ready podcast processing with Apple Silicon optimization and Claude AI integration**