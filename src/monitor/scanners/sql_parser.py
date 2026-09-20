"""SQL parsing foundation for Data Guardian.

SQLGlot is the primary parser. The regex path is deliberately conservative and is
used only to preserve partial discovery when SQLGlot cannot parse a statement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Mapping

import sqlglot
from sqlglot import exp


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


class SQLParser:
    """Parse SQL into immutable structural models."""

    def parse(self, sql: str, *, dialect: str = "tsql") -> ParsedSQL:
        if not sql.strip():
            return ParsedSQL(dialect_used=dialect)

        issues: list[ParseIssue] = []
        entities: list[ParsedEntity] = []
        all_ctes: list[ParsedCTE] = []
        all_joins: list[ParsedJoin] = []
        reads: list[ParsedTable] = []
        writes: list[ParsedTable] = []
        dependencies: list[str] = []
        occurrences: dict[str, list[str]] = {}
        statements = self._split_fallback_statements(sql)
        expressions: list[exp.Expression | None]
        try:
            expressions = list(sqlglot.parse(sql, read=dialect))
            statements = self._split_fallback_statements(sql)
        except Exception as error:
            expressions = [None] * len(statements)
            issues.append(ParseIssue("PARSE-001", str(error), parse_mode="ast"))

        parsed_count = 0
        fallback_count = 0
        for index, statement in enumerate(statements):
            expression = expressions[index] if index < len(expressions) else None
            if expression is None:
                entity = self._fallback_entity(statement, index)
                fallback_count += 1
                issues.append(ParseIssue(
                    "PARSE-001", "SQLGlot could not parse statement",
                    line=self._line_number(sql, statement), statement_index=index,
                    parse_mode="ast",
                ))
                if entity is not None:
                    entities.append(entity)
                    self._append_entity(entity, all_ctes, all_joins, reads, writes, dependencies, occurrences)
                    issues.append(ParseIssue(
                        "PARSE-002", "Regex fallback used for statement",
                        line=entity.line_start, statement_index=index,
                        severity="warning", parse_mode="regex_fallback",
                    ))
                continue
            parsed_count += 1
            entity = self._entity_from_expression(expression, statement, index, dialect)
            entities.append(entity)
            self._append_entity(entity, all_ctes, all_joins, reads, writes, dependencies, occurrences)

        normalized = "\n".join(e.normalized_sql for e in entities if e.normalized_sql)
        return ParsedSQL(
            entities=tuple(entities), ctes=tuple(all_ctes), joins=tuple(all_joins),
            tables_read=tuple(reads), tables_written=tuple(writes),
            dependencies=tuple(dict.fromkeys(dependencies)),
            cte_occurrences={k: tuple(dict.fromkeys(v)) for k, v in occurrences.items()},
            normalized_sql=normalized or None, dialect_used=dialect,
            issues=tuple(issues), statement_count=len(statements),
            parsed_statement_count=parsed_count, fallback_statement_count=fallback_count,
        )

    def _entity_from_expression(self, node: exp.Expression, source: str, index: int, dialect: str) -> ParsedEntity:
        entity_type, statement_type, name_node = self._classify(node)
        name, schema, database, alias = self._qualified_parts(name_node)
        qualified = self._qualified_name(name, schema, database)
        tables = tuple(self._tables(node, "read", dialect))
        written = tuple(self._write_tables(node, dialect))
        ctes = tuple(self._ctes(node, dialect))
        joins = tuple(self._joins(node, dialect))
        called = tuple(self._called_procedures(node, source))
        deps = tuple(dict.fromkeys([self._table_id(t) for t in (*tables, *written)] + list(called)))
        normalized = self._sql(node, dialect)
        seed = "|".join((entity_type, statement_type, qualified or "", normalized or "", *deps))
        return ParsedEntity(
            name=name, entity_type=entity_type, statement_type=statement_type,
            qualified_name=qualified, schema=schema, database=database, alias=alias,
            tables_read=tables, tables_written=written, ctes=ctes, joins=joins,
            dependencies=deps, called_procedures=called, normalized_sql=normalized,
            entity_fingerprint_seed=seed, source="ast", confidence_score=1.0,
            line_start=self._line_start(source), line_end=self._line_end(source),
            statement_index=index,
        )

    def _classify(self, node: exp.Expression) -> tuple[str, str, exp.Expression | None]:
        kind = node.key.upper()
        if isinstance(node, (exp.Create, exp.Alter)):
            this = node.args.get("this")
            target = getattr(this, "this", this)
            target_kind = getattr(target, "key", "").upper()
            if "PROCEDURE" in target_kind or "PROC" in target_kind:
                return "procedure", f"{kind}_PROCEDURE", target
            if "VIEW" in target_kind:
                return "view", f"{kind}_VIEW", target
        return "sql_script", kind, None

    def _tables(self, node: exp.Expression, operation: str, dialect: str) -> list[ParsedTable]:
        result: list[ParsedTable] = []
        for table in node.find_all(exp.Table):
            result.append(self._table(table, operation))
        return result

    def _write_tables(self, node: exp.Expression, dialect: str) -> list[ParsedTable]:
        result: list[ParsedTable] = []
        for cls, operation in ((exp.Insert, "insert"), (exp.Update, "update"), (exp.Delete, "delete"), (exp.Merge, "merge")):
            for parent in node.find_all(cls):
                target = parent.args.get("this")
                if isinstance(target, exp.Table):
                    result.append(self._table(target, operation))
        return result

    def _table(self, node: exp.Table, operation: str) -> ParsedTable:
        return ParsedTable(
            name=node.name, schema=node.db, database=node.catalog,
            alias=node.alias_or_none, operation=operation,
        )

    def _ctes(self, node: exp.Expression, dialect: str) -> list[ParsedCTE]:
        result: list[ParsedCTE] = []
        for cte in node.find_all(exp.CTE):
            name = cte.alias_or_name
            body = cte.this
            tables = tuple(self._tables(body, "read", dialect))
            refs = tuple(dict.fromkeys(t.name for t in body.find_all(exp.Table) if t.name != name))
            result.append(ParsedCTE(
                name=name, recursive=False, references=refs, tables=tables,
                normalized_sql=self._sql(body, dialect),
            ))
        return result

    def _joins(self, node: exp.Expression, dialect: str) -> list[ParsedJoin]:
        result: list[ParsedJoin] = []
        for join in node.find_all(exp.Join):
            kind = str(join.args.get("side") or join.args.get("kind") or "INNER").upper()
            if join.args.get("method"):
                kind = str(join.args["method"]).upper()
            right = join.this.sql(dialect=dialect) if join.this else None
            on = join.args.get("on")
            result.append(ParsedJoin(kind, right=right, condition=self._sql(on, dialect)))
        return result

    def _called_procedures(self, node: exp.Expression, source: str) -> list[str]:
        return list(dict.fromkeys(re.findall(r"(?i)\bEXEC(?:UTE)?\s+([\w\[\].]+)", source)))

    def _fallback_entity(self, source: str, index: int) -> ParsedEntity | None:
        match = re.search(r"(?is)\b(?:CREATE\s+(?:OR\s+ALTER\s+)?|ALTER\s+)(PROCEDURE|PROC|VIEW)\s+([\[\]\w.]+)", source)
        if match:
            kind = "procedure" if match.group(1).upper() in {"PROC", "PROCEDURE"} else "view"
            statement_type = f"CREATE_{kind.upper()}"
            name, schema, database = self._split_name(match.group(2))
        else:
            kind, statement_type, name, schema, database = "sql_script", "UNKNOWN", None, None, None
        tables = tuple(self._fallback_tables(source))
        called = tuple(dict.fromkeys(re.findall(r"(?i)\bEXEC(?:UTE)?\s+([\w\[\].]+)", source)))
        qualified = self._qualified_name(name, schema, database)
        seed = "|".join((kind, statement_type, qualified or "", source.strip(), *called))
        return ParsedEntity(
            name=name, entity_type=kind, statement_type=statement_type,
            qualified_name=qualified, schema=schema, database=database,
            tables_read=tables, dependencies=tuple(t.name for t in tables),
            called_procedures=called, normalized_sql=source.strip(),
            entity_fingerprint_seed=seed, source="regex_fallback", confidence_score=0.4,
            line_start=self._line_start(source), line_end=self._line_end(source), statement_index=index,
        )

    def _fallback_tables(self, source: str) -> list[ParsedTable]:
        result = []
        for match in re.finditer(r"(?i)\b(?:FROM|JOIN|INTO|UPDATE)\s+([\w\[\].]+)", source):
            name, schema, database = self._split_name(match.group(1))
            operation = "read" if match.group(0).upper().startswith(("FROM", "JOIN")) else "write"
            result.append(ParsedTable(name, schema, database, operation=operation, source="regex_fallback", confidence_score=0.4))
        return result

    def _append_entity(self, entity, ctes, joins, reads, writes, dependencies, occurrences):
        ctes.extend(entity.ctes); joins.extend(entity.joins); reads.extend(entity.tables_read); writes.extend(entity.tables_written)
        dependencies.extend(entity.dependencies)
        owner = entity.qualified_name or entity.name or f"statement:{entity.statement_index}"
        for cte in entity.ctes:
            occurrences.setdefault(cte.name, []).append(owner)

    @staticmethod
    def _sql(node, dialect):
        return node.sql(dialect=dialect) if node is not None else None

    @staticmethod
    def _qualified_parts(node):
        if not node:
            return None, None, None, None
        name = getattr(node, "name", None) or getattr(node, "this", None)
        return name, getattr(node, "db", None), getattr(node, "catalog", None), getattr(node, "alias_or_none", None)

    @staticmethod
    def _qualified_name(name, schema, database):
        return ".".join(x for x in (database, schema, name) if x) or None

    @staticmethod
    def _split_name(value):
        parts = [p.strip("[]") for p in value.split(".")]
        return (parts[-1], parts[-2] if len(parts) > 1 else None, parts[-3] if len(parts) > 2 else None)

    @staticmethod
    def _table_id(table):
        return ".".join(x for x in (table.database, table.schema, table.name) if x)

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
