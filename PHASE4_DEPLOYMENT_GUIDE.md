# Phase 4: RSS Distribution & Vercel Deployment Guide

## Overview
Complete RSS hosting pipeline for Daily Tech Digest podcast on your existing paulrbrown.org Vercel site.

## Files Created
- `api/rss.py`: Vercel function serving RSS XML feed
- `api/audio/[episode].py`: Audio file serving endpoint  
- `rss_generator.py`: Local RSS generator for testing
- `generate_episode_metadata.py`: Creates metadata JSON for episodes
- `cleanup_old_episodes.py`: 7-day retention management
- `.github/workflows/deploy-rss.yml`: Automated deployment pipeline
- `vercel.json`: Vercel configuration

## Quick Setup Steps

### 1. Install Vercel CLI & Login
```bash
npm i -g vercel
vercel login
```

### 2. Test RSS Generation Locally
```bash
python3 generate_episode_metadata.py
python3 rss_generator.py
```

### 3. Deploy to Vercel
```bash
# Link to your existing paulrbrown.org project
vercel link

# Deploy
vercel --prod
```

### 4. Set Environment Variables
```bash
# Required for future GitHub Actions
vercel env add VERCEL_TOKEN
vercel env add VERCEL_PROJECT_ID
```

## RSS Feed URLs
- **RSS Feed**: `https://paulrbrown.org/daily-digest.xml`
- **Audio Files**: `https://paulrbrown.org/audio/[filename]`

## Podcast Directory Submission

### Google Podcasts (Android Default)
1. Go to Google Podcasts Manager: https://podcastsmanager.google.com/
2. Add your RSS URL: `https://paulrbrown.org/daily-digest.xml`
3. Verify ownership of paulrbrown.org domain

### Spotify
1. Go to Spotify for Podcasters: https://podcasters.spotify.com/
2. Submit RSS feed URL
3. Wait for review (1-7 days)

### Pocket Casts
1. Go to Pocket Casts Submit: https://www.pocketcasts.com/submit/
2. Submit RSS feed URL
3. Automatic inclusion if feed is valid

## Automation Pipeline

### Daily Process
1. **Local Generation**: Your existing `claude_tts_generator.py --topic-based` creates MP3
2. **GitHub Actions**: Detects new MP3 files, generates metadata, deploys to Vercel
3. **RSS Updates**: Feed automatically includes new episodes
4. **Retention**: Removes files >7 days old

### Manual Triggers
```bash
# Generate new episode
python3 claude_tts_generator.py --topic-based

# Test RSS feed
python3 generate_episode_metadata.py
python3 rss_generator.py

# Deploy manually
vercel --prod
```

## File Structure
```
podcast-scraper/
├── api/
│   ├── rss.py              # RSS XML generator
│   └── audio/[episode].py  # Audio file server
├── daily_digests/          # Generated MP3 files  
├── .github/workflows/
│   └── deploy-rss.yml      # Automated deployment
├── vercel.json             # Vercel config
└── episode_metadata.json  # Episode data for RSS
```

## Testing Checklist
- [ ] RSS XML validates at https://validator.w3.org/feed/
- [ ] Audio files accessible via URLs
- [ ] Podcast app can subscribe to feed
- [ ] New episodes appear automatically
- [ ] Old episodes removed after 7 days

## Next Steps
1. **Deploy**: Run setup steps above
2. **Test**: Subscribe to feed in your podcast app
3. **Automate**: Push new MP3 files to trigger deployment
4. **Submit**: Add to Google Podcasts and Spotify