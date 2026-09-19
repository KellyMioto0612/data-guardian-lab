"""Provider-agnostic monitoring orchestration."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.models.pipeline_run import PipelineRun
from src.providers.base import PipelineProvider


@dataclass(frozen=True)
class Observation:
    name: str
    value: float
    threshold: float
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class GuardianScout:
    """Consume any PipelineProvider without knowing its data source."""

    def __init__(self, provider: PipelineProvider) -> None:
        self.provider = provider

    def collect_runs(self) -> list[PipelineRun]:
        return self.provider.get_pipeline_runs()

    def run(self) -> list[Observation]:
        runs = self.collect_runs()
        failed = sum(run.status == "Failed" for run in runs)
        return [Observation("failed_runs", float(failed), 1.0, metadata={"total_runs": len(runs)})]
