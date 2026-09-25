"""Tests for explainable SQL technical-debt findings."""

from src.analyzers.sql_evidence import SQLEvidenceAnalyzer
from src.analyzers.tdi_engine import TDIClass, calculate_tdi
from src.monitor.scanners.sql_parser import SQLParser


def test_select_star_creates_non_sensitive_evidence() -> None:
    entity = SQLParser().parse("CREATE VIEW dbo.v_orders AS SELECT * FROM dbo.orders").entities[0]

    evidence = SQLEvidenceAnalyzer().analyze(entity)

    assert [(item.rule_id, item.severity) for item in evidence] == [
        ("SQL-001", "medium"),
        ("SQL-009", "low"),
    ]
    assert "dbo.orders" not in evidence[0].summary


def test_dynamic_execution_is_high_debt() -> None:
    entity = SQLParser().parse("EXEC(N'SELECT 1')").entities[0]

    evidence = SQLEvidenceAnalyzer().analyze(entity)
    result = calculate_tdi(evidence)

    assert evidence[0].rule_id == "SQL-004"
    assert result.score == 30.0
    assert result.classification is TDIClass.MODERATE


def test_advanced_rules_cover_documentation_temporary_tables_and_unbounded_writes() -> None:
    entity = SQLParser().parse(
        """
        CREATE PROCEDURE dbo.refresh_orders AS
        BEGIN
            SELECT * INTO #staged_orders FROM dbo.orders;
            UPDATE dbo.orders SET refreshed_at = GETUTCDATE();
        END
        """
    ).entities[0]

    evidence = SQLEvidenceAnalyzer().analyze(entity)

    assert {item.rule_id for item in evidence} >= {"SQL-001", "SQL-005", "SQL-008", "SQL-009"}


def test_qualified_select_star_is_reported_without_confusing_count_star() -> None:
    parser = SQLParser()
    analyzer = SQLEvidenceAnalyzer()
    qualified = parser.parse("CREATE VIEW dbo.v AS SELECT a.* FROM dbo.orders a").entities[0]
    aggregate = parser.parse(
        "CREATE VIEW dbo.v AS SELECT COUNT(*) AS n FROM dbo.orders"
    ).entities[0]

    assert "SQL-001" in {item.rule_id for item in analyzer.analyze(qualified)}
    assert "SQL-001" not in {item.rule_id for item in analyzer.analyze(aggregate)}


def test_deployment_exec_is_not_attributed_to_view() -> None:
    sql = "EXEC(N'DROP PROC dbo.old_view'); CREATE VIEW dbo.v AS SELECT 1 AS id"
    view = next(
        entity for entity in SQLParser().parse(sql).entities if entity.entity_type == "view"
    )

    assert "SQL-004" not in {item.rule_id for item in SQLEvidenceAnalyzer().analyze(view)}
