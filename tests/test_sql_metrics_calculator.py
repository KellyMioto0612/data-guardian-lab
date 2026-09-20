"""Contract coverage for the Foundation SQL metrics calculator."""

from dataclasses import FrozenInstanceError, fields, is_dataclass
from types import MappingProxyType
from typing import Mapping

import pytest

from src.analyzers.sql_metrics_calculator import SQLMetricsCalculator
from src.models.sql_metrics import SQLEntityMetrics, SQLMetrics
from src.monitor.scanners.sql_parser import (
    ParseIssue,
    ParsedCTE,
    ParsedEntity,
    ParsedJoin,
    ParsedSQL,
    ParsedTable,
)


@pytest.fixture
def calculator() -> SQLMetricsCalculator:
    return SQLMetricsCalculator()


@pytest.fixture
def entity_factory():
    def make(name: str, entity_type: str = "sql_script", **kwargs) -> ParsedEntity:
        return ParsedEntity(
            name=name,
            entity_type=entity_type,
            statement_type=entity_type.upper(),
            qualified_name=f"dbo.{name}",
            **kwargs,
        )

    return make


def table(name: str, *, schema: str = "dbo", operation: str = "read") -> ParsedTable:
    return ParsedTable(name=name, schema=schema, operation=operation)


def test_returns_sql_metrics(calculator, entity_factory):
    result = calculator.calculate(ParsedSQL(entities=(entity_factory("orders"),), statement_count=1))

    assert isinstance(result, SQLMetrics)
    assert result.entities
    assert all(isinstance(entity, SQLEntityMetrics) for entity in result.entities)


def test_counts_entities(calculator, entity_factory):
    entities = (
        entity_factory("load_orders", "procedure"),
        entity_factory("order_summary", "view"),
        entity_factory("daily_job", "sql_script"),
    )

    result = calculator.calculate(ParsedSQL(entities=entities, statement_count=3))

    assert (result.procedure_count, result.view_count, result.script_count) == (1, 1, 1)
    assert result.entity_count == 3
    assert result.statement_count == 3


def test_counts_ctes(calculator, entity_factory):
    simple = ParsedCTE("orders")
    recursive = ParsedCTE("tree", recursive=True)
    entities = (entity_factory("query", ctes=(simple, recursive)),)

    result = calculator.calculate(ParsedSQL(entities=entities, ctes=(simple, recursive)))

    assert result.cte_count == 2
    assert result.recursive_cte_count == 1


def test_counts_no_and_multiple_ctes(calculator, entity_factory):
    no_cte = calculator.calculate(ParsedSQL(entities=(entity_factory("plain"),)))
    multiple = calculator.calculate(
        ParsedSQL(
            entities=(entity_factory("query", ctes=(ParsedCTE("a"), ParsedCTE("b"))),),
        )
    )

    assert (no_cte.cte_count, no_cte.recursive_cte_count) == (0, 0)
    assert (multiple.cte_count, multiple.recursive_cte_count) == (2, 0)


def test_calculates_cte_depth(calculator, entity_factory):
    chain = (ParsedCTE("A", references=("B",)), ParsedCTE("B", references=("C",)), ParsedCTE("C"))
    depth_three = calculator.calculate(ParsedSQL(entities=(entity_factory("q"),), ctes=chain))
    depth_one = calculator.calculate(ParsedSQL(entities=(entity_factory("q"),), ctes=(ParsedCTE("A"),)))
    no_ctes = calculator.calculate(ParsedSQL(entities=(entity_factory("q"),)))

    assert depth_three.max_cte_depth == 3
    assert depth_one.max_cte_depth == 1
    assert no_ctes.max_cte_depth == 0


def test_handles_cte_cycles(calculator, entity_factory):
    cycle = (ParsedCTE("A", references=("B",)), ParsedCTE("B", references=("A",)))

    result = calculator.calculate(ParsedSQL(entities=(entity_factory("q"),), ctes=cycle))

    assert result.max_cte_depth > 0
    assert result.max_cte_depth <= 3


