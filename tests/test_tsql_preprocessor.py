"""Tests for the T-SQL preprocessing layer."""

from src.monitor.scanners.tsql_preprocessor import TSQLPreprocessor


def test_removes_go_batch_separator() -> None:
    sql = """
SELECT * FROM dbo.orders
GO
SELECT * FROM dbo.customers
GO
"""

    result = TSQLPreprocessor().process(sql)

    assert "\nGO\n" not in result
    assert "SELECT * FROM dbo.orders" in result
    assert "SELECT * FROM dbo.customers" in result


def test_removes_parser_irrelevant_session_settings() -> None:
    sql = """
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE PROC dbo.refresh_orders
AS
SELECT * FROM dbo.orders
"""

    result = TSQLPreprocessor().process(sql)

    assert "SET ANSI_NULLS" not in result
    assert "SET QUOTED_IDENTIFIER" not in result
    assert "\nGO\n" not in result
    assert "CREATE PROC dbo.refresh_orders" in result
    assert "SELECT * FROM dbo.orders" in result


def test_preserves_exec_statements() -> None:
    sql = """
CREATE PROC dbo.refresh_orders
AS
BEGIN
    EXEC dbo.sp_assert_quality
    EXEC dbo.sp_insert_table
END
"""

    result = TSQLPreprocessor().process(sql)

    assert "EXEC dbo.sp_assert_quality" in result
    assert "EXEC dbo.sp_insert_table" in result


def test_preserves_write_operations() -> None:
    sql = """
UPDATE dbo.orders
SET status = 'processed';

DELETE FROM dbo.order_staging;
"""

    result = TSQLPreprocessor().process(sql)

    assert "UPDATE dbo.orders" in result
    assert "DELETE FROM dbo.order_staging" in result


def test_preserves_create_and_alter_procedure() -> None:
    preprocessor = TSQLPreprocessor()

    create_sql = """
CREATE PROC dbo.proc_a
AS
SELECT * FROM dbo.table_a
"""

    alter_sql = """
ALTER PROC dbo.proc_b
AS
SELECT * FROM dbo.table_b
"""

    assert "CREATE PROC dbo.proc_a" in preprocessor.process(create_sql)
    assert "ALTER PROC dbo.proc_b" in preprocessor.process(alter_sql)


def test_empty_sql_is_preserved() -> None:
    assert TSQLPreprocessor().process("") == ""
    assert TSQLPreprocessor().process("   ") == "   "