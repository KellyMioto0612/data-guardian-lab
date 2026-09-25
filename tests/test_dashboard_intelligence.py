"""Tests for the dashboard's safe SQL intelligence presentation data."""

from pathlib import Path

from src.dashboard.app import evidence_rows, load_sql_intelligence, technical_debt_rows

FIXTURES = Path(__file__).parent / "fixtures" / "sql"


def test_dashboard_loads_local_sql_intelligence() -> None:
    result = load_sql_intelligence(FIXTURES)

    assert result.guardian_objects
    assert result.evidence


def test_dashboard_rows_exclude_raw_sql_content() -> None:
    result = load_sql_intelligence(FIXTURES)
    evidence = evidence_rows(result)
    debt = technical_debt_rows(result)

    assert evidence
    assert debt
    assert "SQL" not in evidence[0]
    assert "normalized_sql" not in debt[0]
    assert {"Ativo", "TDI", "Evidências"} <= set(debt[0])
