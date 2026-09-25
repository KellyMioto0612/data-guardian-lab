"""Behavior and data minimization tests for optional local history."""

import sqlite3
from datetime import UTC, datetime, timedelta

from src.models.pipeline_run import PipelineRun
from src.monitor.operational_history import OperationalHistory


def _run(identifier: str, status: str, started: datetime) -> PipelineRun:
    return PipelineRun(
        pipeline_name="daily_job", run_id=identifier, status=status,
        started_at=started, duration_seconds=42,
        error_message="private error text", metadata={"secret": "private metadata"},
    )


def test_history_deduplicates_prunes_and_excludes_private_payloads(tmp_path) -> None:
    now = datetime(2026, 9, 24, 12, tzinfo=UTC)
    path = tmp_path / "runs.db"
    history = OperationalHistory(path, retention_days=2)
    history.record([
        _run("old", "Failed", now - timedelta(days=3)),
        _run("current", "Failed", now - timedelta(hours=1)),
    ], now=now)
    history.record([_run("current", "Success", now - timedelta(hours=1))], now=now)

    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT run_id, status FROM pipeline_runs").fetchall()
        columns = {item[1] for item in db.execute("PRAGMA table_info(pipeline_runs)")}
    assert rows == [("current", "Success")]
    assert "error_message" not in columns and "metadata" not in columns


def test_alert_explains_observed_failure_without_claiming_root_cause(tmp_path) -> None:
    now = datetime(2026, 9, 24, 12, tzinfo=UTC)
    history = OperationalHistory(tmp_path / "runs.db")
    history.record([
        _run("current", "Failed", now - timedelta(hours=1)),
        _run("previous", "Failed", now - timedelta(days=2)),
    ], now=now)
    finding = history.investigate(now=now)

    assert finding.total_runs == 1
    assert finding.failed_runs == 1
    assert finding.affected_pipelines == ("daily_job",)
    assert finding.alert
    assert "causa raiz não determinada" in finding.explanation


def test_demonstration_and_synapse_histories_are_separate(tmp_path) -> None:
    now = datetime(2026, 9, 24, 12, tzinfo=UTC)
    history = OperationalHistory(tmp_path / "runs.db")
    history.record([_run("shared-id", "Failed", now)], source="demo", now=now)
    history.record([_run("shared-id", "Success", now)], source="synapse", now=now)

    assert history.investigate(source="demo", now=now).failed_runs == 1
    assert history.investigate(source="synapse", now=now).failed_runs == 0
