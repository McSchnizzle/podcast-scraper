A) TTS: process today’s digests

What to change (surgical):

In multi_topic_tts_generator.py, expand the pattern:
- topic_pattern = re.compile(r'^([a-zA-Z_]+)_digest_(\d{8}_\d{6})\.md$')
+ # allow letters, digits, underscores, and hyphens (matches create_safe_slug)
+ topic_pattern = re.compile(r'^([A-Za-z0-9_-]+)_digest_(\d{8}_\d{6})\.md$')

Also: standardize generation=consumption

Confirm utils.sanitization.safe_digest_filename() is the only place that forms filenames, and TTS only relies on the same slug pattern. If there are any older code paths producing ai_news_... (underscores) vs ai-news_... (hyphens), normalize to hyphens everywhere and keep backward compatibility (accept both in the regex).

Verification:

Create a dummy MD: daily_digests/ai-news_digest_20250904_123000.md → run python3 multi_topic_tts_generator.py → expect MP3 created and TTS log showing “Found 1 unprocessed digest file”.

B) RSS ingestion: stop silently skipping

Code changes (feed_monitor.py):

Make the lookback window configurable and slightly generous by default:
- def check_new_episodes(self, hours_back=24, feed_types=None):
+ def check_new_episodes(self, hours_back=None, feed_types=None):
+     if hours_back is None:
+         hours_back = int(os.getenv("FEED_LOOKBACK_HOURS", "48"))

Add explicit “skip reasons” and feed freshness hints:
cutoff_time = datetime.now() - timedelta(hours=hours_back)
...
for entry in feed.entries:
    # determine pub_date (existing code)
    if not pub_date:
        logger.debug(f"SKIP no-date: {title} :: {entry.get('title','(untitled)')}")
        continue
    if pub_date < cutoff_time:
        logger.debug(f"SKIP old-entry: {title} :: {entry.get('title')} ({pub_date} < {cutoff_time})")
        continue
    if self._episode_exists(cursor, episode_id):
        logger.debug(f"SKIP duplicate episode_id: {episode_id}")
        continue
    # otherwise insert pre-download

Add a one-liner per feed to show the newest entry date we saw, to quickly identify stale feeds:
newest_seen = max((pub_date_list), default=None)
if newest_seen:
    logger.info(f"Newest in {title}: {newest_seen.isoformat()} (cutoff {cutoff_time.isoformat()})")

Ensure de-dup isn’t too aggressive:
def _episode_exists(self, cursor, episode_id):
    cursor.execute("SELECT 1 FROM episodes WHERE episode_id=?", (episode_id,))
    return cursor.fetchone() is not None

(If you already have this, keep it. The key is to log when it fires.)

Optional: add a --feeds CLI selector and a --hours-back override so you can quickly test with 72 or 120 hours when debugging.

Verification:

Run ingestion only: python3 feed_monitor.py --hours-back 72 --rss (or via pipeline)

Expect “Found N new episodes” and inserted rows with status='pre-download'.

If still zero: your logs should now show why (old/duplicate/no-date), and the “newest in feed” timestamps, so you can decide to widen or adjust feeds.
C) TTS subprocess: ensure it picks up today’s digests, then emits today’s MP3s

Right now your main pipeline spawns multi_topic_tts_generator.py, which said “No unprocessed digest files found” then listed old MP3s. Once (A) is fixed, do this:

In multi_topic_tts_generator.py:

After process_all_unprocessed(), if zero processed, log both the globbed MD list and the regex-matched subset with their timestamps so it’s obvious what was not recognized.

Add --since YYYY-MM-DD (optional) to process only today’s (e.g., filter where digest.date.date() >= since_date).

In daily_podcast_pipeline.py:

After digest MDs are written, print a concise list of just-created files and pass --since to the TTS subprocess with today’s date (UTC). That prevents the TTS step from grabbing stale MDs accidentally.

proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
if proc.returncode != 0:
    print("❌ Deployment failed")
    print("CMD:", " ".join(cmd))
    print("STDOUT:", proc.stdout)
    print("STDERR:", proc.stderr)
    return 1

If using the REST API (recommended), print the HTTP status code and response JSON on failure.

Env validation upfront:
token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
repo  = os.getenv("GITHUB_REPOSITORY", "McSchnizzle/podcast-scraper")
if not token:
    raise SystemExit("GITHUB_TOKEN/GH_TOKEN is not set")

Idempotency: keep a stable “deployment marker” per topic + timestamp. If it’s already deployed, skip rather than failing. You already have deployed_episodes.json—enforce it before attempting upload.

Large files: if you ever cross GH release limits (or if LFS is needed), fail fast with an explicit message. For your current ~3–5MB MP3s, you’re fine.

Verification:

Dry run: print the assets it would upload.

Live run: upload today’s 3 MP3s, see the release URL in logs.

E) Generate RSS only when there are MP3s for today

Your pipeline currently reports “RSS updated successfully” even when “Files deployed: 0 / RSS items: 0”. Make it explicitly conditional:

If today’s MP3s list is empty, log one line: “RSS not updated: no new MP3s for YYYY-MM-DD”, and return.

When updating RSS, validate that each item’s <enclosure> file exists and length matches; otherwise skip the item and warn once.

F) Quieter, more useful logs (without losing debuggability)

Default (INFO): concise, task-level messages only

Start/end of major phases (feeds, scoring, map-reduce per topic, TTS, deploy, RSS)

Counts & outcomes (N new episodes, M selected, MP3s generated, files deployed)

One-line summary per topic (tokens, retries, durations)

Verbose (DEBUG): detailed per-feed/per-entry reasons, HTTP traces, token counts, etc.

How (quick changes):

Replace scattered print with module loggers: logging.getLogger(__name__)

Gate chatty lines (per entry, per HTTP call) behind logger.isEnabledFor(logging.DEBUG)

Add a --verbose flag in daily_podcast_pipeline.py that sets root logger to DEBUG

Remove httpx request echo logs by default (set its logger to WARNING)

End-of-run summary (always): keep your current nice table from telemetry_manager, but ensure the numbers align with reality (e.g., “RSS items: 0” should not appear if you purposely skipped RSS due to no MP3s).

G) Repo hygiene (aligned with your optimization doc)

Unify naming to hyphen-slugs for topics; keep regex accepting underscores for backward compatibility for a few weeks.

Move scripts into /scripts/ (bootstrap_databases.py, restore_feeds.py, backfill_missing_scores.py, etc.).

Delete or archive old claude_* artifacts and .DS_Store, and add patterns to .gitignore.

Backups: move *.db.backup.* out of the repo root to /backups/ (git-ignored).

Config: ensure one single source of truth for filenames (digest/TTS/RSS) in utils/sanitization.py and a settings.py/config class; remove duplicates.

CI: add a lightweight job that runs: feed monitor (mocked), unit tests for filename/regex, and TTS discovery on sample MDs.