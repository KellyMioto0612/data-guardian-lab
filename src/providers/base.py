"""Abstract provider contract for pipeline observability."""

from abc import ABC, abstractmethod

from src.models.pipeline_run import PipelineRun


class PipelineProvider(ABC):
    """Source-independent interface consumed by monitors and dashboards."""

    @abstractmethod
    def get_pipeline_runs(self) -> list[PipelineRun]:
        """Return normalized pipeline executions."""
        raise NotImplementedError
