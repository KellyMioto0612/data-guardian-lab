"""Azure Synapse provider boundary for normalized pipeline runs."""

from src.config.azure_auth import AzureCredentialFactory
from src.connectors.synapse_pipeline import SynapsePipelineConnector, recent_pipeline_runs
from src.models.pipeline_run import PipelineRun
from src.providers.base import PipelineProvider


class SynapseProvider(PipelineProvider):
    """Provider seam; production query integration can be injected later."""

    def __init__(self, workspace: str, *, lookback_hours: int = 24) -> None:
        self.workspace = workspace
        self.lookback_hours = lookback_hours

    def create_credential(self) -> object:
        """Create a secretless Entra credential; it does not contact Synapse."""
        return AzureCredentialFactory().create()

    def get_pipeline_runs(self) -> list[PipelineRun]:
        """Return bounded, read-only Synapse pipeline-run metadata."""
        connector = SynapsePipelineConnector(self.workspace, self.create_credential())
        return recent_pipeline_runs(connector, lookback_hours=self.lookback_hours)
