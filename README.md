# Daily Podcast Digest System

An automated system for monitoring, processing, and analyzing podcast content across multiple feeds with advanced AI-powered transcription and content analysis.

## Overview

The Daily Podcast Digest System continuously monitors podcast RSS feeds and YouTube channels, automatically processes new episodes, and extracts high-priority content using advanced speech recognition and AI analysis.

### Key Features

- **Multi-Source Monitoring**: RSS feeds and YouTube channels with intelligent feed management
- **Advanced Transcription**: NVIDIA Parakeet ASR with Apple Silicon optimization for superior podcast quality
- **Content Analysis**: AI-powered priority scoring and content categorization
- **Speaker Detection**: Basic multi-speaker conversation detection
- **Smart Filtering**: Length-based filtering for YouTube content (>3 minutes)
- **Cross-Reference Detection**: Automatic duplicate content identification across sources

## System Architecture

### Phase 1: Feed Monitoring ✅
- RSS feed parsing and episode discovery
- YouTube channel monitoring via RSS
- SQLite database for episode tracking
- Automated feed updates and new episode detection

### Phase 2: Content Processing Pipeline ✅
- **YouTube**: Direct transcript API access with duration filtering
- **RSS Audio**: Advanced transcription using NVIDIA Parakeet ASR
- **Content Analysis**: Priority scoring and content type classification
- **Quality Gates**: Processing validation and error handling

### Phase 2.5: Parakeet ASR Integration ✅ (Current)
- **Apple Silicon Optimized**: Uses `parakeet-mlx` for native M-series chip acceleration
- **Production Quality**: Superior podcast transcription vs. general speech models
- **Speaker Detection**: Basic multi-speaker conversation identification
- **Fallback Strategy**: Whisper backup for compatibility

### Phase 3: TTS Generation (Planned)
- Text-to-speech generation for audio summaries
- Daily digest compilation
- Distribution pipeline

## Technical Stack

### Core Dependencies
- **Python 3.10+**: Core runtime environment
- **SQLite**: Episode database and metadata storage
- **ffmpeg**: Audio format conversion and processing
- **Parakeet MLX**: Apple Silicon optimized ASR (primary)
- **OpenAI Whisper**: Fallback ASR engine
- **YouTube Transcript API**: Direct YouTube transcript access

### Audio Processing Pipeline
```
RSS Audio → Download → ffmpeg conversion → Parakeet MLX → Content Analysis
YouTube → Direct API → Transcript → Content Analysis
```

### ASR Engine Selection
- **Primary**: Parakeet MLX (Apple Silicon native, 3380 RTFx performance)
- **Fallback**: OpenAI Whisper (universal compatibility)
- **Auto-Detection**: Graceful fallback with capability detection

## Installation

### Prerequisites
```bash
# Install system dependencies (macOS)
brew install ffmpeg

# Install Python dependencies
pip install -r requirements.txt

# Install Parakeet MLX for Apple Silicon optimization
pip install parakeet-mlx

# Install Whisper as fallback
pip install openai-whisper
```

### Quick Setup
```bash
git clone https://github.com/McSchnizzle/podcast-scraper.git
cd podcast-scraper
pip install -r requirements.txt
python3 pipeline.py setup
```

## Usage

### Basic Operation
```bash
# Run complete pipeline (monitoring + processing)
python3 pipeline.py run

# Monitor feeds only
python3 feed_monitor.py

# Process pending episodes
python3 content_processor.py

# Analyze existing content
python3 content_analyzer.py
```

### Content Processing
```bash
# Process specific episode
python3 -c "
from content_processor import ContentProcessor
processor = ContentProcessor()
result = processor.process_episode(episode_id)
"

# Get high-priority content
python3 -c "
from content_processor import ContentProcessor
processor = ContentProcessor()
episodes = processor.get_processed_episodes(min_priority=0.5)
for ep in episodes:
    print(f'{ep['title']} - Priority: {ep['priority_score']:.2f}')
"
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
- **Content Priority Threshold**: 0.3 (adjustable)
- **Audio Cache**: Persistent storage in `audio_cache/` directory
- **Transcript Storage**: Text files in `transcripts/` directory

## Current Status

### Processed Content (As of Aug 26, 2024)
- **Total Episodes Monitored**: 31
- **YouTube Episodes Processed**: 3 (substantial content >3 min)
- **RSS Episodes Pending**: 22 (ready for Parakeet processing)
- **High-Priority Content**: Multiple episodes with >0.5 priority score

### Feed Sources
- **Technology**: THIS IS REVOLUTION podcast, tech-focused channels
- **Business**: The Diary Of A CEO, business interview content
- **News/Politics**: The Red Nation Podcast, The Malcolm Effect
- **Multiple YouTube Channels**: Tech talks and interviews

## Performance Metrics

### Parakeet MLX Advantages
- **Speed**: 3380 RTFx (transcribes 56 minutes in 1 second with batch processing)
- **Quality**: Superior podcast-specific accuracy vs. general speech models
- **Apple Silicon**: Native Metal acceleration, optimal for M-series chips
- **Memory**: Efficient processing with 2GB+ RAM requirements

### Processing Efficiency
- **YouTube**: Instant transcript access via API
- **RSS Audio**: High-quality transcription with Parakeet MLX
- **Content Analysis**: Real-time priority scoring and categorization
- **Database Operations**: Optimized SQLite queries and indexing

## File Structure

```
podcast-scraper/
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── pipeline.py                 # Main orchestration script
├── feed_monitor.py            # RSS/YouTube feed monitoring
├── content_processor.py       # Audio transcription and processing
├── content_analyzer.py        # Content analysis and insights
├── podscraper_prd.md         # Product Requirements Document
├── podcast_monitor.db         # SQLite database
├── audio_cache/              # Downloaded audio files
├── transcripts/              # Generated transcript files
└── test_*.py                 # Testing utilities
```

## Development Status

### ✅ Completed Features
- Multi-source feed monitoring (RSS + YouTube)
- YouTube transcript processing with duration filtering  
- Advanced content analysis pipeline
- SQLite database with comprehensive episode tracking
- Parakeet MLX ASR integration for Apple Silicon
- Basic speaker detection and conversation analysis
- Error handling and graceful fallbacks

### 🔄 Current Development
- **Phase 2.5**: Parakeet ASR integration and RSS processing optimization
- Quality validation of Parakeet vs. Whisper transcription accuracy
- Performance optimization for batch processing

### 📋 Planned Features
- **Phase 3**: TTS generation for daily audio digests
- Advanced speaker diarization with timestamps
- Enhanced content categorization and topic extraction
- Web interface for content management
- Distribution pipeline for generated digests

## Contributing

This project follows a phased development approach:

1. **Fork the repository**
2. **Create feature branch** for your phase/feature
3. **Follow existing code patterns** and conventions
4. **Update PRD documentation** with your changes
5. **Test with existing episode database**
6. **Submit pull request** with detailed description

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- **Inspiration**: Tomasz Tunguz's podcast processing system
- **ASR Technology**: NVIDIA Parakeet models via MLX framework
- **Apple Silicon Optimization**: `parakeet-mlx` by senstella
- **Fallback ASR**: OpenAI Whisper for universal compatibility

---

**Built with Apple Silicon optimization for production-quality podcast transcription**