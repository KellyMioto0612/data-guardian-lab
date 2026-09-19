"""Azure Synapse provider boundary for normalized pipeline runs."""

from src.models.pipeline_run import PipelineRun
from src.providers.base import PipelineProvider


class SynapseProvider(PipelineProvider):
    """Provider seam; production query integration can be injected later."""

    def __init__(self, workspace: str) -> None:
        self.workspace = workspace

    def get_pipeline_runs(self) -> list[PipelineRun]:
        """Return runs from Synapse when the query adapter is implemented."""
        raise NotImplementedError(
            "SynapseProvider requires a configured query adapter in Sprint 3"
        )
