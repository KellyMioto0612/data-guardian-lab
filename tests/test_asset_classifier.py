"""Tests for semantic SQL entity classification."""

import pytest

from src.analyzers.asset_classifier import AssetCategory, AssetClassifier
from src.monitor.scanners.sql_parser import ParsedEntity, ParsedTable


@pytest.fixture
def classifier() -> AssetClassifier:
    return AssetClassifier()


def entity(
    *,
    entity_type: str = "sql_script",
    statement_type: str = "UNKNOWN",
    name: str | None = None,
    normalized_sql: str | None = None,
    confidence_score: float = 1.0,
    tables_read: tuple[ParsedTable, ...] = (),
    tables_written: tuple[ParsedTable, ...] = (),
) -> ParsedEntity:
    return ParsedEntity(
        name=name,
        entity_type=entity_type,
        statement_type=statement_type,
        normalized_sql=normalized_sql,
        confidence_score=confidence_score,
        tables_read=tables_read,
        tables_written=tables_written,
    )


def test_procedure_is_persistent_asset(classifier: AssetClassifier) -> None:
    result = classifier.classify(
        entity(
            entity_type="procedure",
            statement_type="CREATE_PROCEDURE",
            name="sp_refresh_orders",
            confidence_score=0.4,
        )
    )

    assert result.category is AssetCategory.ASSET
    assert result.include_in_knowledge_graph is True


def test_view_is_persistent_asset(classifier: AssetClassifier) -> None:
    result = classifier.classify(
        entity(
            entity_type="view",
            statement_type="CREATE_VIEW",
            name="v_active_orders",
        )
    )

    assert result.category is AssetCategory.ASSET


@pytest.mark.parametrize("value", ["END", "GO"])
def test_batch_artifacts_are_noise(
    classifier: AssetClassifier,
    value: str,
) -> None:
    result = classifier.classify(
        entity(
            statement_type="UNKNOWN",
            normalized_sql=value,
            confidence_score=0.4,
        )
    )

    assert result.category is AssetCategory.NOISE
    assert result.include_in_knowledge_graph is False


def test_temporary_table_is_internal(classifier: AssetClassifier) -> None:
    result = classifier.classify(
        entity(
            statement_type="DROP",
            tables_read=(ParsedTable(name="#tmp_orders"),),
        )
    )

    assert result.category is AssetCategory.INTERNAL


@pytest.mark.parametrize(
    "statement_type",
    [
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "MERGE",
        "DECLARE",
        "DROP",
        "EXEC",
    ],
)
def test_sql_operations_are_statements(
    classifier: AssetClassifier,
    statement_type: str,
) -> None:
    result = classifier.classify(
        entity(statement_type=statement_type)
    )

    assert result.category is AssetCategory.STATEMENT
    assert result.include_in_knowledge_graph is False


def test_unknown_fallback_is_low_confidence(
    classifier: AssetClassifier,
) -> None:
    result = classifier.classify(
        entity(
            statement_type="UNKNOWN",
            normalized_sql="some unsupported T-SQL fragment",
            confidence_score=0.4,
        )
    )

    assert result.category is AssetCategory.LOW_CONFIDENCE
    assert result.include_in_knowledge_graph is False


def test_confidence_is_preserved(
    classifier: AssetClassifier,
) -> None:
    result = classifier.classify(
        entity(
            entity_type="procedure",
            confidence_score=0.4,
        )
    )

    assert result.confidence_score == 0.4