"""Calculate immutable metrics from parsed SQL structures."""

from __future__ import annotations

from collections import Counter
from typing import Mapping

from src.models.sql_metrics import SQLMetrics, SQLEntityMetrics
from src.monitor.scanners.sql_parser import (
    ParsedCTE,
    ParsedEntity,
    ParsedJoin,
    ParsedSQL,
    ParsedTable,
)


class SQLMetricsCalculator:
    """Build SQL metrics without mutating the parser output."""

    def calculate(self, parsed: ParsedSQL) -> SQLMetrics:
        entity_metrics = tuple(self._entity_metrics(entity) for entity in parsed.entities)
        all_tables_read = tuple(
            self._table_id(table) for entity in parsed.entities for table in entity.tables_read
        )
        all_tables_written = tuple(
            self._table_id(table) for entity in parsed.entities for table in entity.tables_written
        )
        table_references = (*all_tables_read, *all_tables_written)
        unique_tables = tuple(sorted(set(table_references)))

        join_counts = Counter(
            join_type
            for entity in parsed.entities
            for join_type in (self._join_type(join) for join in entity.joins)
        )
        joins = tuple(join for entity in parsed.entities for join in entity.joins)
        dependencies = tuple(
            sorted({dependency for entity in parsed.entities for dependency in entity.dependencies})
        )
        fan_out_by_object = {
            self._entity_id(entity, index): len(set(entity.dependencies))
            for index, entity in enumerate(parsed.entities)
        }
        issues = tuple(parsed.issues)
        parse_error_count = sum(1 for issue in issues if issue.severity.lower() == "error")
        warning_count = sum(1 for issue in issues if issue.severity.lower() == "warning")
        ctes = tuple(cte for entity in parsed.entities for cte in entity.ctes)
        ctes = (*ctes, *parsed.ctes)
        max_depth = self._max_cte_depth(ctes)
        called_procedures = tuple(
            sorted({procedure for entity in parsed.entities for procedure in entity.called_procedures})
        )

        return SQLMetrics(
            entity_count=len(parsed.entities),
            procedure_count=sum(entity.entity_type.lower() == "procedure" for entity in parsed.entities),
            view_count=sum(entity.entity_type.lower() == "view" for entity in parsed.entities),
            script_count=sum(entity.entity_type.lower() == "sql_script" for entity in parsed.entities),
            statement_count=parsed.statement_count,
            cte_count=len(ctes),
            recursive_cte_count=sum(cte.recursive for cte in ctes),
            max_cte_depth=max_depth,
            join_count=len(joins),
            join_types=dict(sorted(join_counts.items())),
            cross_join_count=join_counts["CROSS"],
            joins_without_condition=sum(join.condition is None for join in joins),
            table_reference_count=len(table_references),
            unique_table_count=len(unique_tables),
            read_table_count=len(all_tables_read),
            written_table_count=len(all_tables_written),
            dependency_count=len(dependencies),
            dependency_fan_out=max(fan_out_by_object.values(), default=0),
            dependency_fan_out_by_object=fan_out_by_object,
            called_procedure_count=len(called_procedures),
            parse_error_count=parse_error_count,
            warning_count=warning_count,
            tables_read=tuple(sorted(set(all_tables_read))),
            tables_written=tuple(sorted(set(all_tables_written))),
            unique_tables=unique_tables,
            dependencies=dependencies,
            entities=entity_metrics,
            complexity_score=None,
            content_hash=None,
            semantic_hash=None,
        )

    def _entity_metrics(self, entity: ParsedEntity) -> SQLEntityMetrics:
        reads = tuple(sorted({self._table_id(table) for table in entity.tables_read}))
        writes = tuple(sorted({self._table_id(table) for table in entity.tables_written}))
        references = (*reads, *writes)
        joins = tuple(entity.joins)
        join_counts = Counter(self._join_type(join) for join in joins)
        dependencies = tuple(sorted(set(entity.dependencies)))
        ctes = tuple(entity.ctes)
        cte_depth = self._max_cte_depth(ctes)
        entity_type = entity.entity_type.lower()
        return SQLEntityMetrics(
            name=entity.name,
            entity_type=entity.entity_type,
            statement_type=entity.statement_type,
            qualified_name=entity.qualified_name,
            statement_count=1,
            procedure_count=int(entity_type == "procedure"),
            view_count=int(entity_type == "view"),
            script_count=int(entity_type == "sql_script"),
            cte_count=len(ctes),
            recursive_cte_count=sum(cte.recursive for cte in ctes),
            max_cte_depth=cte_depth,
            join_count=len(joins),
            join_types=dict(sorted(join_counts.items())),
            cross_join_count=join_counts["CROSS"],
            joins_without_condition=sum(join.condition is None for join in joins),
            read_table_count=len(entity.tables_read),
            written_table_count=len(entity.tables_written),
            unique_table_count=len(set(references)),
            table_reference_count=len(references),
            dependency_count=len(dependencies),
            dependency_fan_out=len(dependencies),
            dependency_fan_out_by_object={self._entity_id(entity, 0): len(dependencies)},
            called_procedure_count=len(set(entity.called_procedures)),
            tables_read=reads,
            tables_written=writes,
            dependencies=dependencies,
            called_procedures=tuple(sorted(set(entity.called_procedures))),
            cte_names=tuple(sorted(cte.name for cte in ctes)),
            cte_reuse_index=None,
            parse_error_count=0,
            warning_count=0,
            complexity_score=None,
            content_hash=None,
            semantic_hash=None,
        )

    @staticmethod
    def _table_id(table: ParsedTable) -> str:
        return ".".join(
            value for value in (table.database, table.schema, table.name) if value
        )

    @staticmethod
    def _join_type(join: ParsedJoin) -> str:
        value = (join.join_type or "").strip().upper().replace(" JOIN", "")
        aliases = {
            "": "UNKNOWN",
            "INNER JOIN": "INNER",
            "LEFT OUTER": "LEFT",
            "RIGHT OUTER": "RIGHT",
            "FULL OUTER": "FULL",
        }
        value = aliases.get(value, value)
        return value if value in {"INNER", "LEFT", "RIGHT", "FULL", "CROSS", "NATURAL"} else "UNKNOWN"

    @staticmethod
    def _entity_id(entity: ParsedEntity, index: int) -> str:
        if entity.qualified_name:
            return f"{entity.entity_type}:{entity.qualified_name}"
        return f"{entity.entity_type}:{entity.name or 'statement'}:{index}"

    @classmethod
    def _max_cte_depth(cls, ctes: tuple[ParsedCTE, ...]) -> int:
        if not ctes:
            return 0
        by_name = {cte.name: cte for cte in ctes}
        visiting: set[str] = set()
        visited: dict[str, int] = {}

        def depth(name: str) -> int:
            if name in visited:
                return visited[name]
            if name in visiting:
                return 1
            cte = by_name.get(name)
            if cte is None:
                return 1
            visiting.add(name)
            result = 1 + max((depth(reference) for reference in cte.references), default=0)
            visiting.remove(name)
            visited[name] = result
            return result

        return max(depth(cte.name) for cte in ctes)


__all__ = ["SQLMetricsCalculator"]
