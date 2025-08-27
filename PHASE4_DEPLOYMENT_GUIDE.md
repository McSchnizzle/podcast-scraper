# Phase 4: RSS Distribution & Vercel Deployment - COMPLETE ✅

## Overview
Complete RSS hosting pipeline for Daily Tech Digest podcast deployed on Vercel with working audio downloads.

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

## Live RSS Feed URLs ✅

**PRODUCTION FEED** (Ready for podcast apps):
- **RSS Feed**: `https://podcast-scraper-kxxvl6bnx-paul-browns-projects-cf5d21b4.vercel.app/daily-digest.xml`
- **Audio Files**: `https://podcast-scraper-kxxvl6bnx-paul-browns-projects-cf5d21b4.vercel.app/audio/[filename]`

**Status**: 
- ✅ RSS feed validates with 2 episodes
- ✅ Audio downloads working (10MB+ MP3s)
- ✅ Tested in Podcast Addict successfully

## Podcast Directory Submission

### Google Podcasts (Android Default)
1. Go to Google Podcasts Manager: https://podcastsmanager.google.com/
2. Add your RSS URL: `https://podcast-scraper-kxxvl6bnx-paul-browns-projects-cf5d21b4.vercel.app/daily-digest.xml`
3. Verify ownership or use direct RSS submission

### Spotify
1. Go to Spotify for Podcasters: https://podcasters.spotify.com/
2. Submit RSS feed URL: `https://podcast-scraper-kxxvl6bnx-paul-browns-projects-cf5d21b4.vercel.app/daily-digest.xml`
3. Wait for review (1-7 days)

### Pocket Casts
1. Go to Pocket Casts Submit: https://www.pocketcasts.com/submit/
2. Submit RSS feed URL: `https://podcast-scraper-kxxvl6bnx-paul-browns-projects-cf5d21b4.vercel.app/daily-digest.xml`
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
│   ├── rss.py              # RSS XML generator (Vercel function)
│   └── audio/[episode].py  # Audio file server (fallback)
├── public/audio/           # Static MP3 files (primary serving)
├── daily_digests/          # Source MP3 files  
├── .github/workflows/
│   └── deploy-rss.yml      # Automated deployment
├── vercel.json             # Vercel config
└── episode_metadata.json  # Episode data for RSS
```

## Testing Checklist ✅
- [x] RSS XML validates at https://validator.w3.org/feed/
- [x] Audio files accessible via URLs (10MB+ streaming)
- [x] Podcast app can subscribe to feed (Podcast Addict tested)
- [x] Episodes download successfully in podcast apps
- [ ] New episodes appear automatically (GitHub Actions)
- [ ] Old episodes removed after 7 days (retention system)

## Deployment Complete ✅

**LIVE RSS FEED**: `https://podcast-scraper-kxxvl6bnx-paul-browns-projects-cf5d21b4.vercel.app/daily-digest.xml`

### What Works Now:
1. ✅ **RSS Feed**: Live and accessible to podcast apps
2. ✅ **Audio Downloads**: 10MB+ MP3s streaming correctly  
3. ✅ **Podcast Apps**: Successfully tested in Podcast Addict
4. ✅ **Static Serving**: MP3s served from `public/audio/` directory

### Next Steps:
1. **Submit to Directories**: Use RSS URL above for Google Podcasts, Spotify, Pocket Casts
2. **Automation**: Set up GitHub Actions for automatic deployment of new episodes
3. **Domain**: Optional - configure custom domain if desired
4. **Monitoring**: Set up RSS feed monitoring and analytics