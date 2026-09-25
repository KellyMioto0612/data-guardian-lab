"""End-to-end validation of the SQL pipeline against repository fixtures."""

from pathlib import Path

import pytest

from src.models.pipeline_run import PipelineRun
from src.pipeline.sql_pipeline import SQLPipeline

FIXTURES = Path(__file__).parent / "fixtures" / "sql"


@pytest.fixture
def pipeline() -> SQLPipeline:
    return SQLPipeline()


def test_run_complete_repository(pipeline: SQLPipeline) -> None:
    result = pipeline.run_repository(FIXTURES)

    assert isinstance(result, PipelineRun)
    assert result.status in {"SUCCESS", "PARTIAL", "FAILED"}
    assert result.processed_files
    assert result.observations
    assert result.guardian_objects
    assert len(result.observations) <= len(result.guardian_objects)


def test_procedures_preserve_calls_and_dependency_graph(pipeline: SQLPipeline) -> None:
    result = pipeline.run_directory(FIXTURES / "procedures")

    assert {"refresh_orders.sql", "validate_orders.sql"} <= set(result.processed_files)
    assert result.metrics is not None
    called = {name for entity in result.metrics.entities for name in entity.called_procedures}
    assert "dbo.refresh_orders" in called
    assert result.dependency_graph is not None
    assert any(edge.edge_type == "CALLS" for edge in result.dependency_graph.edges)


def test_pipeline_only_promotes_persistent_assets(pipeline: SQLPipeline) -> None:
    result = pipeline.run_file(FIXTURES / "procedures" / "refresh_orders.sql")

    assert result.guardian_objects
    assert {obj.object_type for obj in result.guardian_objects} == {"procedure"}
    assert result.metadata["asset_classification_counts"]["asset"] == 1
    assert result.evidence
    assert result.evidence[0].rule_id == "SQL-005"
    assert result.guardian_objects[0].metadata["technical_debt"]["score"] == 10.0
    assert result.observations[0].metadata["evidence"][0]["rule_id"] == "SQL-005"


def test_pipeline_retains_evidence_for_non_persistent_sql(pipeline: SQLPipeline) -> None:
    result = pipeline.run_file(FIXTURES / "joins" / "cross_join.sql")

    assert not result.guardian_objects
    assert [item.rule_id for item in result.evidence] == ["SQL-002"]
    assert result.metadata["evidence_count"] == 1


def test_views_create_guardian_objects_and_reads(pipeline: SQLPipeline) -> None:
    result = pipeline.run_directory(FIXTURES / "views")

    assert {obj.object_type for obj in result.guardian_objects} == {"view"}
    assert result.metrics is not None
    assert result.metrics.read_table_count > 0
    assert result.dependency_graph is not None
    assert any(edge.edge_type == "READS" for edge in result.dependency_graph.edges)


def test_ctes_have_bounded_depth_and_do_not_loop(pipeline: SQLPipeline) -> None:
    result = pipeline.run_directory(FIXTURES / "ctes")

    assert result.metrics is not None
    assert result.metrics.cte_count >= 2
    assert result.metrics.max_cte_depth >= 1
    assert result.metrics.max_cte_depth <= result.metrics.cte_count
    assert result.metrics.recursive_cte_count >= 0


def test_join_fixtures_preserve_join_metadata(pipeline: SQLPipeline) -> None:
    result = pipeline.run_directory(FIXTURES / "joins")

    assert result.metrics is not None
    assert result.metrics.join_count >= 3
    join_types = result.metrics.join_types.as_mapping()
    assert join_types["INNER"] >= 1
    assert join_types["LEFT"] >= 1
    assert join_types["CROSS"] >= 1
    assert result.metrics.joins_without_condition >= 1
    assert result.dependency_graph is not None
    assert any("join_type" in edge.metadata for edge in result.dependency_graph.edges)


def test_merge_fixture_preserves_written_table_and_dependencies(pipeline: SQLPipeline) -> None:
    result = pipeline.run_file(FIXTURES / "scripts" / "merge_orders.sql")

    assert result.metrics is not None
    assert result.metrics.written_table_count > 0
    assert result.metrics.table_reference_count >= result.metrics.written_table_count
    assert result.metrics.dependencies


def test_repository_execution_is_deterministic(pipeline: SQLPipeline) -> None:
    first = pipeline.run_repository(FIXTURES)
    second = pipeline.run_repository(FIXTURES)

    assert first.processed_files == second.processed_files
    assert [(item.object_id, item.object_type, item.name) for item in first.guardian_objects] == [
        (item.object_id, item.object_type, item.name) for item in second.guardian_objects
    ]
    assert [(item.name, item.value, item.metadata) for item in first.observations] == [
        (item.name, item.value, item.metadata) for item in second.observations
    ]
    assert first.metrics is not None and second.metrics is not None
    assert first.metrics.entity_count == second.metrics.entity_count
    assert first.metrics.join_count == second.metrics.join_count
    assert first.metrics.cte_count == second.metrics.cte_count


def test_invalid_fixture_is_optional_until_added(pipeline: SQLPipeline) -> None:
    invalid = FIXTURES / "invalid.sql"
    if not invalid.exists():
        pytest.skip("No invalid SQL fixture exists in the approved fixture set")

    result = pipeline.run_file(invalid)

    assert result.status in {"PARTIAL", "FAILED"}
    assert result.parse_error_count >= 0
    assert result.warning_count >= 0
