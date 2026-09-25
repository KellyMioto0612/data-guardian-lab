from pathlib import Path

import pytest

from src.monitor.scanners.sql_scanner import SQLScanner


def test_rejects_paths_outside_the_explicit_allowed_root(tmp_path: Path) -> None:
    scanner = SQLScanner(allowed_root=tmp_path)

    with pytest.raises(ValueError, match="outside the allowed root"):
        scanner.scan_file(tmp_path.parent / "outside.sql")


def test_error_message_withholds_sql_content() -> None:
    error = ValueError("SELECT confidential_value FROM private_table")

    message = SQLScanner._error(error)

    assert message == "ValueError: SQL content withheld"
