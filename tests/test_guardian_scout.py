from datetime import UTC, datetime

from src.models.pipeline_run import PipelineRun
from src.monitor.guardian_scout import GuardianScout
from src.providers.base import PipelineProvider


class StaticProvider(PipelineProvider):
    def get_pipeline_runs(self) -> list[PipelineRun]:
        return [
            PipelineRun(
                pipeline_name="sql_scanner",
                run_id="failed-run",
                status="FAILED",
                started_at=datetime.now(UTC),
                duration_seconds=0,
            )
        ]


def test_scout_counts_uppercase_failed_pipeline_runs() -> None:
    observation = GuardianScout(StaticProvider()).run()[0]

    assert observation.name == "failed_runs"
    assert observation.value == 1.0
