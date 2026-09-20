"""Build an immutable dependency graph from parsed SQL structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from src.monitor.scanners.sql_parser import ParsedEntity, ParsedSQL, ParsedTable


def _freeze(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(sorted(value.items())))


@dataclass(frozen=True)
class DependencyNode:
    node_id: str
    node_type: str
    name: str
    qualified_name: str | None = None
    schema: str | None = None
    database: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True)
class DependencyEdge:
    source_id: str
    target_id: str
    edge_type: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    @property
    def edge_id(self) -> str:
        return f"{self.source_id}->{self.target_id}:{self.edge_type}"


@dataclass(frozen=True)
class DependencyGraph:
    nodes: tuple[DependencyNode, ...] = ()
    edges: tuple[DependencyEdge, ...] = ()
    fan_out_by_node: Mapping[str, int] = field(default_factory=dict)
    called_procedures: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    cte_reuse: Mapping[str, int] = field(default_factory=dict)
    shared_tables: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    max_dependency_chain: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "edges", tuple(self.edges))
        object.__setattr__(self, "fan_out_by_node", _freeze(self.fan_out_by_node))
        object.__setattr__(self, "called_procedures", _freeze({k: tuple(sorted(v)) for k, v in self.called_procedures.items()}))
        object.__setattr__(self, "cte_reuse", _freeze(self.cte_reuse))
        object.__setattr__(self, "shared_tables", _freeze({k: tuple(sorted(v)) for k, v in self.shared_tables.items()}))
        object.__setattr__(self, "metadata", _freeze(self.metadata))


class DependencyGraphBuilder:
    """Convert ParsedSQL into a deterministic graph."""

    def build(self, parsed: ParsedSQL) -> DependencyGraph:
        nodes: dict[str, DependencyNode] = {}
        edges: dict[tuple[str, str, str], DependencyEdge] = {}
        entity_ids: dict[int, str] = {}
        table_ids: dict[str, str] = {}
        procedure_ids: dict[str, str] = {}
        consumers: dict[str, set[str]] = {}

        def node(node_value: DependencyNode) -> str:
            nodes.setdefault(node_value.node_id, node_value)
            return node_value.node_id

        def edge(source: str, target: str, kind: str, metadata: Mapping[str, object] | None = None) -> None:
            edges.setdefault((source, target, kind), DependencyEdge(source, target, kind, metadata or {}))

        def table(value: ParsedTable) -> str:
            key = self._table_key(value)
            identifier = table_ids.setdefault(key, f"table:{key}")
            node(DependencyNode(identifier, "table", value.name, key, value.schema, value.database))
            return identifier

        for index, entity in enumerate(parsed.entities):
            identifier = self._entity_id(entity, index)
            entity_ids[index] = identifier
            node(DependencyNode(identifier, entity.entity_type, entity.name or identifier, entity.qualified_name, entity.schema, entity.database))
            if entity.entity_type.lower() == "procedure" and entity.qualified_name:
                procedure_ids.setdefault(entity.qualified_name, identifier)

        for index, entity in enumerate(parsed.entities):
            owner = entity_ids[index]
            for cte in entity.ctes:
                cte_id = f"cte:{owner}:{cte.name}"
                node(DependencyNode(cte_id, "cte", cte.name, cte.name, metadata={"recursive": cte.recursive}))
                edge(owner, cte_id, "DEPENDS_ON")
                for value in cte.tables:
                    target = table(value)
                    edge(cte_id, target, "READS")
                    consumers.setdefault(target, set()).add(owner)
                for reference in cte.references:
                    target = f"cte:{owner}:{reference}"
                    if target in nodes:
                        edge(cte_id, target, "DEPENDS_ON")
            for value in entity.tables_read:
                target = table(value)
                edge(owner, target, "READS", {"operation": value.operation})
                consumers.setdefault(target, set()).add(owner)
            for value in entity.tables_written:
                target = table(value)
                edge(owner, target, "WRITES", {"operation": value.operation})
                consumers.setdefault(target, set()).add(owner)
            for called in entity.called_procedures:
                edge(owner, self._resolve_procedure(called, procedure_ids, nodes), "CALLS")
            for dependency in entity.dependencies:
                target = self._resolve_dependency(dependency, nodes, table_ids)
                if target:
                    edge(owner, target, "DEPENDS_ON")
            for join in entity.joins:
                target = self._resolve_name(join.right, nodes, table_ids)
                if target:
                    edge(owner, target, "JOINS", {"join_type": join.join_type, "condition": join.condition, "left": join.left, "right": join.right})

        destinations: dict[str, set[str]] = {}
        for item in edges.values():
            destinations.setdefault(item.source_id, set()).add(item.target_id)
        fan_out = {key: len(value) for key, value in sorted(destinations.items())}
        called = {
            entity_ids[index]: tuple(sorted({procedure_ids.get(name, f"procedure:{name}") for name in entity.called_procedures}))
            for index, entity in enumerate(parsed.entities) if entity.called_procedures
        }
        longest, cycles = self._chain_metrics(tuple(nodes), tuple(edges.values()))
        return DependencyGraph(
            nodes=tuple(nodes.values()), edges=tuple(edges.values()), fan_out_by_node=fan_out,
            called_procedures=called, shared_tables={k: tuple(sorted(v)) for k, v in consumers.items() if len(v) > 1},
            max_dependency_chain=longest, metadata={"cycles": cycles},
        )

    @staticmethod
    def _entity_id(entity: ParsedEntity, index: int) -> str:
        return f"{entity.entity_type}:{entity.qualified_name or entity.name or 'statement'}"

    @staticmethod
    def _table_key(table: ParsedTable) -> str:
        return ".".join(part for part in (table.database, table.schema, table.name) if part)

    @staticmethod
    def _resolve_procedure(name: str, procedures: Mapping[str, str], nodes: dict[str, DependencyNode]) -> str:
        identifier = procedures.get(name, f"procedure:{name}")
        nodes.setdefault(identifier, DependencyNode(identifier, "procedure", name, qualified_name=name, metadata={"external": identifier not in procedures}))
        return identifier

    @staticmethod
    def _resolve_dependency(value: str, nodes: Mapping[str, DependencyNode], tables: Mapping[str, str]) -> str | None:
        for identifier, item in nodes.items():
            if item.qualified_name == value or item.name == value:
                return identifier
        return tables.get(value) or (f"table:{value}" if value else None)

    @staticmethod
    def _resolve_name(value: str | None, nodes: Mapping[str, DependencyNode], tables: Mapping[str, str]) -> str | None:
        if not value:
            return None
        clean = value.replace("[", "").replace("]", "")
        return next((identifier for identifier, item in nodes.items() if item.name == clean or item.qualified_name == clean), tables.get(clean))

    @staticmethod
    def _chain_metrics(nodes: tuple[DependencyNode, ...], edges: tuple[DependencyEdge, ...]) -> tuple[int, tuple[tuple[str, ...], ...]]:
        adjacency: dict[str, set[str]] = {}
        for item in edges:
            adjacency.setdefault(item.source_id, set()).add(item.target_id)
        cycles: set[tuple[str, ...]] = set()

        def visit(identifier: str, path: tuple[str, ...]) -> int:
            if identifier in path:
                return len(path)
            current = (*path, identifier)
            children = tuple(sorted(adjacency.get(identifier, set())))
            for child in children:
                if child in current:
                    cycles.add(current[current.index(child):] + (child,))
            return max((visit(child, current) for child in children), default=len(current))

        return max((visit(item.node_id, ()) for item in nodes), default=0), tuple(sorted(cycles))


__all__ = ["DependencyEdge", "DependencyGraph", "DependencyGraphBuilder", "DependencyNode"]
