# Changelog

All notable changes to the Multi-Topic Podcast Digest System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - Phase 3 Import/Telemetry Fixes

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