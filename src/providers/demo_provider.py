"""Deterministic demo data provider for local development."""

from datetime import datetime, timedelta, timezone

from src.models.pipeline_run import PipelineRun
from src.providers.base import PipelineProvider


class DemoProvider(PipelineProvider):
    """Generate 127 representative executions without external dependencies."""

    def get_pipeline_runs(self) -> list[PipelineRun]:
        start = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
        statuses = ("Success", "Success", "Success", "Failed", "Running")
        runs: list[PipelineRun] = []
        for index in range(127):
            status = statuses[index % len(statuses)]
            runs.append(
                PipelineRun(
                    pipeline_name=f"demo_pipeline_{index % 12 + 1:02d}",
                    run_id=f"demo-{index + 1:03d}",
                    status=status,
                    started_at=start - timedelta(days=index % 14, minutes=index * 7),
                    duration_seconds=0 if status == "Running" else 180 + (index * 37) % 900,
                    error_message="Simulated failure" if status == "Failed" else None,
                )
            )
        return runs
