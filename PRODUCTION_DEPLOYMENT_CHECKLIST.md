# Production Deployment Checklist

**🎯 MISSION-CRITICAL: Complete Production Hardening Checklist**

This checklist addresses all critical issues identified in the security review and ensures bulletproof production deployment.

## 🔒 Critical Security Issues (MUST FIX)

### 1. GUID Immutability ❌ CRITICAL
**Issue**: GUIDs use runtime timestamp, causing same content to produce different GUIDs on re-runs.

**Current**: `MD5(topic + runtime_timestamp)` → Different GUIDs for same logical episode
**Required**: Content-based stable GUIDs

**✅ Solution Implemented**:
```python
# Use new production configuration
from config.production import get_stable_guid

# Generate stable GUID based on content
stable_guid = get_stable_guid(topic, episode_ids, canonical_date)
```

**Verification**:
```bash
python3 -c "from config.production import get_stable_guid; print(get_stable_guid('AI News', ['ep1', 'ep2'], '2025-09-04'))"
# Should produce identical GUID when run multiple times
```

### 2. Base URL Configuration ❌ CRITICAL
**Issue**: Base URLs hardcoded in multiple places, risk of dev URLs in production feed.

**Current**: Hardcoded `https://paulrbrown.org` in 3+ files
**Required**: Environment-driven configuration with validation

**✅ Solution Implemented**:
```bash
# Set environment variables
export PODCAST_BASE_URL=https://podcast.paulrbrown.org
export AUDIO_BASE_URL=https://paulrbrown.org/audio
export ENVIRONMENT=production
```

**Verification**:
```bash
python3 -c "from config.production import production_config; print(production_config.PODCAST_BASE_URL)"
```

### 3. Time Zone Policy ❌ CRITICAL  
**Issue**: Mixed UTC/local time usage causes DST edge cases.

**Current**: Pipeline uses `datetime.now()`, RSS uses UTC
**Required**: All operations in UTC

**✅ Solution Implemented**:
```python
from config.production import get_utc_now, format_rss_date, get_weekday_label

# All datetime operations now use UTC
current_time = get_utc_now()
rss_date = format_rss_date(current_time)
weekday = get_weekday_label(current_time)
```

## 🛡️ Security Hardening (HIGH PRIORITY)

### 4. Enhanced Input Validation
**✅ Implemented**: `security/validation.py`
- Path traversal prevention
- XML injection protection  
- Resource exhaustion limits
- Content sanitization

**Verification**:
```bash
python3 -c "from security.validation import validate_filename_secure; print(validate_filename_secure('../../../etc/passwd'))"
# Should return (False, 'sanitized_filename')
```

### 5. RSS Specification Conformance
**Requirements**:
- `<guid isPermaLink="false">` ✅
- Consistent `<pubDate>` in UTC ✅
- `<enclosure length>` matches file size ✅
- `<atom:link rel="self">` present ✅
- `<lastBuildDate>` monotonic ✅

**✅ Solution**: Use `rss_generator_production.py`

## 🔧 Configuration Management

### 6. Environment Variables (REQUIRED)
```bash
# Base URLs
export PODCAST_BASE_URL=https://podcast.paulrbrown.org
export AUDIO_BASE_URL=https://paulrbrown.org/audio

# Environment
export ENVIRONMENT=production

# API Keys
export OPENAI_API_KEY=sk-...
export ELEVENLABS_API_KEY=...  # Optional for TTS
export GITHUB_TOKEN=ghp_...

# Quota Limits
export OPENAI_DAILY_TOKEN_LIMIT=50000
export YOUTUBE_DAILY_REQUEST_LIMIT=1000
export MAX_EPISODES_PER_RUN=20
```

### 7. Security Environment Variables
```bash
# Security settings
export ENABLE_SECURITY_VALIDATION=true
export MAX_FILE_SIZE_MB=100
export MAX_CONTENT_LENGTH=50000
```

## 🧪 Pre-Deployment Testing

### 8. Run Production Hardening Tests
```bash
# Comprehensive hardening validation
python3 tests/production_hardening.py

# Verify all critical tests pass
# Target: >95% security score, 0 critical failures
```

### 9. RSS Feed Validation
```bash
# Test production RSS generator
python3 rss_generator_production.py

# Validate with external tools
curl -s https://validator.w3.org/feed/check.cgi?url=https://your-domain.com/daily-digest.xml

# Test in podcast apps
# - Apple Podcasts
# - Pocket Casts  
# - Overcast
```

