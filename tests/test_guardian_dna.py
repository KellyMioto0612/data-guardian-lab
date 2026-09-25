"""Tests for structural SQL similarity candidates."""

from src.analyzers.guardian_dna import GuardianDNAAnalyzer
from src.monitor.scanners.sql_parser import SQLParser


def test_detects_structurally_similar_views_without_sql_output() -> None:
    parsed = SQLParser().parse(
        """
        CREATE VIEW dbo.v_orders_a AS
        SELECT DISTINCT CASE WHEN a.status = 'x' THEN 1 END AS state
        FROM dbo.orders_a AS a
        WHERE a.active = 1
        GROUP BY a.status;

        CREATE VIEW dbo.v_orders_b AS
        SELECT DISTINCT CASE WHEN b.status = 'y' THEN 1 END AS state
        FROM dbo.orders_b AS b
        WHERE b.active = 1
        GROUP BY b.status;
        """
    )

    candidates = GuardianDNAAnalyzer().find_similar(parsed.entities)

    assert len(candidates) == 1
    assert candidates[0].score >= 0.8
    assert "SELECT" not in candidates[0].left_object_id


def test_different_asset_types_are_not_compared() -> None:
    parsed = SQLParser().parse(
        "CREATE VIEW dbo.v_a AS SELECT * FROM dbo.a; "
        "CREATE PROCEDURE dbo.p_a AS SELECT * FROM dbo.b;"
    )

    assert not GuardianDNAAnalyzer().find_similar(parsed.entities)
