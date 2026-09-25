def test_core_models_and_monitor_import_without_a_cycle() -> None:
    from src.models.pipeline_run import PipelineRun
    from src.monitor.guardian_scout import GuardianScout, Observation

    assert PipelineRun.__name__ == "PipelineRun"
    assert GuardianScout.__name__ == "GuardianScout"
    assert Observation.__name__ == "Observation"
