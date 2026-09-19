from src.models.pipeline_run import PipelineRun
from src.providers.demo_provider import DemoProvider


def test_demo_provider_generates_expected_dataset() -> None:
    runs = DemoProvider().get_pipeline_runs()
    assert len(runs) == 127
    assert {run.status for run in runs} == {"Success", "Failed", "Running"}
    assert all(isinstance(run, PipelineRun) for run in runs)
