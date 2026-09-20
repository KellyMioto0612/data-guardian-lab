"""Build an immutable dependency graph from parsed SQL structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from src.monitor.scanners.sql_parser import ParsedCTE, ParsedEntity, ParsedSQL, ParsedTable


@dataclass(frozen=True)
class DependencyNode:
    node_id: str
    node_type: str
    name: str
    qualified_name: str | None = None
    schema: str | None = None
    database: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DependencyEdge:
    source_id: str
    target_id: str
    edge_type: str
    metadata: Mapping[str, object] = field(default_factory=dict)

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


class DependencyGraphBuilder:
    """Convert ParsedSQL into a deterministic in-memory dependency graph."""

    def build(self, parsed: ParsedSQL) -> DependencyGraph:
        nodes: dict[str, DependencyNode] = {}
        edges: dict[tuple[str, str, str], DependencyEdge] = {}
        entity_ids: dict[int, str] = {}
        cte_ids: dict[tuple[int, str], str] = {}
        table_ids: dict[str, str] = {}
        procedure_ids: dict[str, str] = {}
        cte_owners: dict[str, set[str]] = {}
        table_consumers: dict[str, set[str]] = {}

        def add_node(node: DependencyNode) -> str:
            nodes.setdefault(node.node_id, node)
            return node.node_id

        def add_edge(source: str, target: str, edge_type: str, metadata: Mapping[str, object] | None = None) -> None:
            if source == target and edge_type == "DEPENDS_ON":
                # Retain self-dependencies for cycle reporting.
                pass
            key = (source, target, edge_type)
            edges.setdefault(key, DependencyEdge(source, target, edge_type, dict(metadata or {})))

        def add_table(table: ParsedTable) -> str:
            qualified = self._table_key(table)
            node_id = table_ids.get(qualified)
            if node_id is None:
                node_id = f"table:{qualified}"
                table_ids[qualified] = node_id
                add_node(DependencyNode(
                    node_id=node_id,
                    node_type="table",
                    name=table.name,
                    qualified_name=qualified,
                    schema=table.schema,
                    database=table.database,
                    metadata={"source": table.source, "confidence_score": table.confidence_score},
                ))
            return node_id

        for index, entity in enumerate(parsed.entities):
            entity_id = self._entity_id(entity, index)
            entity_ids[index] = entity_id
            add_node(DependencyNode(
                node_id=entity_id,
                node_type=entity.entity_type,
                name=entity.name or entity_id,
                qualified_name=entity.qualified_name,
                schema=entity.schema,
                database=entity.database,
                metadata={
                    "statement_type": entity.statement_type,
                    "source": entity.source,
                    "confidence_score": entity.confidence_score,
                },
            ))
            if entity.entity_type == "procedure" and entity.qualified_name:
                procedure_ids.setdefault(entity.qualified_name, entity_id)

        for index, entity in enumerate(parsed.entities):
            owner_id = entity_ids[index]
            for cte in entity.ctes:
                cte_id = f"cte:{owner_id}:{cte.name}"
                cte_ids[(index, cte.name)] = cte_id
                add_node(DependencyNode(
                    node_id=cte_id,
                    node_type="cte",
                    name=cte.name,
                    qualified_name=cte.name,
                    metadata={
                        "recursive": cte.recursive,
                        "source": cte.source,
                        "confidence_score": cte.confidence_score,
                    },
                ))
                cte_owners.setdefault(cte_id, set()).add(owner_id)
                add_edge(owner_id, cte_id, "DEPENDS_ON")

                for table in cte.tables:
                    table_id = add_table(table)
                    add_edge(cte_id, table_id, "READS")
                    table_consumers.setdefault(table_id, set()).add(owner_id)
                for reference in cte.references:
                    target = self._resolve_cte(reference, entity, index, cte_ids)
                    if target:
                        add_edge(cte_id, target, "DEPENDS_ON")

        for index, entity in enumerate(parsed.entities):
            owner_id = entity_ids[index]
            for table in entity.tables_read:
                table_id = add_table(table)
                add_edge(owner_id, table_id, "READS", {"operation": table.operation})
                table_consumers.setdefault(table_id, set()).add(owner_id)
            for table in entity.tables_written:
                table_id = add_table(table)
                add_edge(owner_id, table_id, "WRITES", {"operation": table.operation})
                table_consumers.setdefault(table_id, set()).add(owner_id)
            for procedure in entity.called_procedures:
                target = self._resolve_procedure(procedure, procedure_ids, nodes)
                add_edge(owner_id, target, "CALLS")
            for dependency in entity.dependencies:
                target = self._resolve_dependency(dependency, owner_id, nodes, table_ids)
                if target:
                    add_edge(owner_id, target, "DEPENDS_ON")
            for join in entity.joins:
                target = self._resolve_join_target(join.right, table_ids, nodes)
                if target:
                    add_edge(owner_id, target, "JOINS", {
                        "join_type": join.join_type,
                        "condition": join.condition,
                        "left": join.left,
                        "right": join.right,
                    })

        fan_out: dict[str, int] = {}
        for edge in edges.values():
            fan_out.setdefault(edge.source_id, set()).add(edge.target_id)  # type: ignore[union-attr]
        fan_out = {node_id: len(targets) for node_id, targets in fan_out.items()}  # type: ignore[arg-type]

        called = self._called_metrics(parsed, entity_ids, procedure_ids)
        cte_reuse = {key: len(owners) for key, owners in cte_owners.items()}
        shared = {
            table_id: tuple(sorted(consumers))
            for table_id, consumers in table_consumers.items()
            if len(consumers) > 1
        }
        max_chain, cycles = self._chain_metrics(tuple(nodes), tuple(edges.values()))
        metadata = {"cycles": tuple(cycles)}
        return DependencyGraph(
            nodes=tuple(nodes.values()),
            edges=tuple(edges.values()),
            fan_out_by_node=fan_out,
            called_procedures=called,
            cte_reuse=cte_reuse,
            shared_tables=shared,
            max_dependency_chain=max_chain,
            metadata=MappingProxyType(metadata),
        )

    @staticmethod
    def _entity_id(entity: ParsedEntity, index: int) -> str:
        if entity.qualified_name:
            return f"{entity.entity_type}:{entity.qualified_name}"
        return f"{entity.entity_type}:{entity.name or 'statement'}:{index}"

    @staticmethod
    def _table_key(table: ParsedTable) -> str:
        return ".".join(part for part in (table.database, table.schema, table.name) if part)

    @staticmethod
    def _resolve_cte(name: str, entity: ParsedEntity, index: int, cte_ids: Mapping[tuple[int, str], str]) -> str | None:
        return cte_ids.get((index, name))

    @staticmethod
    def _resolve_procedure(name: str, procedures: Mapping[str, str], nodes: dict[str, DependencyNode]) -> str:
        if name in procedures:
            return procedures[name]
        node_id = f"procedure:{name}"
        nodes.setdefault(node_id, DependencyNode(node_id, "procedure", name, qualified_name=name, metadata={"external": True}))
        return node_id

    @staticmethod
    def _resolve_dependency(dependency: str, owner_id: str, nodes: Mapping[str, DependencyNode], tables: Mapping[str, str]) -> str | None:
        for node_id, node in nodes.items():
            if node.qualified_name == dependency or node.name == dependency:
                return node_id
        return tables.get(dependency) or (f"table:{dependency}" if dependency else None)

    @staticmethod
    def _resolve_join_target(value: str | None, tables: Mapping[str, str], nodes: Mapping[str, DependencyNode]) -> str | None:
        if not value:
            return None
        clean = value.replace("[", "").replace("]", "")
        for node_id, node in nodes.items():
            if node.name == clean or node.qualified_name == clean:
                return node_id
        return tables.get(clean)

    @staticmethod
    def _called_metrics(parsed: ParsedSQL, entity_ids: Mapping[int, str], procedures: Mapping[str, str]) -> Mapping[str, tuple[str, ...]]:
        result: dict[str, tuple[str, ...]] = {}
        for index, entity in enumerate(parsed.entities):
            if entity.called_procedures:
                result[entity_ids[index]] = tuple(
                    procedures.get(name, f"procedure:{name}") for name in dict.fromkeys(entity.called_procedures)
                )
        return result

    @staticmethod
    def _chain_metrics(nodes: tuple[DependencyNode, ...], edges: tuple[DependencyEdge, ...]) -> tuple[int, tuple[tuple[str, ...], ...]]:
        adjacency: dict[str, tuple[str, ...]] = {}
        for edge in edges:
            adjacency.setdefault(edge.source_id, ())
            adjacency[edge.source_id] = (*adjacency[edge.source_id], edge.target_id)
        cycles: list[tuple[str, ...]] = []
        longest = 0

        def visit(node_id: str, path: tuple[str, ...]) -> int:
            nonlocal cycles
            if node_id in path:
                cycle = path[path.index(node_id):] + (node_id,)
                if cycle not in cycles:
                    cycles.append(cycle)
                return len(path)
            next_path = (*path, node_id)
            children = adjacency.get(node_id, ())
            if not children:
                return len(next_path)
            return max(visit(child, next_path) for child in children)

        for node in nodes:
            longest = max(longest, visit(node.node_id, ()))
        return longest, tuple(cycles)


__all__ = [
    "DependencyEdge",
    "DependencyGraph",
    "DependencyGraphBuilder",
    "DependencyNode",
]
