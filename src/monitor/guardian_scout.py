"""Provider-agnostic monitoring orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.providers.base import PipelineProvider

if TYPE_CHECKING:
    from src.models.pipeline_run import PipelineRun


@dataclass(frozen=True)
class Observation:
    name: str
    value: float
    threshold: float
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


class GuardianScout:
    """Consume any PipelineProvider without knowing its data source."""

    def __init__(self, provider: PipelineProvider) -> None:
        self.provider = provider

    def collect_runs(self) -> list[PipelineRun]:
        return self.provider.get_pipeline_runs()

    def run(self) -> list[Observation]:
        runs = self.collect_runs()
        failed = sum(run.status.upper() == "FAILED" for run in runs)
        return [Observation("failed_runs", float(failed), 1.0, metadata={"total_runs": len(runs)})]
