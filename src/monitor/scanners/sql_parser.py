"""SQL parsing foundation for Data Guardian."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from types import MappingProxyType

import sqlglot
from sqlglot import exp


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(value))


def _dedupe(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _make_entity_id(
    entity_type: str, qualified_name: str | None, name: str | None, index: int | None = None
) -> str:
    identity = (
        qualified_name or name or (f"statement:{index}" if index is not None else "statement")
    )
    return f"{entity_type}:{identity}"


def _make_table_id(database: str | None, schema: str | None, name: str) -> str:
    return ".".join(part for part in (database, schema, name) if part)


def _make_cte_id(owner_id: str, name: str) -> str:
    return f"cte:{owner_id}:{name}"


def _table_seed(table: ParsedTable) -> str:
    return _make_table_id(table.database, table.schema, table.name)


def _join_seed(join: ParsedJoin) -> str:
    return repr((join.join_type, join.left, join.right, join.condition))


def _cte_seed(cte: ParsedCTE) -> str:
    return repr(
        (
            cte.name,
            cte.recursive,
            tuple(sorted(cte.references)),
            tuple(sorted(_table_seed(table) for table in cte.tables)),
            cte.normalized_sql,
        )
    )


def _fingerprint_seed(
    entity_type: str,
    statement_type: str,
    qualified_name: str | None,
    normalized_sql: str | None,
    tables_read: tuple[ParsedTable, ...],
    tables_written: tuple[ParsedTable, ...],
    ctes: tuple[ParsedCTE, ...],
    joins: tuple[ParsedJoin, ...],
    dependencies: tuple[str, ...],
    called_procedures: tuple[str, ...],
) -> str:
    return repr(
        (
            entity_type,
            statement_type,
            qualified_name,
            normalized_sql,
            tuple(sorted(_table_seed(table) for table in tables_read)),
            tuple(sorted(_table_seed(table) for table in tables_written)),
            tuple(sorted(_cte_seed(cte) for cte in ctes)),
            tuple(sorted(_join_seed(join) for join in joins)),
            tuple(sorted(dependencies)),
            tuple(called_procedures),
        )
    )


@dataclass(frozen=True)
class ParseIssue:
    code: str
    message: str
    line: int | None = None
    column: int | None = None
    statement_index: int | None = None
    severity: str = "error"
    parse_mode: str = "ast"
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class ParsedTable:
    name: str
    schema: str | None = None
    database: str | None = None
    alias: str | None = None
    operation: str = "read"
    source: str = "ast"
    confidence_score: float = 1.0
    line_start: int | None = None
    line_end: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class ParsedJoin:
    join_type: str
    left: str | None = None
    right: str | None = None
    condition: str | None = None
    source: str = "ast"
    confidence_score: float = 1.0
    line_start: int | None = None
    line_end: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class ParsedCTE:
    name: str
    recursive: bool = False
    references: tuple[str, ...] = ()
    tables: tuple[ParsedTable, ...] = ()
    normalized_sql: str | None = None
    source: str = "ast"
    confidence_score: float = 1.0
    line_start: int | None = None
    line_end: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "references", _dedupe(tuple(self.references)))
        object.__setattr__(self, "tables", tuple(self.tables))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class ParsedEntity:
    name: str | None
    entity_type: str
    statement_type: str
    qualified_name: str | None = None
    schema: str | None = None
    database: str | None = None
    alias: str | None = None
    tables_read: tuple[ParsedTable, ...] = ()
    tables_written: tuple[ParsedTable, ...] = ()
    ctes: tuple[ParsedCTE, ...] = ()
    joins: tuple[ParsedJoin, ...] = ()
    dependencies: tuple[str, ...] = ()
    called_procedures: tuple[str, ...] = ()
    normalized_sql: str | None = None
    entity_fingerprint_seed: str | None = None
    source: str = "ast"
    confidence_score: float = 1.0
    line_start: int | None = None
    line_end: int | None = None
    statement_index: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        tables_read = tuple(self.tables_read)
        tables_written = tuple(self.tables_written)
        ctes = tuple(self.ctes)
        joins = tuple(self.joins)
        dependencies = tuple(sorted(set(self.dependencies)))
        called = _dedupe(tuple(self.called_procedures))
        seed = self.entity_fingerprint_seed or _fingerprint_seed(
            self.entity_type,
            self.statement_type,
            self.qualified_name,
            self.normalized_sql,
            tables_read,
            tables_written,
            ctes,
            joins,
            dependencies,
            called,
        )
        object.__setattr__(self, "tables_read", tables_read)
        object.__setattr__(self, "tables_written", tables_written)
        object.__setattr__(self, "ctes", ctes)
        object.__setattr__(self, "joins", joins)
        object.__setattr__(self, "dependencies", dependencies)
        object.__setattr__(self, "called_procedures", called)
        object.__setattr__(self, "entity_fingerprint_seed", seed)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class ParsedSQL:
    entities: tuple[ParsedEntity, ...] = ()
    ctes: tuple[ParsedCTE, ...] = ()
    joins: tuple[ParsedJoin, ...] = ()
    tables_read: tuple[ParsedTable, ...] = ()
    tables_written: tuple[ParsedTable, ...] = ()
    dependencies: tuple[str, ...] = ()
    cte_occurrences: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    normalized_sql: str | None = None
    dialect_used: str = "tsql"
    issues: tuple[ParseIssue, ...] = ()
    statement_count: int = 0
    parsed_statement_count: int = 0
    fallback_statement_count: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        occurrences = {
            key: tuple(sorted(set(values))) for key, values in self.cte_occurrences.items()
        }
        object.__setattr__(self, "entities", tuple(self.entities))
        object.__setattr__(self, "ctes", tuple(self.ctes))
        object.__setattr__(self, "joins", tuple(self.joins))
        object.__setattr__(self, "tables_read", tuple(self.tables_read))
        object.__setattr__(self, "tables_written", tuple(self.tables_written))
        object.__setattr__(self, "dependencies", tuple(sorted(set(self.dependencies))))
        object.__setattr__(self, "cte_occurrences", _freeze_mapping(occurrences))
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


class SQLParser:
    """Parse SQL into immutable structural models."""

    def parse(self, sql: str, *, dialect: str = "tsql") -> ParsedSQL:
        if not sql.strip():
            return ParsedSQL(dialect_used=dialect)
        # SQLGlot does not model complete SQL Server procedure bodies reliably.
        # Extracting their structure is safer than accepting partial AST output
        # (or allowing the parser to print raw SQL in warnings).
        if self._is_tsql_procedure_definition(sql):
            entity = self._fallback_entity(sql, 0, confidence_score=0.7)
            assert entity is not None
            return self._parsed_from_fallback(entity, dialect)
        issues: list[ParseIssue] = []
        entities: list[ParsedEntity] = []
        all_ctes: list[ParsedCTE] = []
        all_joins: list[ParsedJoin] = []
        reads: list[ParsedTable] = []
        writes: list[ParsedTable] = []
        dependencies: list[str] = []
        occurrences: dict[str, list[str]] = {}
        statements = self._split_fallback_statements(sql)
        try:
            with self._quiet_sqlglot_warnings():
                expressions = list(sqlglot.parse(sql, read=dialect))
        except Exception as error:
            expressions = [None] * len(statements)
            issues.append(
                ParseIssue(
                    "PARSE-001",
                    "AST parsing failed; structural fallback was used.",
                    parse_mode="ast",
                    severity="warning",
                    metadata={"exception_type": type(error).__name__},
                )
            )
        parsed_count = 0
        fallback_count = 0
        for index, statement in enumerate(statements):
            expression = expressions[index] if index < len(expressions) else None
            if expression is None:
                entity = self._fallback_entity(statement, index)
                fallback_count += 1
                if entity is not None:
                    entities.append(entity)
                    self._append_entity(
                        entity, all_ctes, all_joins, reads, writes, dependencies, occurrences
                    )
                    issues.append(
                        ParseIssue(
                            "PARSE-002",
                            "Regex fallback used for statement",
                            line=entity.line_start,
                            statement_index=index,
                            severity="warning",
                            parse_mode="regex_fallback",
                        )
                    )
                continue
            parsed_count += 1
            entity = self._entity_from_expression(expression, statement, index, dialect)
            entities.append(entity)
            self._append_entity(
                entity, all_ctes, all_joins, reads, writes, dependencies, occurrences
            )
        normalized = "\n".join(e.normalized_sql for e in entities if e.normalized_sql)
        return ParsedSQL(
            entities=tuple(entities),
            ctes=tuple(all_ctes),
            joins=tuple(all_joins),
            tables_read=tuple(reads),
            tables_written=tuple(writes),
            dependencies=tuple(dependencies),
            cte_occurrences=occurrences,
            normalized_sql=normalized or None,
            dialect_used=dialect,
            issues=tuple(issues),
            statement_count=len(statements),
            parsed_statement_count=parsed_count,
            fallback_statement_count=fallback_count,
        )

    def _entity_from_expression(
        self, node: exp.Expression, source: str, index: int, dialect: str
    ) -> ParsedEntity:
        entity_type, statement_type, name_node = self._classify(node)
        name, schema, database, alias = self._qualified_parts(name_node)
        qualified = self._qualified_name(name, schema, database)
        tables = tuple(self._tables(node, "read", dialect))
        written = tuple(self._write_tables(node, dialect))
        ctes = tuple(self._ctes(node, dialect))
        joins = tuple(self._joins(node, dialect))
        called = tuple(self._called_procedures(node, source))
        deps = tuple(self._table_id(t) for t in (*tables, *written)) + called
        normalized = self._sql(node, dialect)
        return ParsedEntity(
            name=name,
            entity_type=entity_type,
            statement_type=statement_type,
            qualified_name=qualified,
            schema=schema,
            database=database,
            alias=alias,
            tables_read=tables,
            tables_written=written,
            ctes=ctes,
            joins=joins,
            dependencies=deps,
            called_procedures=called,
            normalized_sql=normalized,
            source="ast",
            confidence_score=1.0,
            line_start=self._line_start(source),
            line_end=self._line_end(source),
            statement_index=index,
        )

    def _classify(self, node: exp.Expression) -> tuple[str, str, exp.Expression | None]:
        kind = node.key.upper()
        if isinstance(node, (exp.Create, exp.Alter)):
            this = node.args.get("this")
            target_kind = str(node.args.get("kind") or "").upper()
            if target_kind in {"PROCEDURE", "PROC"}:
                return "procedure", f"{kind}_PROCEDURE", this
            if target_kind == "VIEW":
                return "view", f"{kind}_VIEW", this
        return "sql_script", kind, None

    def _tables(self, node: exp.Expression, operation: str, dialect: str) -> list[ParsedTable]:
        return [self._table(table, operation) for table in node.find_all(exp.Table)]

    def _write_tables(self, node: exp.Expression, dialect: str) -> list[ParsedTable]:
        result: list[ParsedTable] = []
        for cls, operation in (
            (exp.Insert, "insert"),
            (exp.Update, "update"),
            (exp.Delete, "delete"),
            (exp.Merge, "merge"),
        ):
            for parent in node.find_all(cls):
                target = parent.args.get("this")
                if isinstance(target, exp.Table):
                    result.append(self._table(target, operation))
        return result

    def _table(self, node: exp.Table, operation: str) -> ParsedTable:
        return ParsedTable(
            name=node.name,
            schema=node.db,
            database=node.catalog,
            alias=node.alias or None,
            operation=operation,
        )

    def _ctes(self, node: exp.Expression, dialect: str) -> list[ParsedCTE]:
        return [
            ParsedCTE(
                name=cte.alias_or_name,
                tables=tuple(self._tables(cte.this, "read", dialect)),
                references=tuple(
                    t.name for t in cte.this.find_all(exp.Table) if t.name != cte.alias_or_name
                ),
                normalized_sql=self._sql(cte.this, dialect),
            )
            for cte in node.find_all(exp.CTE)
        ]

    def _joins(self, node: exp.Expression, dialect: str) -> list[ParsedJoin]:
        result: list[ParsedJoin] = []
        for join in node.find_all(exp.Join):
            kind = str(join.args.get("side") or join.args.get("kind") or "INNER").upper()
            if join.args.get("method"):
                kind = str(join.args["method"]).upper()
            right = join.this.sql(dialect=dialect) if join.this else None
            result.append(
                ParsedJoin(kind, right=right, condition=self._sql(join.args.get("on"), dialect))
            )
        return result

    def _called_procedures(self, node: exp.Expression, source: str) -> list[str]:
        return list(dict.fromkeys(re.findall(r"(?i)\bEXEC(?:UTE)?\s+([\w\[\].]+)", source)))

    def _fallback_entity(
        self, source: str, index: int, *, confidence_score: float = 0.4
    ) -> ParsedEntity | None:
        match = re.search(
            r"(?is)\b(?:CREATE\s+(?:OR\s+ALTER\s+)?|ALTER\s+)(PROCEDURE|PROC|VIEW)\s+([\[\]\w.]+)",
            source,
        )
        if match:
            kind = "procedure" if match.group(1).upper() in {"PROC", "PROCEDURE"} else "view"
            statement_type = f"CREATE_{kind.upper()}"
            name, schema, database = self._split_name(match.group(2))
        else:
            kind, statement_type, name, schema, database = "sql_script", "UNKNOWN", None, None, None
        tables = tuple(self._fallback_tables(source))
        called = tuple(dict.fromkeys(re.findall(r"(?i)\bEXEC(?:UTE)?\s+([\w\[\].]+)", source)))
        qualified = self._qualified_name(name, schema, database)
        dependencies = tuple(self._table_id(table) for table in tables) + called
        return ParsedEntity(
            name=name,
            entity_type=kind,
            statement_type=statement_type,
            qualified_name=qualified,
            schema=schema,
            database=database,
            tables_read=tuple(table for table in tables if table.operation == "read"),
            tables_written=tuple(table for table in tables if table.operation != "read"),
            dependencies=dependencies,
            called_procedures=called,
            normalized_sql=source.strip(),
            source="regex_fallback",
            confidence_score=confidence_score,
            line_start=self._line_start(source),
            line_end=self._line_end(source),
            statement_index=index,
        )

    def _parsed_from_fallback(self, entity: ParsedEntity, dialect: str) -> ParsedSQL:
        """Build a complete parsed model for a structurally extracted procedure."""
        return ParsedSQL(
            entities=(entity,),
            ctes=entity.ctes,
            joins=entity.joins,
            tables_read=entity.tables_read,
            tables_written=entity.tables_written,
            dependencies=entity.dependencies,
            normalized_sql=entity.normalized_sql,
            dialect_used=dialect,
            statement_count=1,
            fallback_statement_count=1,
        )

    @staticmethod
    def _is_tsql_procedure_definition(sql: str) -> bool:
        return bool(
            re.search(
                r"(?is)^\s*(?:CREATE\s+(?:OR\s+ALTER\s+)?|ALTER\s+)(?:PROCEDURE|PROC)\b",
                sql,
            )
        )

    @staticmethod
    @contextmanager
    def _quiet_sqlglot_warnings():
        """Prevent third-party parser warnings from disclosing SQL in logs."""
        logger = logging.getLogger("sqlglot")
        previous_level = logger.level
        logger.setLevel(logging.ERROR)
        try:
            yield
        finally:
            logger.setLevel(previous_level)

    def _fallback_tables(self, source: str) -> list[ParsedTable]:
        result: list[ParsedTable] = []
        pattern = (
            r"(?P<operation>FROM|JOIN|INSERT\s+INTO|UPDATE|DELETE\s+FROM|"
            r"MERGE(?:\s+INTO)?)\s+(?P<table>[\w\[\].]+)"
)
        for match in re.finditer(pattern, source):
            name, schema, database = self._split_name(match.group("table"))
            keyword = match.group("operation").upper()
            operation = {
                "FROM": "read",
                "JOIN": "read",
                "INSERT INTO": "insert",
                "UPDATE": "update",
                "DELETE FROM": "delete",
            }.get(keyword, "merge")

            result.append(
                ParsedTable(
                    name,
                    schema,
                    database,
                    operation=operation,
                    source="regex_fallback",
                    confidence_score=0.4,
                )
            )

        return result
    
    def _append_entity(
        self,
        entity: ParsedEntity,
        ctes: list[ParsedCTE],
        joins: list[ParsedJoin],
        reads: list[ParsedTable],
        writes: list[ParsedTable],
        dependencies: list[str],
        occurrences: dict[str, list[str]],
    ) -> None:
        ctes.extend(entity.ctes)
        joins.extend(entity.joins)
        reads.extend(entity.tables_read)
        writes.extend(entity.tables_written)
        dependencies.extend(entity.dependencies)
        owner = _make_entity_id(
            entity.entity_type, entity.qualified_name, entity.name, entity.statement_index
        )
        for cte in entity.ctes:
            occurrences.setdefault(cte.name, []).append(_make_cte_id(owner, cte.name))

    @staticmethod
    def _sql(node: exp.Expression | None, dialect: str) -> str | None:
        return node.sql(dialect=dialect) if node is not None else None

    @staticmethod
    # def _qualified_parts(node: exp.Expression | None):
    #     if not node:
    #         return None, None, None, None
    #     name = getattr(node, "name", None) or getattr(node, "this", None)
    #     return (
    #         name,
    #         getattr(node, "db", None),
    #         getattr(node, "catalog", None),
    #         getattr(node, "alias_or_none", None),
    #     )

    @staticmethod
    def _qualified_parts(
        node: exp.Expression | None,
    ) -> tuple[
        str | None,
        str | None,
        str | None,
        str | None,
    ]:
        if node is None:
            return None, None, None, None

        if isinstance(node, exp.Dot):
            left = node.args.get("this")
            right = node.args.get("expression")

            schema = (
                left.name
                if isinstance(left, exp.Identifier)
                else str(left)
            )
            name = (
                right.name
                if isinstance(right, exp.Identifier)
                else str(right)
            )

            return name, schema, None, None

        raw_name = getattr(node, "name", None) or getattr(
            node,
            "this",
            None,
        )

        name = str(raw_name) if raw_name is not None else None
        schema = getattr(node, "db", None)
        database = getattr(node, "catalog", None)
        alias = getattr(node, "alias_or_none", None)

        if name and "." in name:
            cleaned = (
                name.replace('"', "")
                .replace("[", "")
                .replace("]", "")
            )
            parts = [
                part.strip()
                for part in cleaned.split(".")
                if part.strip()
            ]

            if parts:
                name = parts[-1]

            if len(parts) >= 2 and not schema:
                schema = parts[-2]

            if len(parts) >= 3 and not database:
                database = parts[-3]

        return (
            str(name) if name else None,
            str(schema) if schema else None,
            str(database) if database else None,
            str(alias) if alias else None,
        )

    @staticmethod
    def _qualified_name(name, schema, database):
        return ".".join(x for x in (database, schema, name) if x) or None

    @staticmethod
    def _split_name(value):
        parts = [part.strip("[]") for part in value.split(".")]
        return (
            parts[-1],
            parts[-2] if len(parts) > 1 else None,
            parts[-3] if len(parts) > 2 else None,
        )

    @staticmethod
    def _table_id(table: ParsedTable) -> str:
        return _make_table_id(table.database, table.schema, table.name)

    @staticmethod
    def _line_start(source):
        return 1 if source else None

    @staticmethod
    def _line_end(source):
        return source.count("\n") + 1 if source else None

    @staticmethod
    def _line_number(full, fragment):
        position = full.find(fragment)
        return full.count("\n", 0, position) + 1 if position >= 0 else None

    @staticmethod
    def _split_fallback_statements(sql):
        return tuple(part.strip() for part in sql.split(";") if part.strip())


__all__ = [
    "ParseIssue",
    "ParsedCTE",
    "ParsedEntity",
    "ParsedJoin",
    "ParsedSQL",
    "ParsedTable",
    "SQLParser",
]
