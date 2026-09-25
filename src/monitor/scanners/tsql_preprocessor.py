"""Pre-processing utilities for SQL Server/Synapse T-SQL scripts."""

from __future__ import annotations

import re


class TSQLPreprocessor:
    """Prepare T-SQL scripts for structural parsing without changing semantics."""

    _GO_PATTERN = re.compile(r"(?im)^\s*GO\s*;?\s*$")

    _SESSION_SETTING_PATTERN = re.compile(
        r"(?im)^\s*SET\s+"
        r"(?:ANSI_NULLS|QUOTED_IDENTIFIER)\s+"
        r"(?:ON|OFF)\s*;?\s*$"
    )

    def process(self, sql: str) -> str:
        """Return SQL with parser-irrelevant batch/session directives removed."""
        if not sql.strip():
            return sql

        processed = self._GO_PATTERN.sub("", sql)
        processed = self._SESSION_SETTING_PATTERN.sub("", processed)

        return processed.strip()