### 10. GUID Stability Test
```bash
# Generate RSS twice, verify identical GUIDs
python3 rss_generator_production.py
cp daily-digest-production.xml rss1.xml

sleep 5

python3 rss_generator_production.py  
cp daily-digest-production.xml rss2.xml

# Compare GUIDs (should be identical)
diff <(grep '<guid' rss1.xml) <(grep '<guid' rss2.xml)
```

## 🚀 Deployment Steps

### 11. GitHub Actions Environment
```yaml
# Add to .github/workflows/daily-podcast-pipeline.yml
env:
  PODCAST_BASE_URL: https://podcast.paulrbrown.org
  AUDIO_BASE_URL: https://paulrbrown.org/audio
  ENVIRONMENT: production
  ENABLE_SECURITY_VALIDATION: true
```

### 12. Production Pipeline Switch
```python
# Update daily_podcast_pipeline.py to use production components
from rss_generator_production import ProductionRSSGenerator
from config.production import production_config, validate_quota_usage
from security.validation import security_validator
```

### 13. DNS and CDN Configuration
- ✅ Configure `podcast.paulrbrown.org` → GitHub Pages
- ✅ Configure `paulrbrown.org/audio/*` → GitHub Releases
- ✅ Enable HTTPS/SSL certificates
- ✅ Set up CDN caching rules

## 📊 Monitoring and Alerting

### 14. Health Checks
```bash
# RSS feed accessibility
curl -f https://podcast.paulrbrown.org/daily-digest.xml

# Audio file accessibility  
curl -I https://paulrbrown.org/audio/sample_digest.mp3

# GUID stability monitoring
python3 tests/verify_guid_stability.py
```

### 15. Quota Monitoring
```python
# Daily quota usage tracking
from config.production import validate_quota_usage

quota_status = validate_quota_usage(tokens_used=10000, requests_made=50)
if not quota_status['should_continue']:
    # Send alert, throttle operations
    pass
```

### 16. Error Alerting
- **RSS Generation Failures**: 0 episodes generated
- **Security Violations**: Path traversal attempts, injection attempts
- **Quota Exceeded**: OpenAI token limit, YouTube API limit
- **File System Issues**: Disk space, permissions
- **Network Issues**: CDN failures, DNS issues

## 🎯 Quality Gates

### 17. Pre-Deployment Validation
**All must pass before deployment**:
- [ ] Production hardening tests: >95% pass rate
- [ ] RSS spec validation: 100% conformance  
- [ ] GUID stability: Identical across runs
- [ ] Security validation: 0 critical issues
- [ ] Environment variables: All required vars set
- [ ] DNS resolution: All URLs accessible
- [ ] SSL certificates: Valid and not expiring soon

### 18. Post-Deployment Verification
**Within 1 hour of deployment**:
- [ ] RSS feed accessible via HTTPS
- [ ] Latest episode MP3 files accessible
- [ ] Podcast apps can fetch feed
- [ ] No 404 errors in logs
- [ ] GUID consistency maintained
- [ ] All enclosure sizes accurate

## 🔄 Rollback Plan

### 19. Emergency Rollback
**If critical issues detected**:
```bash
# Revert to previous RSS feed
git checkout HEAD~1 daily-digest.xml
git add daily-digest.xml
git commit -m "Emergency rollback RSS feed"
git push

# Disable GitHub Actions workflow
# Edit .github/workflows/daily-podcast-pipeline.yml
# Add: if: false

# Manual RSS generation with old system
python3 rss_generator_multi_topic.py
```

### 20. Rollback Triggers
- **GUID Changes**: Existing episodes get new GUIDs
- **RSS Validation Failures**: Feed parsing errors
- **Security Breaches**: Path traversal, injection attempts
- **Quota Exhaustion**: API limits exceeded
- **Performance Degradation**: >5x slower processing

## 📋 Launch Checklist Summary

**Critical Items (MUST COMPLETE)**:
- [ ] Environment variables configured
- [ ] Production hardening tests passing
- [ ] GUID stability verified
- [ ] RSS spec conformance validated
- [ ] Security validation enabled
- [ ] DNS and CDN configured
- [ ] Monitoring and alerting active
- [ ] Rollback plan tested

**Success Metrics**:
- Security score: ≥95%
- RSS validation: 100% pass
- GUID stability: 100% consistent
- API quota usage: <80%
- Feed accessibility: 99.9% uptime
- Episode delivery: 0 broken links

---

**🎯 DEPLOYMENT AUTHORIZATION**

Only deploy when ALL critical items are checked and verified.

**Deployment Approved By**: _________________
**Date**: _________________
**Production Environment**: ✅ READY / ❌ NOT READY