# Changelog

All notable changes to the Multi-Topic Podcast Digest System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v4-complete] - 2025-09-06

### 🎉 Phase 4 Database Integrity Complete

This release marks the completion of Phase 4: Database Integrity with comprehensive foreign key enforcement, connection factory adoption, and operational reliability improvements.

### ✨ Added

#### Database Integrity & Factory System
- **Database Connection Factory** (`utils/db.py`): Centralized connection management with enforced standards
  - PRAGMA foreign_keys = ON (always enforced)  
  - PRAGMA journal_mode = WAL (better concurrency)
  - PRAGMA synchronous = NORMAL (balance durability/performance)
  - Schema version validation and timeout configuration
- **Schema Integrity Verification** (`scripts/verify_schema_integrity.py`): Comprehensive database validation
  - Foreign key enforcement and integrity checks
  - Schema version validation (user_version = 2)
  - Required tables, indexes, and unique constraints verification
  - Orphaned records detection and data integrity validation
- **Startup Preflight Logging** (`utils/startup_preflight.py`): PID-guarded system status logging
  - One-time logging per process of critical database and system settings
  - SQLite version, foreign keys status, journal mode, schema version reporting

#### Feed Processing Robustness  
- **Enhanced Feed Monitoring** (`feed_monitor.py`): Complete rewrite with Phase 4 features
  - HTTP caching with ETag/Last-Modified support (reduces bandwidth)
  - Per-feed lookback controls with 15-minute grace period
  - Date-less items handled deterministically without duplicate processing
  - Enhanced duplicate detection prevents re-processing
  - Exactly 2 INFO lines per feed (header + totals) with debug details
- **Feed Helpers** (`utils/feed_helpers.py`): Utility functions for robust feed processing
- **Database Migration** (`scripts/migrate_phase4_schema_integrity.py`): Complete schema v2 migration

#### Testing & Validation
- **Phase 4 Integration Tests** (`tests/test_phase4_feed_ingestion.py`): Comprehensive test suite (16 test methods)
- **Double-Run Smoke Testing**: Deterministic validation of ingestion idempotency
- **Migration Idempotency Testing**: Ensures migrations can be re-run safely

### 🔄 Changed

#### Database Schema (v1 → v2)
- **Foreign Key Enforcement**: All connections now enforce FK constraints
- **Enhanced Indexes**: Performance indexes on all foreign key columns
- **Unique Constraints**: Deduplication constraints for data integrity
- **Schema Version Tracking**: `PRAGMA user_version = 2` for migration tracking

#### Connection Management
- **Factory Adoption**: 71+ files migrated from direct `sqlite3.connect()` to connection factory
- **Consistent Configuration**: Timeout, isolation_level, row_factory standardized
- **Error Handling**: Comprehensive connection error handling and logging

### 🛡️ Security & Reliability
- **Foreign Key Integrity**: Prevents orphaned records and maintains referential integrity
- **Connection Validation**: Schema version and constraint verification on connection
- **14-Day Retention**: Intelligent cleanup with database optimization and VACUUM operations
- **Startup Validation**: PID-guarded preflight checks log critical system state

### 📊 Performance Improvements
- **WAL Mode**: Better concurrency with Write-Ahead Logging
- **HTTP Caching**: Reduces bandwidth usage with 304 Not Modified responses
- **Optimized Indexes**: Performance indexes on all foreign key columns

### 📈 Statistics
- **Database Migrations Applied**: Both `podcast_monitor.db` (23 feeds) and `youtube_transcripts.db` (9 feeds)
- **Connection Factory Adoption**: 71+ non-test files migrated from direct sqlite3.connect
- **Schema Version**: Upgraded from v1 to v2 with comprehensive integrity checks
- **Foreign Key Compliance**: 100% enforcement across all database connections

## [Phase-3-Complete] - Phase 3 Import/Telemetry Fixes

### Added
- `TelemetryManager.record_metric()` with automatic type detection and structured logging
- `TelemetryManager.record_counter()`, `record_gauge()`, `record_histogram()` convenience methods
- Structured metric logging with JSON output for observability
- Compatibility shim `openai_scorer_compat.py` for legacy imports
- CI guard `tests/test_no_legacy_imports.py` to prevent legacy imports in production code
- Comprehensive Phase 3 integration test suite
- Conditional export mechanism in `openai_scorer.py` via `ALLOW_LEGACY_OPENAI_SCORER_ALIAS`
- Deprecation warnings for old class names to guide migration

### Changed
- **BREAKING**: `OpenAIScorer` class renamed to `OpenAITopicScorer`
  - Backward compatibility maintained via compatibility shim
  - Will be fully removed in v2.0.0
- Enhanced telemetry with metric type detection via suffix convention
- Removed `sys.path.append` hacks in favor of proper absolute imports
- Updated `utils/episode_failures.py` to use new class name directly

### Fixed
- **Critical**: Import errors in retry queue processing (`cannot import name 'OpenAIScorer'`)
- **Critical**: Missing `record_metric` method in TelemetryManager causing AttributeError
- Retry queue processing now works without import failures
- Pipeline telemetry recording functional for both RSS and YouTube processing

### Deprecated
- `OpenAIScorer` class name - use `OpenAITopicScorer` instead
- `OpenAIRelevanceScorer` class name - use `OpenAITopicScorer` instead
- Legacy imports via `from openai_scorer import OpenAIScorer` - use shim or update to new name

### Security
- Improved import hygiene with CI guards against legacy patterns
- Better error handling in telemetry with structured logging

## [Previous Versions]

### Phase 2 - GPT-5 Integration (Completed)
- Migrated to GPT-5 Responses API for digest generation
- Added idempotency and anti-injection protection
- Enhanced OpenAI integration with structured output and validation

### Phase 1 - Datetime/Timezone Reliability (Completed) 
- Standardized on UTC timezone handling with `zoneinfo`
- Removed `pytz` dependency
- Enhanced datetime utilities and feed processing

### Phase 0 - Guardrails & Baseline (Completed)
- Implemented CI smoke tests and validation
- Centralized logging and configuration
- Added dry-run and timeout support