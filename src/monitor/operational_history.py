"""Optional local history and explainable alerts; stores no SQL or error payloads."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.models.pipeline_run import PipelineRun


@dataclass(frozen=True)
class Investigation:
    total_runs: int
    failed_runs: int
    affected_pipelines: tuple[str, ...]
    alert: bool
    explanation: str


class OperationalHistory:
    """Keep minimal execution metadata in an explicitly configured local database."""

    def __init__(self, path: str | Path, *, retention_days: int = 30) -> None:
        if retention_days <= 0:
            raise ValueError("retention_days must be positive")
        self.path = Path(path)
        self.retention_days = retention_days
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS pipeline_runs (
                source TEXT NOT NULL, run_id TEXT NOT NULL, pipeline_name TEXT NOT NULL,
                status TEXT NOT NULL, started_at TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                PRIMARY KEY (source, run_id)
            )""")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def record(
        self, runs: list[PipelineRun], *, source: str = "demo", now: datetime | None = None
    ) -> int:
        """Upsert runs and remove old records. SQL, tokens and error text are excluded."""
        moment = (now or datetime.now(UTC)).astimezone(UTC)
        cutoff = (moment - timedelta(days=self.retention_days)).isoformat()
        rows = [
            (
                source,
                run.run_id,
                run.pipeline_name,
                run.status,
                run.started_at.astimezone(UTC).isoformat(),
                run.duration_seconds,
            )
            for run in runs
        ]
        with self._connect() as db:
            db.executemany(
                """INSERT INTO pipeline_runs VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, run_id) DO UPDATE SET
                pipeline_name=excluded.pipeline_name, status=excluded.status,
                started_at=excluded.started_at, duration_seconds=excluded.duration_seconds""",
                rows,
            )
            db.execute("DELETE FROM pipeline_runs WHERE started_at < ?", (cutoff,))
        return len(rows)

    def investigate(
        self, *, window_hours: int = 24, failure_threshold: int = 1,
        now: datetime | None = None, source: str = "demo",
    ) -> Investigation:
        """Summarize observed failures without guessing a root cause."""
        if window_hours <= 0 or failure_threshold <= 0:
            raise ValueError("window_hours and failure_threshold must be positive")
        moment = (now or datetime.now(UTC)).astimezone(UTC)
        cutoff = (moment - timedelta(hours=window_hours)).isoformat()
        with self._connect() as db:
            rows = db.execute(
                "SELECT pipeline_name, status FROM pipeline_runs "
                "WHERE source = ? AND started_at >= ? AND started_at <= ?",
                (source, cutoff, moment.isoformat()),
            ).fetchall()
        affected = tuple(sorted({name for name, status in rows if status.upper() == "FAILED"}))
        failures = sum(status.upper() == "FAILED" for _, status in rows)
        explanation = (
            f"{failures} falha(s) em {len(rows)} execução(ões) nas últimas {window_hours} horas; "
            "causa raiz não determinada apenas pelos metadados de execução."
        )
        return Investigation(
            len(rows), failures, affected, failures >= failure_threshold, explanation
        )


__all__ = ["Investigation", "OperationalHistory"]
