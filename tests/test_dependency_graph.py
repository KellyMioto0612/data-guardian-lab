"""Coverage for the dependency graph foundation."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, is_dataclass
from types import MappingProxyType

import pytest

from src.analyzers.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyGraphBuilder,
    DependencyNode,
)
from src.monitor.scanners.sql_parser import (
    ParsedCTE,
    ParsedEntity,
    ParsedJoin,
    ParsedSQL,
    ParsedTable,
)


def table(name: str, schema: str | None = "sales") -> ParsedTable:
    return ParsedTable(name=name, schema=schema)


def entity(
    name: str,
    entity_type: str,
    *,
    qualified_name: str | None = None,
    reads: tuple[ParsedTable, ...] = (),
    writes: tuple[ParsedTable, ...] = (),
    ctes: tuple[ParsedCTE, ...] = (),
    joins: tuple[ParsedJoin, ...] = (),
    dependencies: tuple[str, ...] = (),
    called: tuple[str, ...] = (),
) -> ParsedEntity:
    return ParsedEntity(
        name=name,
        entity_type=entity_type,
        statement_type="SELECT",
        qualified_name=qualified_name,
        tables_read=reads,
        tables_written=writes,
        ctes=ctes,
        joins=joins,
        dependencies=dependencies,
        called_procedures=called,
    )


def build(*entities: ParsedEntity) -> DependencyGraph:
    return DependencyGraphBuilder().build(ParsedSQL(entities=entities))


def edge_types(graph: DependencyGraph) -> set[str]:
    return {edge.edge_type for edge in graph.edges}


def test_creates_all_required_node_types() -> None:
    cte = ParsedCTE(name="recent_orders", tables=(table("orders"),))
    graph = build(
        entity(
            "refresh",
            "procedure",
            qualified_name="dbo.refresh",
            ctes=(cte,),
            reads=(table("orders"),),
        ),
        entity("active", "view", qualified_name="sales.active", reads=(table("customers"),)),
        entity("script.sql", "sql_script", reads=(table("audit"),)),
    )

    assert {node.node_type for node in graph.nodes} == {
        "procedure",
        "view",
        "sql_script",
        "cte",
        "table",
    }


def test_creates_all_required_edge_types_and_join_metadata() -> None:
    join = ParsedJoin(
        join_type="LEFT",
        left="sales.orders",
        right="sales.customers",
        condition="orders.customer_id = customers.id",
    )
    graph = build(
        entity(
            "refresh",
            "procedure",
            qualified_name="dbo.refresh",
            reads=(table("orders"),),
            writes=(table("order_summary"),),
            ctes=(ParsedCTE(name="base", tables=(table("orders"),)),),
            joins=(join,),
            dependencies=("sales.orders",),
            called=("dbo.validate",),
        ),
    )

    assert {"READS", "WRITES", "CALLS", "DEPENDS_ON", "JOINS"} <= edge_types(graph)
    join_edge = next(edge for edge in graph.edges if edge.edge_type == "JOINS")
    assert join_edge.metadata == {
        "join_type": "LEFT",
        "condition": "orders.customer_id = customers.id",
        "left": "sales.orders",
        "right": "sales.customers",
    }


def test_deduplicates_nodes_and_edges() -> None:
    orders = table("orders")
    graph = build(
        entity("refresh", "procedure", qualified_name="dbo.refresh", reads=(orders, orders)),
        entity("refresh-copy", "procedure", qualified_name="dbo.refresh", reads=(orders,)),
    )

    assert len([node for node in graph.nodes if node.node_id == "procedure:dbo.refresh"]) == 1
    reads = [edge for edge in graph.edges if edge.edge_type == "READS"]
    assert len(reads) == 1


def test_calculates_fan_out_using_distinct_destinations() -> None:
    graph = build(
        entity(
            "refresh",
            "procedure",
            qualified_name="dbo.refresh",
            reads=(table("orders"), table("orders")),
            writes=(table("summary"),),
            called=("dbo.validate",),
        )
    )

    assert graph.fan_out_by_node["procedure:dbo.refresh"] == 3


def test_collects_called_procedures() -> None:
    graph = build(
        entity(
            "refresh",
            "procedure",
            qualified_name="dbo.refresh",
            called=("dbo.validate", "dbo.validate"),
        )
    )

    assert graph.called_procedures["procedure:dbo.refresh"] == ("procedure:dbo.validate",)


def test_calculates_cte_reuse_and_shared_tables() -> None:
    shared = table("orders")
    first_cte = ParsedCTE(name="recent", tables=(shared,))
    second_cte = ParsedCTE(name="recent", tables=(shared,))
    graph = build(
        entity("one", "view", qualified_name="sales.one", ctes=(first_cte,), reads=(shared,)),
        entity("two", "view", qualified_name="sales.two", ctes=(second_cte,), reads=(shared,)),
    )

    assert graph.cte_reuse["cte:view:sales.one:recent"] == 1
    assert graph.cte_reuse["cte:view:sales.two:recent"] == 1
    assert graph.shared_tables["table:sales.orders"] == ("view:sales.one", "view:sales.two")


def test_calculates_simple_and_long_dependency_chains() -> None:
    graph = build(
        entity("a", "procedure", qualified_name="dbo.a", called=("dbo.b",)),
        entity("b", "procedure", qualified_name="dbo.b", called=("dbo.c",)),
        entity("c", "procedure", qualified_name="dbo.c", reads=(table("orders"),)),
    )

    assert graph.max_dependency_chain == 4


def test_detects_cycles_without_infinite_loop() -> None:
    graph = build(
        entity("a", "procedure", qualified_name="dbo.a", called=("dbo.b",)),
        entity("b", "procedure", qualified_name="dbo.b", called=("dbo.a",)),
    )

    cycles = graph.metadata["cycles"]
    assert cycles
    assert any(cycle[0] == cycle[-1] for cycle in cycles)


def test_generates_deterministic_and_fallback_ids() -> None:
    graph = build(
        entity("refresh", "procedure", qualified_name="dbo.refresh"),
        entity("anonymous", "sql_script"),
        entity("active", "view", qualified_name="sales.active", ctes=(ParsedCTE("recent"),)),
        entity("orders", "sql_script", reads=(table("orders"),)),
    )

    node_ids = {node.node_id for node in graph.nodes}
    assert "procedure:dbo.refresh" in node_ids
    assert "sql_script:anonymous:1" in node_ids
    assert "cte:view:sales.active:recent" in node_ids
    assert "table:sales.orders" in node_ids


def test_models_are_frozen_and_use_immutable_collection_contracts() -> None:
    node = DependencyNode("table:sales.orders", "table", "orders", metadata=MappingProxyType({}))
    edge = DependencyEdge("a", "b", "READS", metadata=MappingProxyType({}))
    graph = DependencyGraph(nodes=(node,), edges=(edge,), metadata=MappingProxyType({}))

    for model in (DependencyNode, DependencyEdge, DependencyGraph):
        assert is_dataclass(model)
        assert model.__dataclass_params__.frozen

    assert isinstance(graph.nodes, tuple)
    assert isinstance(graph.edges, tuple)
    assert isinstance(graph.metadata, Mapping)
    with pytest.raises(FrozenInstanceError):
        node.name = "changed"  # type: ignore[misc]
