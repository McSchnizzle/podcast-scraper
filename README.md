# Daily Podcast Digest System

An automated system for monitoring, processing, and analyzing podcast content with AI-powered transcription, Claude-based content analysis, and automated digest generation.

## Overview

The Daily Podcast Digest System continuously monitors podcast RSS feeds and YouTube channels, automatically processes episodes using Apple Silicon optimized transcription, and generates comprehensive daily digests using Claude AI integration.

### Key Features

- **Multi-Source Monitoring**: RSS feeds and YouTube channels with intelligent feed management
- **Advanced Transcription**: Parakeet MLX ASR with Apple Silicon optimization (10-minute chunking)
- **Claude AI Integration**: Automated content analysis and digest generation via Claude Code
- **Speaker Detection**: Multi-speaker conversation detection and analysis
- **Smart Filtering**: Length-based filtering for YouTube content (>3 minutes)
- **Automated Publishing**: RSS generation and GitHub deployment pipeline
- **Web API**: Endpoints for audio streaming and RSS feed serving
- **Dual Status Workflow**: RSS (pre-download→downloaded→transcribed→digested) and YouTube (pre-download→transcribed→digested)

## System Architecture

### Phase 1: Feed Monitoring ✅ COMPLETE
- RSS feed parsing and episode discovery
- YouTube channel monitoring via RSS
- SQLite database for episode tracking
- Automated feed updates and new episode detection

### Phase 2: Content Processing Pipeline ✅ COMPLETE
- **YouTube**: Direct transcript API access with duration filtering
- **RSS Audio**: Advanced transcription using Parakeet MLX (10-minute chunks)
- **Content Analysis**: Priority scoring and content type classification
- **Quality Gates**: Processing validation and error handling

### Phase 3: Claude AI Analysis ✅ COMPLETE
- **Claude Code Integration**: Headless Claude integration for content analysis
- **Daily Digest Generation**: Automated topic-based content summarization
- **Cross-Reference Analysis**: Episode correlation and theme detection
- **Topic Organization**: Intelligent content grouping and prioritization

### Phase 4: Publishing Pipeline ✅ COMPLETE
- **RSS Generation**: Automated podcast RSS feed creation
- **GitHub Deployment**: Automated episode publishing and release management
- **Web API**: Audio streaming and RSS serving endpoints

## Technical Stack

### Core Dependencies
- **Python 3.10+**: Core runtime environment
- **SQLite**: Episode database and metadata storage
- **ffmpeg**: Audio format conversion and processing
- **Parakeet MLX**: Apple Silicon optimized ASR
- **MLX Framework**: Apple Silicon native acceleration
- **Claude Code**: AI content analysis and digest generation
- **YouTube Transcript API**: Direct YouTube transcript access

### Audio Processing Pipeline
```
RSS Audio → Download → ffmpeg conversion → Parakeet MLX (10min chunks) → Claude Analysis
YouTube → Direct API → Transcript → Claude Analysis
```

## Installation

### Prerequisites
```bash
# Install system dependencies (macOS)
brew install ffmpeg

# Install Python dependencies
pip install -r requirements.txt

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
pip install -r requirements.txt

# Set environment variables
export GITHUB_TOKEN="your_github_token"
export ELEVENLABS_API_KEY="your_elevenlabs_key"  # Optional
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

# Generate Claude digest
python3 claude_headless_integration.py

# Generate audio digest (if TTS configured)
python3 claude_tts_generator.py
```

## Configuration

### Feed Configuration
Add new podcast feeds in `feed_monitor.py`:
```python
feeds = [
    {
        'title': 'Your Podcast Name',
        'url': 'https://example.com/rss',
        'type': 'rss',  # or 'youtube'
        'topic_category': 'technology'  # or 'business', 'news'
    }
]
```

### Processing Parameters
- **YouTube Minimum Duration**: 3.0 minutes (configurable)
- **Audio Chunking**: 10 minutes per chunk (updated from 5 minutes)
- **Content Priority Threshold**: 0.3 (adjustable)
- **Audio Cache**: Persistent storage in `audio_cache/` directory
- **Transcript Storage**: Text files in `transcripts/` and `transcripts/digested/`

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
├── podscraper_prd.md          # Product Requirements Document
├── requirements.txt            # Python dependencies (updated)
├── config.py                   # Centralized configuration management ⭐
├── fix_malloc_warnings.sh     # macOS malloc warning fix
├── daily_podcast_pipeline.py  # Main orchestration script ⭐
├── feed_monitor.py            # RSS/YouTube feed monitoring
├── content_processor.py       # Audio transcription and processing
├── claude_headless_integration.py # Claude AI analysis
├── robust_transcriber.py      # Advanced transcription engine
├── claude_tts_generator.py    # Consolidated TTS + topic compilation ⭐
├── deploy_episode.py          # GitHub deployment
├── rss_generator.py           # RSS feed generation
├── api/
│   ├── rss.py                 # RSS endpoint
│   └── audio/[episode].py     # Audio streaming endpoint
├── claude_digest_instructions.md # Claude AI digest generation instructions
├── docs/                      # Documentation and guides
│   ├── podcast-workflow.md
│   ├── PHASE3_TTS_GUIDE.md
│   ├── PHASE4_DEPLOYMENT_GUIDE.md
│   └── refactor-complete-workflow.md
├── podcast_monitor.db          # SQLite database
├── audio_cache/               # Downloaded audio files
├── transcripts/               # Active transcript files
├── transcripts/digested/      # Processed transcript files
└── daily_digests/            # Generated audio digests
```

## Current Status

### ✅ Completed Features
- Multi-source feed monitoring (RSS + YouTube)
- Advanced audio transcription with 10-minute chunking
- Claude AI integration for content analysis
- Automated daily digest generation
- GitHub deployment pipeline
- RSS feed generation and serving
- Web API endpoints for audio and RSS
- Database status tracking (transcribed → digested workflow)

### 🔄 Recent Updates
- **Streamlined Codebase**: Reduced from 28 to 10 Python files
- **Fixed Database Sync**: Resolved transcript status mismatches
- **Improved Chunking**: Updated to 10-minute audio segments
- **macOS Compatibility**: Added malloc warning fix script
- **Enhanced Deployment**: Fixed GitHub release handling for existing releases
- **RSS Feed Reliability**: Fixed episode detection and publication to podcast.paulrbrown.org

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
RSS Audio:    pre-download → downloaded → transcribed → digested
YouTube:      pre-download → transcribed → digested
```

## Troubleshooting

### Common Issues

**macOS Malloc Warnings**: Run `./fix_malloc_warnings.sh`

**Missing Dependencies**: 
```bash
pip install parakeet-mlx feedparser youtube-transcript-api
```

**Database Issues**: Episodes are automatically tracked with proper status transitions

**Audio Processing**: Ensure ffmpeg is installed and accessible

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- **ASR Technology**: NVIDIA Parakeet models via MLX framework
- **AI Integration**: Claude Code for content analysis
- **Apple Silicon Optimization**: `parakeet-mlx` framework
- **Inspiration**: Modern podcast processing and AI content analysis

---

**Production-ready podcast processing with Apple Silicon optimization and Claude AI integration**