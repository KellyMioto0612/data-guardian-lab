"""Deterministic SQL technical-debt evidence rules."""

from __future__ import annotations

import hashlib
import re

from src.models.evidence import Evidence, EvidenceSeverity
from src.monitor.scanners.sql_parser import ParsedEntity


class SQLEvidenceAnalyzer:
    """Produce explainable findings without preserving SQL fragments in output."""

    _SELECT_STAR = re.compile(
        r"(?is)\bSELECT\s+(?:DISTINCT\s+)?(?:[\[\]\w]+\s*\.\s*)?\*"
        r"|,\s*[\[\]\w]+\s*\.\s*\*"
    )
    _DYNAMIC_EXEC = re.compile(r"(?is)\bEXEC(?:UTE)?\s*\(")
    _SUBQUERY = re.compile(r"(?is)\(\s*SELECT\b")
    _TEMPORARY_TABLE = re.compile(r"(?<!\w)#\w+")
    _COMMENT = re.compile(r"(?s)(?:--[^\n]*|/\*.*?\*/)")

    def analyze(self, entity: ParsedEntity) -> tuple[Evidence, ...]:
        object_id = entity.qualified_name or entity.entity_fingerprint_seed or "statement"
        findings: list[tuple[str, EvidenceSeverity, str, int | None]] = []
        normalized = entity.normalized_sql or ""
        if self._SELECT_STAR.search(normalized):
            findings.append(
                ("SQL-001", EvidenceSeverity.MEDIUM, "SELECT * usage", entity.line_start)
            )
        if any(join.join_type.upper() == "CROSS" for join in entity.joins):
            findings.append(
                ("SQL-002", EvidenceSeverity.HIGH, "CROSS JOIN usage", entity.line_start)
            )
        if any(
            join.condition is None and join.join_type.upper() != "CROSS" for join in entity.joins
        ):
            findings.append(
                ("SQL-003", EvidenceSeverity.MEDIUM, "JOIN without condition", entity.line_start)
            )
        if self._DYNAMIC_EXEC.search(normalized):
            findings.append(
                ("SQL-004", EvidenceSeverity.HIGH, "Dynamic EXEC usage", entity.line_start)
            )
        if entity.source == "regex_fallback":
            findings.append(
                ("SQL-005", EvidenceSeverity.LOW, "Reduced parser confidence", entity.line_start)
            )
        structural_complexity = (
            len(entity.joins)
            + (2 * len(entity.ctes))
            + (2 * len(self._SUBQUERY.findall(normalized)))
            + len(entity.called_procedures)
        )
        if structural_complexity >= 8:
            findings.append(
                (
                    "SQL-006",
                    EvidenceSeverity.MEDIUM,
                    "High structural complexity",
                    entity.line_start,
                )
            )
        if len(self._SUBQUERY.findall(normalized)) >= 2:
            findings.append(
                ("SQL-007", EvidenceSeverity.LOW, "Multiple subquery patterns", entity.line_start)
            )
        if self._TEMPORARY_TABLE.search(normalized):
            findings.append(
                ("SQL-008", EvidenceSeverity.LOW, "Temporary table usage", entity.line_start)
            )
        if entity.entity_type in {"procedure", "view"} and not self._COMMENT.search(normalized):
            findings.append(
                (
                    "SQL-009",
                    EvidenceSeverity.LOW,
                    "Missing object documentation comment",
                    entity.line_start,
                )
            )
        if self._has_unbounded_write(normalized):
            findings.append(
                (
                    "SQL-010",
                    EvidenceSeverity.HIGH,
                    "Write operation without WHERE filter",
                    entity.line_start,
                )
            )
        return tuple(
            self._evidence(object_id, rule, severity, summary, line)
            for rule, severity, summary, line in findings
        )

    @staticmethod
    def _evidence(
        object_id: str,
        rule_id: str,
        severity: EvidenceSeverity,
        summary: str,
        line_start: int | None,
    ) -> Evidence:
        seed = f"{object_id}:{rule_id}:{line_start or 0}".encode()
        evidence_id = hashlib.sha256(seed).hexdigest()[:16]
        return Evidence(
            evidence_id=evidence_id,
            rule_id=rule_id,
            object_id=object_id,
            severity=severity,
            summary=summary,
            line_start=line_start,
        )

    @staticmethod
    def _has_unbounded_write(sql: str) -> bool:
        statements = (part.strip() for part in sql.split(";") if part.strip())
        return any(
            re.match(r"(?is)^(?:UPDATE\s+|DELETE\s+FROM\s+)", statement)
            and not re.search(r"(?is)\bWHERE\b", statement)
            for statement in statements
        )


__all__ = ["SQLEvidenceAnalyzer"]
