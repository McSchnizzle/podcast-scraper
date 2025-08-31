# 🎧 Dual Database Architecture for YouTube + RSS Processing

This architecture solves the **YouTube API blocking in GitHub Actions** by splitting processing between local and cloud environments while maintaining seamless integration.

## 🏗️ **Architecture Overview**

### **Database Split**
- **`podcast_monitor.db`** (GitHub Actions) - RSS feeds only
- **`youtube_transcripts.db`** (Local machine) - YouTube feeds only  
- **Digest generation** reads from both databases seamlessly

### **Processing Split**
- **GitHub Actions** (Cloud) - Handles RSS feeds (no IP blocking issues)
- **Local Machine** (Your computer) - Handles YouTube feeds (no IP restrictions)
- **Shared Git Repository** - Synchronizes databases and transcripts

## 🔄 **Workflow**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   LOCAL MACHINE │    │   GIT REPOSITORY │    │ GITHUB ACTIONS  │
│                 │    │                 │    │                 │
│ YouTube         │◄──►│ Sync databases  │◄──►│ RSS Processing  │
│ Processing      │    │ & transcripts   │    │ + Digest Gen    │
│                 │    │                 │    │                 │
│ Every 6 hours   │    │ Commits/pulls   │    │ Daily workflow  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🛠️ **Setup Instructions**

### **1. Initialize YouTube Database**
```bash
# Create YouTube database and sync feeds
python3 youtube_processor.py --sync-feeds

# Test YouTube processing
python3 youtube_processor.py --process-new --hours-back 24
```

### **2. Setup Local Automation**
```bash
# Setup automated YouTube processing (macOS/Linux)
python3 setup_youtube_automation.py

# This creates:
# - macOS: LaunchAgent (runs every 6 hours)
# - Linux: Crontab entry (runs every 6 hours)  
# - Git automation script
```

### **3. Update GitHub Actions**
The workflow now uses `--rss-only` mode:
```yaml
- name: Run RSS-only podcast pipeline
  run: python3 daily_podcast_pipeline.py --rss-only
```

## 📊 **Management Commands**

### **YouTube Processing (Local)**
```bash
# Process new YouTube episodes
python3 youtube_processor.py --process-new

# Check YouTube stats
python3 youtube_processor.py --stats

# Sync YouTube feeds from config
python3 youtube_processor.py --sync-feeds

# Manual git sync
./youtube_git_automation.sh
```

### **Feed Management**
```bash
# List all feeds (both databases)
python3 manage_feeds.py list

# Add new feed (automatically goes to correct database)
python3 manage_feeds.py add

# Remove feed
python3 manage_feeds.py remove
```

### **Pipeline Testing**
```bash
# Test RSS-only mode (GitHub Actions simulation)
python3 daily_podcast_pipeline.py --rss-only

# Test complete workflow (local)
python3 daily_podcast_pipeline.py --run

# Check system status
python3 daily_podcast_pipeline.py --status
```

## 📁 **File Structure**

### **New Files**
- `youtube_processor.py` - Local YouTube processing
- `youtube_transcripts.db` - YouTube-specific database
- `setup_youtube_automation.py` - Local automation setup
- `youtube_git_automation.sh` - Git sync script (auto-generated)
- `manage_feeds.py` - Feed management CLI

### **Modified Files**
- `claude_api_integration.py` - Reads from both databases
- `daily_podcast_pipeline.py` - Added `--rss-only` mode
- `content_processor.py` - Enhanced YouTube error handling
- `.github/workflows/daily-podcast-pipeline.yml` - Uses `--rss-only`
- `config.py` - Database management functions

## 🎯 **Workflow Details**

### **Local Workflow (Every 6 hours)**
1. **YouTube Processing**: Download new YouTube episodes and generate transcripts
2. **Database Update**: Store episodes in `youtube_transcripts.db`
3. **Git Commit**: Commit database and transcripts to GitHub
4. **Status Logging**: Log processing results

### **GitHub Actions Workflow (Daily)**
1. **Git Pull**: Get latest YouTube data from local processing
2. **RSS Processing**: Handle RSS feeds (no blocking issues)
3. **Digest Generation**: Create digest from BOTH databases 
4. **Publishing**: Generate TTS, deploy to releases, update RSS feed
5. **Cleanup**: Mark episodes as digested in both databases

## 🔍 **Troubleshooting**

### **YouTube Processing Issues**
```bash
# Check YouTube stats
python3 youtube_processor.py --stats

# View logs (macOS)
tail -f logs/youtube_processor.log

# Manually sync feeds
python3 youtube_processor.py --sync-feeds
```

### **Database Issues**
```bash
# Check RSS database
sqlite3 podcast_monitor.db "SELECT status, COUNT(*) FROM episodes GROUP BY status;"

# Check YouTube database  
sqlite3 youtube_transcripts.db "SELECT status, COUNT(*) FROM episodes GROUP BY status;"
```

### **GitHub Actions Issues**
- Check that `youtube_transcripts.db` exists in repository
- Verify `--rss-only` mode works locally
- Check GitHub Actions logs for specific errors

## ✅ **Benefits of This Architecture**

1. **No YouTube API Blocking** - Local processing avoids GitHub Actions IP restrictions
2. **Reliable RSS Processing** - GitHub Actions handles RSS feeds without issues
3. **Unified Digests** - Single digest combines content from both sources
4. **Zero Additional Costs** - Uses existing infrastructure efficiently
5. **Independent Operation** - RSS processing continues even if YouTube fails
6. **Easy Management** - CLI tools for feed and database management
7. **Automated Sync** - Git keeps everything synchronized

## 🚀 **Next Steps**

1. Run `python3 setup_youtube_automation.py` to set up local automation
2. Test the complete workflow end-to-end
3. Monitor logs to ensure everything works smoothly
4. Add more feeds using `python3 manage_feeds.py add`

The system is now ready to handle both RSS and YouTube feeds reliably!