#!/usr/bin/env python3
"""
Telemetry Manager for Podcast Scraper System
Tracks per-topic metrics, token usage, retry counts, and operational statistics
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Final, List, Optional

from utils.datetime_utils import now_utc

logger = logging.getLogger(__name__)

# Metric type detection via suffix convention
SUFFIX_TO_KIND: Final[Dict[str, str]] = {
    ".count": "counter",
    ".ms": "histogram",
    ".seconds": "histogram",
    ".gauge": "gauge",
    "_total": "counter",
    "_duration": "histogram",
}


@dataclass
class TopicMetrics:
    """Per-topic operational metrics"""

    topic: str
    total_candidates: int
    above_threshold_count: int
    selected_count: int
    threshold_used: float
    map_phase_tokens: int
    reduce_phase_tokens: int
    total_tokens: int
    retry_count: int
    processing_time_seconds: float
    episode_ids_included: List[str]
    episode_ids_dropped: List[str]
    success: bool
    error_message: Optional[str] = None


@dataclass
class RunMetrics:
    """Complete pipeline run metrics"""

    run_id: str
    timestamp: str
    pipeline_type: str  # daily, weekly, catchup
    total_processing_time: float
    topics_processed: List[TopicMetrics]
    episodes_transcribed: int
    episodes_scored: int
    episodes_digested: int
    files_deployed: int
    rss_items_generated: int
    total_api_calls: int
    total_tokens_used: int
    total_cost_estimate: float
    errors: List[str]
    warnings: List[str]


class TelemetryManager:
    """Centralized telemetry collection and persistence"""

    def __init__(self, telemetry_dir: str = "telemetry", retention_days: int = 14):
        self.telemetry_dir = Path(telemetry_dir)
        self.telemetry_dir.mkdir(exist_ok=True)

        # Map summaries directory for 14-day retention
        self.map_summaries_dir = self.telemetry_dir / "map_summaries"
        self.map_summaries_dir.mkdir(exist_ok=True)

        self.retention_days = retention_days
        self.current_run_id = self._generate_run_id()

        # Initialize current run metrics
        self.current_run = RunMetrics(
            run_id=self.current_run_id,
            timestamp=now_utc().isoformat(),
            pipeline_type="daily",  # Will be updated
            total_processing_time=0.0,
            topics_processed=[],
            episodes_transcribed=0,
            episodes_scored=0,
            episodes_digested=0,
            files_deployed=0,
            rss_items_generated=0,
            total_api_calls=0,
            total_tokens_used=0,
            total_cost_estimate=0.0,
            errors=[],
            warnings=[],
        )

        logger.info(f"📊 Telemetry initialized - Run ID: {self.current_run_id}")

    def _generate_run_id(self) -> str:
        """Generate unique run identifier"""
        return f"run_{now_utc().strftime('%Y%m%d_%H%M%S')}"

    def set_pipeline_type(self, pipeline_type: str):
        """Set the type of pipeline run (daily/weekly/catchup)"""
        self.current_run.pipeline_type = pipeline_type
        logger.info(f"📊 Pipeline type: {pipeline_type}")

    def record_topic_processing(
        self,
        topic: str,
        total_candidates: int,
        above_threshold_count: int,
        selected_count: int,
        threshold_used: float,
        map_phase_tokens: int,
        reduce_phase_tokens: int,
        retry_count: int,
        processing_time: float,
        episode_ids_included: List[str],
        episode_ids_dropped: List[str],
        success: bool,
        error_message: Optional[str] = None,
    ):
        """Record comprehensive topic processing metrics"""

        total_tokens = map_phase_tokens + reduce_phase_tokens

        metrics = TopicMetrics(
            topic=topic,
            total_candidates=total_candidates,
            above_threshold_count=above_threshold_count,
            selected_count=selected_count,
            threshold_used=threshold_used,
            map_phase_tokens=map_phase_tokens,
            reduce_phase_tokens=reduce_phase_tokens,
            total_tokens=total_tokens,
            retry_count=retry_count,
            processing_time_seconds=processing_time,
            episode_ids_included=episode_ids_included,
            episode_ids_dropped=episode_ids_dropped,
            success=success,
            error_message=error_message,
        )

        self.current_run.topics_processed.append(metrics)
        self.current_run.total_tokens_used += total_tokens
        self.current_run.total_api_calls += 1 + retry_count  # Base call + retries

        # Estimate cost (rough approximation)
        # GPT-4-turbo: $0.01/1K input tokens, $0.03/1K output tokens
        # GPT-4o-mini: $0.00015/1K input tokens, $0.0006/1K output tokens
        if map_phase_tokens > 0:
            # Map phase uses cost-effective model
            cost_estimate = (map_phase_tokens * 0.00015 / 1000) + (
                map_phase_tokens * 0.0006 / 1000
            )
        else:
            cost_estimate = 0

        if reduce_phase_tokens > 0:
            # Reduce phase uses primary model
            cost_estimate += (reduce_phase_tokens * 0.01 / 1000) + (
                reduce_phase_tokens * 0.03 / 1000
            )

        self.current_run.total_cost_estimate += cost_estimate

        # Log comprehensive metrics
        status = "✅" if success else "❌"
        logger.info(f"📊 {status} Topic: {topic}")
        logger.info(
            f"    Candidates: {total_candidates} → Threshold ≥{threshold_used}: {above_threshold_count} → Selected: {selected_count}"
        )
        logger.info(
            f"    Tokens: Map={map_phase_tokens} + Reduce={reduce_phase_tokens} = {total_tokens}"
        )
        logger.info(f"    Retries: {retry_count}, Time: {processing_time:.1f}s")
        logger.info(
            f"    Episodes included: {len(episode_ids_included)}, dropped: {len(episode_ids_dropped)}"
        )
        if error_message:
            logger.info(f"    Error: {error_message}")

    def record_processing_stats(
        self,
        transcribed: int = 0,
        scored: int = 0,
        digested: int = 0,
        deployed: int = 0,
        rss_items: int = 0,
    ):
        """Record general processing statistics"""
        self.current_run.episodes_transcribed += transcribed
        self.current_run.episodes_scored += scored
        self.current_run.episodes_digested += digested
        self.current_run.files_deployed += deployed
        self.current_run.rss_items_generated += rss_items

    def record_error(self, error_message: str):
        """Record an error in the current run"""
        self.current_run.errors.append(error_message)
        logger.error(f"📊 Error recorded: {error_message}")

    def record_warning(self, warning_message: str):
        """Record a warning in the current run"""
        self.current_run.warnings.append(warning_message)
        logger.warning(f"📊 Warning recorded: {warning_message}")

    def record_metric(self, name: str, value: float = 1.0, **labels) -> None:
        """
        Record a generic metric with automatic type detection.

        Args:
            name: Metric name (use suffixes: .count, .ms, .gauge for type hints)
            value: Metric value (default 1.0 for counters)
            **labels: Additional labels for the metric

        Examples:
            record_metric('pipeline.retries.count', 3)
            record_metric('openai.tokens.count', 500, component='scorer')
            record_metric('processing.duration.ms', 1500, stage='transcription')
        """
        # Detect metric type from suffix
        metric_kind = "counter"  # default
        for suffix, kind in SUFFIX_TO_KIND.items():
            if name.endswith(suffix):
                metric_kind = kind
                break

        # Add run_id to labels
        labels["run_id"] = self.current_run_id

        # Emit structured metric log
        self._emit_metric(metric_kind, name, value, labels)

        # Update internal counters for backward compatibility
        self._update_run_metrics(name, value)

    def _emit_metric(
        self, kind: str, name: str, value: float, labels: Dict[str, str]
    ) -> None:
        """Emit structured metric as JSON log entry"""
        metric_record = {
            "evt": "metric",
            "kind": kind,
            "name": name,
            "value": value,
            "labels": labels,
            "run_id": self.current_run_id,
            "ts": now_utc().isoformat(),
        }

        # Log at DEBUG level to avoid noise, but structured for parsing
        logger.debug(f"METRIC {json.dumps(metric_record)}")

    def _update_run_metrics(self, name: str, value: float) -> None:
        """Update internal run metrics for compatibility"""
        # Map metric names to run fields
        if "retries" in name.lower():
            if "processed" in name:
                self.current_run.total_api_calls += int(value)
            elif "succeeded" in name:
                # Track success rate implicitly
                pass
        elif "tokens" in name.lower():
            self.current_run.total_tokens_used += int(value)
        elif "episodes" in name.lower():
            if "transcribed" in name:
                self.current_run.episodes_transcribed += int(value)
            elif "scored" in name:
                self.current_run.episodes_scored += int(value)
            elif "digested" in name:
                self.current_run.episodes_digested += int(value)
        elif "error" in name.lower():
            self.current_run.errors.append(f"Metric error: {name}={value}")

    def record_counter(
        self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a counter metric (monotonically increasing)"""
        self.record_metric(
            f"{name}.count" if not name.endswith(".count") else name,
            value,
            **(labels or {}),
        )

    def record_gauge(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a gauge metric (can go up or down)"""
        self.record_metric(
            f"{name}.gauge" if not name.endswith(".gauge") else name,
            value,
            **(labels or {}),
        )

    def record_histogram(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a histogram metric (for distributions like latency)"""
        self.record_metric(
            f"{name}.ms" if not name.endswith((".ms", ".seconds")) else name,
            value,
            **(labels or {}),
        )

    def save_map_summary(
        self, episode_id: str, topic: str, summary_content: str, token_count: int
    ):
        """Save episode map summary for 14-day retention"""
        summary_data = {
            "episode_id": episode_id,
            "topic": topic,
            "timestamp": now_utc().isoformat(),
            "summary": summary_content,
            "token_count": token_count,
            "run_id": self.current_run_id,
        }

        # Save with timestamp for retention management
        timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
        summary_file = self.map_summaries_dir / f"{episode_id}_{topic}_{timestamp}.json"

        try:
            with open(summary_file, "w") as f:
                json.dump(summary_data, f, indent=2)
            logger.debug(f"📊 Saved map summary: {summary_file.name}")
        except Exception as e:
            logger.error(f"Failed to save map summary for {episode_id}: {e}")

    def finalize_run(self, total_time: float):
        """Finalize and save the current run metrics"""
        self.current_run.total_processing_time = total_time

        # Save run telemetry
        telemetry_file = self.telemetry_dir / f"{self.current_run_id}.json"

        try:
            with open(telemetry_file, "w") as f:
                json.dump(asdict(self.current_run), f, indent=2)

            logger.info(f"📊 Run telemetry saved: {telemetry_file}")
            self._log_run_summary()

            # Clean up old telemetry files
            self._cleanup_old_telemetry()

        except Exception as e:
            logger.error(f"Failed to save run telemetry: {e}")

    def _log_run_summary(self):
        """Log comprehensive run summary"""
        run = self.current_run

        logger.info("📊 RUN SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Run ID: {run.run_id}")
        logger.info(f"Type: {run.pipeline_type}")
        logger.info(f"Total time: {run.total_processing_time:.1f}s")
        logger.info(
            f"Episodes: {run.episodes_transcribed} transcribed, {run.episodes_scored} scored, {run.episodes_digested} digested"
        )
        logger.info(f"Topics processed: {len(run.topics_processed)}")

        for topic_metrics in run.topics_processed:
            status = "✅" if topic_metrics.success else "❌"
            logger.info(
                f"  {status} {topic_metrics.topic}: {topic_metrics.selected_count}/{topic_metrics.total_candidates} episodes, {topic_metrics.total_tokens} tokens"
            )

        logger.info(f"API calls: {run.total_api_calls}")
        logger.info(f"Total tokens: {run.total_tokens_used:,}")
        logger.info(f"Estimated cost: ${run.total_cost_estimate:.4f}")
        logger.info(f"Files deployed: {run.files_deployed}")
        logger.info(f"RSS items: {run.rss_items_generated}")

        if run.errors:
            logger.info(f"Errors: {len(run.errors)}")
            for error in run.errors:
                logger.info(f"  ❌ {error}")

        if run.warnings:
            logger.info(f"Warnings: {len(run.warnings)}")
            for warning in run.warnings:
                logger.info(f"  ⚠️ {warning}")

        logger.info("=" * 50)

    def _cleanup_old_telemetry(self):
        """Clean up old telemetry files and map summaries"""
        cutoff_date = now_utc() - timedelta(days=self.retention_days)

        # Clean up main telemetry files
        removed_count = 0
        for telemetry_file in self.telemetry_dir.glob("run_*.json"):
            try:
                # Extract date from filename
                date_str = (
                    telemetry_file.stem.split("_")[1]
                    + "_"
                    + telemetry_file.stem.split("_")[2]
                )
                file_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")

                if file_date < cutoff_date:
                    telemetry_file.unlink()
                    removed_count += 1
            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse date from {telemetry_file}: {e}")

        # Clean up map summaries
        map_removed_count = 0
        for summary_file in self.map_summaries_dir.glob("*.json"):
            try:
                # Extract timestamp from filename (last part before .json)
                parts = summary_file.stem.split("_")
                if len(parts) >= 3:
                    date_str = parts[-2] + "_" + parts[-1]
                    file_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")

                    if file_date < cutoff_date:
                        summary_file.unlink()
                        map_removed_count += 1
            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse date from {summary_file}: {e}")

        if removed_count > 0 or map_removed_count > 0:
            logger.info(
                f"🧹 Cleaned up {removed_count} old telemetry files and {map_removed_count} old map summaries"
            )

    def get_recent_runs(self, days: int = 7) -> List[Dict]:
        """Get telemetry data for recent runs"""
        cutoff_date = now_utc() - timedelta(days=days)
        recent_runs = []

        for telemetry_file in self.telemetry_dir.glob("run_*.json"):
            try:
                with open(telemetry_file, "r") as f:
                    run_data = json.load(f)

                run_date = datetime.fromisoformat(run_data["timestamp"])
                if run_date >= cutoff_date:
                    recent_runs.append(run_data)
            except Exception as e:
                logger.warning(f"Could not load {telemetry_file}: {e}")

        # Sort by timestamp (newest first)
        recent_runs.sort(key=lambda x: x["timestamp"], reverse=True)
        return recent_runs

    def generate_summary_report(self, days: int = 7) -> str:
        """Generate a summary report for the last N days"""
        recent_runs = self.get_recent_runs(days)

        if not recent_runs:
            return f"No runs found in the last {days} days"

        # Aggregate statistics
        total_runs = len(recent_runs)
        total_topics = sum(len(run.get("topics_processed", [])) for run in recent_runs)
        total_episodes = sum(run.get("episodes_digested", 0) for run in recent_runs)
        total_tokens = sum(run.get("total_tokens_used", 0) for run in recent_runs)
        total_cost = sum(run.get("total_cost_estimate", 0) for run in recent_runs)
        total_errors = sum(len(run.get("errors", [])) for run in recent_runs)

        # Success rates
        successful_topics = sum(
            len([t for t in run.get("topics_processed", []) if t.get("success", False)])
            for run in recent_runs
        )
        topic_success_rate = (
            (successful_topics / total_topics * 100) if total_topics > 0 else 0
        )

        report = f"""
📊 TELEMETRY SUMMARY REPORT ({days} days)
{'=' * 50}

Pipeline Runs: {total_runs}
Topics Processed: {total_topics} ({topic_success_rate:.1f}% success rate)
Episodes Digested: {total_episodes}
Total Tokens Used: {total_tokens:,}
Estimated Total Cost: ${total_cost:.4f}
Total Errors: {total_errors}

Recent Runs:
"""

        for i, run in enumerate(recent_runs[:5]):  # Show last 5 runs
            run_date = datetime.fromisoformat(run["timestamp"]).strftime(
                "%Y-%m-%d %H:%M"
            )
            topics = len(run.get("topics_processed", []))
            success = len(
                [t for t in run.get("topics_processed", []) if t.get("success", False)]
            )

            report += f"  {i+1}. {run_date} ({run.get('pipeline_type', 'unknown')}): {success}/{topics} topics successful\n"

        return report


# Global telemetry instance
telemetry = TelemetryManager()
