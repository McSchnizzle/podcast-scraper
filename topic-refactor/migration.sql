-- Migration script for podcast-scraper refactor

-- Apply to BOTH podcast_monitor.db and youtube_transcripts.db

ALTER TABLE episodes ADD COLUMN topic_relevance_json TEXT;
ALTER TABLE episodes ADD COLUMN digest_topic TEXT;
ALTER TABLE episodes ADD COLUMN digest_date TEXT;
ALTER TABLE episodes ADD COLUMN scores_version TEXT;

-- Optional: make feeds.topic_category nullable (deprecate)
PRAGMA foreign_keys=off;
CREATE TABLE feeds_new AS SELECT id, url, title, type, topic_category FROM feeds;
DROP TABLE feeds;
ALTER TABLE feeds_new RENAME TO feeds;
PRAGMA foreign_keys=on;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_episodes_digest
  ON episodes(digest_topic, digest_date);
CREATE INDEX IF NOT EXISTS idx_episodes_transcribed_at
  ON episodes(transcribed_at);
