"""Calculate immutable metrics from parsed SQL structures."""

from __future__ import annotations

from collections import Counter

from src.models.sql_metrics import SQLEntityMetrics, SQLMetrics
from src.monitor.scanners.sql_parser import (
    ParsedCTE,
    ParsedEntity,
    ParsedJoin,
    ParsedSQL,
    ParsedTable,
)


class SQLMetricsCalculator:
    """Build metrics without mutating parser output."""

    def calculate(self, parsed: ParsedSQL) -> SQLMetrics:
        entities = tuple(parsed.entities)
        entity_metrics = tuple(self._entity_metrics(entity) for entity in entities)
        reads = tuple(self._table_id(table) for entity in entities for table in entity.tables_read)
        writes = tuple(
            self._table_id(table) for entity in entities for table in entity.tables_written
        )
        joins = tuple(join for entity in entities for join in entity.joins)
        join_types = Counter(self._join_type(join) for join in joins)
        dependencies = tuple(sorted({item for entity in entities for item in entity.dependencies}))
        fan_out_by_object = {
            self._entity_id(entity): len(set(entity.dependencies)) for entity in entities
        }
        called = tuple(sorted({item for entity in entities for item in entity.called_procedures}))
        ctes = self._aggregate_ctes(parsed)
        errors = sum(issue.severity.lower() == "error" for issue in parsed.issues)
        warnings = sum(issue.severity.lower() == "warning" for issue in parsed.issues)
        unique_tables = tuple(sorted(set((*reads, *writes))))
        return SQLMetrics(
            entity_count=len(entities),
            procedure_count=sum(self._is_type(entity, "procedure") for entity in entities),
            view_count=sum(self._is_type(entity, "view") for entity in entities),
            script_count=sum(self._is_type(entity, "sql_script") for entity in entities),
            statement_count=parsed.statement_count,
            cte_count=len(ctes),
            recursive_cte_count=sum(cte.recursive for cte in ctes),
            max_cte_depth=self._max_cte_depth(ctes),
            join_count=len(joins),
            join_types=dict(sorted(join_types.items())),
            cross_join_count=join_types["CROSS"],
            joins_without_condition=sum(join.condition is None for join in joins),
            table_reference_count=len(reads) + len(writes),
            unique_table_count=len(unique_tables),
            read_table_count=len(reads),
            written_table_count=len(writes),
            dependency_count=len(dependencies),
            dependency_fan_out=max(fan_out_by_object.values(), default=0),
            dependency_fan_out_by_object=fan_out_by_object,
            called_procedure_count=len(called),
            parse_error_count=errors,
            warning_count=warnings,
            tables_read=tuple(sorted(set(reads))),
            tables_written=tuple(sorted(set(writes))),
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
        joins = tuple(entity.joins)
        join_types = Counter(self._join_type(join) for join in joins)
        dependencies = tuple(sorted(set(entity.dependencies)))
        ctes = tuple(entity.ctes)
        called = tuple(sorted(set(entity.called_procedures)))
        return SQLEntityMetrics(
            name=entity.name,
            entity_type=entity.entity_type,
            statement_type=entity.statement_type,
            qualified_name=entity.qualified_name,
            statement_count=1,
            procedure_count=int(self._is_type(entity, "procedure")),
            view_count=int(self._is_type(entity, "view")),
            script_count=int(self._is_type(entity, "sql_script")),
            cte_count=len(ctes),
            recursive_cte_count=sum(cte.recursive for cte in ctes),
            max_cte_depth=self._max_cte_depth(ctes),
            join_count=len(joins),
            join_types=dict(sorted(join_types.items())),
            cross_join_count=join_types["CROSS"],
            joins_without_condition=sum(join.condition is None for join in joins),
            read_table_count=len(entity.tables_read),
            written_table_count=len(entity.tables_written),
            unique_table_count=len(set((*reads, *writes))),
            table_reference_count=len(entity.tables_read) + len(entity.tables_written),
            dependency_count=len(dependencies),
            dependency_fan_out=len(dependencies),
            dependency_fan_out_by_object={self._entity_id(entity): len(dependencies)},
            called_procedure_count=len(called),
            tables_read=reads,
            tables_written=writes,
            dependencies=dependencies,
            called_procedures=called,
            cte_names=tuple(sorted(cte.name for cte in ctes)),
            cte_reuse_index=None,
            parse_error_count=0,
            warning_count=0,
            complexity_score=None,
            content_hash=None,
            semantic_hash=None,
        )

    @staticmethod
    def _aggregate_ctes(parsed: ParsedSQL) -> tuple[ParsedCTE, ...]:
        return (
            tuple(parsed.ctes)
            if parsed.ctes
            else tuple(cte for entity in parsed.entities for cte in entity.ctes)
        )

    @staticmethod
    def _is_type(entity: ParsedEntity, expected: str) -> bool:
        return entity.entity_type.strip().lower() == expected

    @staticmethod
    def _table_id(table: ParsedTable) -> str:
        return ".".join(value for value in (table.database, table.schema, table.name) if value)

    @staticmethod
    def _join_type(join: ParsedJoin) -> str:
        value = (join.join_type or "").strip().upper().replace(" JOIN", "")
        value = {
            "": "UNKNOWN",
            "LEFT OUTER": "LEFT",
            "RIGHT OUTER": "RIGHT",
            "FULL OUTER": "FULL",
        }.get(value, value)
        return (
            value if value in {"INNER", "LEFT", "RIGHT", "FULL", "CROSS", "NATURAL"} else "UNKNOWN"
        )

    @staticmethod
    def _entity_id(entity: ParsedEntity) -> str:
        return f"{entity.entity_type}:{entity.qualified_name or entity.name or 'statement'}"

    @classmethod
    def _max_cte_depth(cls, ctes: tuple[ParsedCTE, ...]) -> int:
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
            result = 1 + max((depth(ref) for ref in cte.references), default=0)
            visiting.remove(name)
            visited[name] = result
            return result

        return max((depth(cte.name) for cte in ctes), default=0)


__all__ = ["SQLMetricsCalculator"]