def test_counts_joins(calculator, entity_factory):
    joins = (
        ParsedJoin("INNER", condition="a.id = b.id"),
        ParsedJoin("LEFT", condition="a.id = c.id"),
        ParsedJoin("CROSS"),
        ParsedJoin("INNER"),
    )
    result = calculator.calculate(ParsedSQL(entities=(entity_factory("q", joins=joins),)))

    assert result.join_count == 4
    assert result.join_types.as_mapping()["INNER"] == 2
    assert result.join_types.as_mapping()["LEFT"] == 1
    assert result.join_types.as_mapping()["CROSS"] == 1
    assert result.cross_join_count == 1
    assert result.joins_without_condition == 2
    assert result.join_types.total == result.join_count


def test_counts_tables(calculator, entity_factory):
    reads = (table("orders"), table("orders"), table("customers"))
    writes = (table("orders", operation="insert"), table("archive", operation="insert"))
    entity = entity_factory("q", tables_read=reads, tables_written=writes)

    result = calculator.calculate(ParsedSQL(entities=(entity,)))

    assert result.table_reference_count == 5
    assert result.read_table_count == 3
    assert result.written_table_count == 2
    assert result.unique_table_count == 3
    assert result.unique_tables == ("dbo.archive", "dbo.customers", "dbo.orders")


def test_counts_dependencies(calculator, entity_factory):
    entity = entity_factory("q", dependencies=("table:orders", "table:orders", "view:summary"))

    result = calculator.calculate(ParsedSQL(entities=(entity,)))

    assert result.dependency_count == 2
    assert result.dependencies == ("table:orders", "view:summary")
    assert result.entities[0].dependency_count == 2


def test_calculates_fan_out(calculator, entity_factory):
    entities = (
        entity_factory("small", dependencies=("a",)),
        entity_factory("large", dependencies=("a", "b", "c", "c")),
    )

    result = calculator.calculate(ParsedSQL(entities=entities))

    assert result.dependency_fan_out == 3
    assert result.dependency_fan_out_by_object["sql_script:dbo.large"] == 3
    assert result.dependency_fan_out_by_object["sql_script:dbo.small"] == 1


def test_counts_called_procedures(calculator, entity_factory):
    called = ("procedure:dbo.validate_orders", "procedure:dbo.refresh_customers", "procedure:dbo.validate_orders")
    result = calculator.calculate(ParsedSQL(entities=(entity_factory("q", called_procedures=called),)))

    assert result.called_procedure_count == 2
    assert result.entities[0].called_procedure_count == 2
    assert result.entities[0].called_procedures == (
        "procedure:dbo.refresh_customers",
        "procedure:dbo.validate_orders",
    )


def test_counts_parse_issues(calculator, entity_factory):
    issues = (
        ParseIssue("PARSE-001", "bad syntax", severity="error"),
        ParseIssue("PARSE-002", "fallback", severity="warning"),
    )
    result = calculator.calculate(ParsedSQL(entities=(entity_factory("q"),), issues=issues))

    assert result.parse_error_count == 1
    assert result.warning_count == 1


def test_preserves_optional_fields(calculator, entity_factory):
    result = calculator.calculate(ParsedSQL(entities=(entity_factory("q"),)))
    entity = result.entities[0]

    for metrics in (result, entity):
        assert metrics.complexity_score is None
        assert metrics.content_hash is None
        assert metrics.semantic_hash is None
    assert entity.cte_reuse_index is None


def test_models_are_immutable(calculator, entity_factory):
    result = calculator.calculate(ParsedSQL(entities=(entity_factory("q"),)))

    assert is_dataclass(result)
    assert is_dataclass(result.entities[0])
    assert SQLMetrics.__dataclass_params__.frozen is True
    assert SQLEntityMetrics.__dataclass_params__.frozen is True
    assert isinstance(result.entities, tuple)
    assert isinstance(result.dependency_fan_out_by_object, Mapping)
    assert isinstance(result.entities[0].metadata.values, Mapping)
    assert isinstance(result.dependency_fan_out_by_object, MappingProxyType)

    with pytest.raises(FrozenInstanceError):
        result.entity_count = 99
    with pytest.raises(TypeError):
        result.dependency_fan_out_by_object["new"] = 1
    with pytest.raises(FrozenInstanceError):
        result.entities[0].name = "changed"

    assert all(field.name for field in fields(SQLMetrics))
