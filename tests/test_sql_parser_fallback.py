"""Contract tests for SQL parser fallback and real T-SQL structures."""

import pytest

from src.monitor.scanners.sql_parser import SQLParser


@pytest.mark.parametrize(
    ("sql", "operation"),
    [
        ("DELETE FROM dbo.orders", "delete"),
        ("INSERT INTO dbo.orders SELECT 1", "insert"),
        ("UPDATE dbo.orders SET status = 'archived'", "update"),
        (
            "MERGE INTO dbo.orders AS target "
            "USING dbo.source AS source ON 1 = 1",
            "merge",
        ),
    ],
)
def test_regex_fallback_preserves_write_operations(
    monkeypatch,
    sql: str,
    operation: str,
) -> None:
    def forced_parser_failure(*_args, **_kwargs):
        raise ValueError("forced parser failure")

    monkeypatch.setattr(
        "src.monitor.scanners.sql_parser.sqlglot.parse",
        forced_parser_failure,
    )

    result = SQLParser().parse(sql)

    assert result.fallback_statement_count == 1
    assert result.tables_written
    assert result.tables_written[0].operation == operation


def test_procedure_name_is_normalized() -> None:
    sql = """
    CREATE PROC [guardian_dw].[sp_test_guardian]
    AS
    BEGIN
        SELECT *
        FROM guardian_dw.d_account;
    END
    """

    result = SQLParser().parse(sql)

    procedures = [
        entity
        for entity in result.entities
        if entity.entity_type == "procedure"
    ]

    assert len(procedures) == 1

    procedure = procedures[0]

    assert procedure.name == "sp_test_guardian"
    assert procedure.schema == "guardian_dw"
    assert procedure.qualified_name == "guardian_dw.sp_test_guardian"


def test_tsql_view_is_recognized_as_asset() -> None:
    sql = """
    CREATE VIEW guardian_dw.v_test_guardian
    AS
    SELECT *
    FROM guardian_dw.d_account;
    """

    result = SQLParser().parse(sql)

    views = [
        entity
        for entity in result.entities
        if entity.entity_type == "view"
    ]

    assert len(views) == 1

    view = views[0]

    assert view.name == "v_test_guardian"
    assert view.schema == "guardian_dw"
    assert view.qualified_name == "guardian_dw.v_test_guardian"


def test_tsql_procedure_body_belongs_to_single_asset() -> None:
    sql = """
    CREATE PROC [guardian_dw].[sp_complex_guardian]
        @params VARCHAR(1000)
    AS
    BEGIN
        SET NOCOUNT ON;

        DECLARE @reason NVARCHAR(20);

        SELECT *
        FROM guardian_dw.d_account;

        UPDATE guardian_dw.a_account
        SET dt_load = GETDATE();

        EXEC [guardian_dw].[sp_assert_quality];

        EXEC [guardian_dw].[sp_insert_table];
    END
    """

    result = SQLParser().parse(sql)

    procedures = [
        entity
        for entity in result.entities
        if entity.entity_type == "procedure"
    ]

    assert len(procedures) == 1

    procedure = procedures[0]

    assert procedure.name == "sp_complex_guardian"
    assert procedure.schema == "guardian_dw"
    assert procedure.qualified_name == "guardian_dw.sp_complex_guardian"
    assert procedure.source == "regex_fallback"
    assert procedure.confidence_score == 0.7
    assert {table.operation for table in procedure.tables_written} == {"update"}
    assert set(procedure.called_procedures) == {
        "[guardian_dw].[sp_assert_quality]",
        "[guardian_dw].[sp_insert_table]",
    }


def test_sqlglot_warning_does_not_log_sql_content(caplog: pytest.LogCaptureFixture) -> None:
    SQLParser().parse("EXEC dbo.private_operation @token = 'do-not-log'")

    assert "do-not-log" not in caplog.text


def test_unsupported_view_body_keeps_asset_identity() -> None:
    sql = (
        "CREATE VIEW dbo.v_example AS SELECT id FROM dbo.orders ORDER BY id DESC\n"
        "SELECT id FROM dbo.orders"
    )

    result = SQLParser().parse(sql)

    assert len(result.entities) == 1
    assert result.entities[0].entity_type == "view"
    assert result.entities[0].qualified_name == "dbo.v_example"
    assert result.entities[0].source == "regex_fallback"
    assert any(issue.code == "PARSE-002" for issue in result.issues)
