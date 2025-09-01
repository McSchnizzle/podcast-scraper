-- UPDATED Migration: preserve and add required columns without dropping data
-- Apply to BOTH podcast_monitor.db and youtube_transcripts.db

-- Episodes additions
ALTER TABLE episodes ADD COLUMN topic_relevance_json TEXT;
ALTER TABLE episodes ADD COLUMN digest_topic TEXT;
ALTER TABLE episodes ADD COLUMN digest_date TEXT;
ALTER TABLE episodes ADD COLUMN scores_version TEXT;

-- Feeds additions (SQLite: BOOLEAN -> INTEGER 0/1; TIMESTAMP stored as TEXT/NUMERIC)
ALTER TABLE feeds ADD COLUMN active INTEGER DEFAULT 1;
ALTER TABLE feeds ADD COLUMN last_checked TEXT;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_episodes_digest ON episodes(digest_topic, digest_date);
CREATE INDEX IF NOT EXISTS idx_episodes_transcribed_at ON episodes(transcribed_at);
