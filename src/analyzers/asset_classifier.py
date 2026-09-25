"""Classify parsed SQL entities for Guardian knowledge modeling."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.monitor.scanners.sql_parser import ParsedEntity


class AssetCategory(StrEnum):
    """Semantic role of an entity discovered during SQL analysis."""

    ASSET = "asset"
    INTERNAL = "internal"
    STATEMENT = "statement"
    LOW_CONFIDENCE = "low_confidence"
    NOISE = "noise"


@dataclass(frozen=True)
class AssetClassification:
    """Classification result with an explicit reason."""

    category: AssetCategory
    reason: str
    confidence_score: float

    @property
    def include_in_knowledge_graph(self) -> bool:
        """Return whether the entity can represent a graph-level asset."""
        return self.category is AssetCategory.ASSET


class AssetClassifier:
    """Classify parsed entities without changing parser output."""

    _PERSISTENT_TYPES = frozenset(
        {
            "procedure",
            "view",
        }
    )

    _STATEMENT_TYPES = frozenset(
        {
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "MERGE",
            "DECLARE",
            "DROP",
            "EXEC",
            "EXECUTE",
            "SEMICOLON",
        }
    )

    _NOISE_STATEMENTS = frozenset(
        {
            "END",
            "GO",
        }
    )

    def classify(self, entity: ParsedEntity) -> AssetClassification:
        """Classify one parsed entity from explicit structural evidence."""
        confidence = float(entity.confidence_score)

        if entity.entity_type in self._PERSISTENT_TYPES:
            return AssetClassification(
                category=AssetCategory.ASSET,
                reason=f"persistent SQL object: {entity.entity_type}",
                confidence_score=confidence,
            )

        statement_type = (entity.statement_type or "").strip().upper()
        normalized_sql = (entity.normalized_sql or "").strip()

        if self._is_noise(statement_type, normalized_sql):
            return AssetClassification(
                category=AssetCategory.NOISE,
                reason="batch/parser artifact without asset identity",
                confidence_score=confidence,
            )

        if self._has_temporary_structure(entity):
            return AssetClassification(
                category=AssetCategory.INTERNAL,
                reason="temporary SQL structure",
                confidence_score=confidence,
            )

        if statement_type in self._STATEMENT_TYPES:
            return AssetClassification(
                category=AssetCategory.STATEMENT,
                reason=f"SQL statement: {statement_type}",
                confidence_score=confidence,
            )

        if confidence < 1.0:
            return AssetClassification(
                category=AssetCategory.LOW_CONFIDENCE,
                reason="fallback entity without reliable persistent identity",
                confidence_score=confidence,
            )

        return AssetClassification(
            category=AssetCategory.STATEMENT,
            reason="non-persistent SQL construct",
            confidence_score=confidence,
        )

    @classmethod
    def _is_noise(cls, statement_type: str, normalized_sql: str) -> bool:
        if statement_type in cls._NOISE_STATEMENTS:
            return True

        normalized_upper = normalized_sql.upper().strip()

        return normalized_upper in cls._NOISE_STATEMENTS

    @staticmethod
    def _has_temporary_structure(entity: ParsedEntity) -> bool:
        names: list[str] = []

        if entity.name:
            names.append(str(entity.name))

        if entity.qualified_name:
            names.append(str(entity.qualified_name))

        names.extend(table.name for table in entity.tables_read)
        names.extend(table.name for table in entity.tables_written)

        return any(name.strip().startswith("#") for name in names)


__all__ = [
    "AssetCategory",
    "AssetClassification",
    "AssetClassifier",
]