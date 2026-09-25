"""Tests for dependency impact and lineage traversal."""

from src.analyzers.dependency_graph import DependencyEdge, DependencyGraph, DependencyNode
from src.analyzers.lineage import LineageAnalyzer


def test_resolves_transitive_upstream_and_downstream_impact() -> None:
    graph = DependencyGraph(
        nodes=(
            DependencyNode("procedure:dbo.refresh", "procedure", "refresh", "dbo.refresh"),
            DependencyNode("view:dbo.orders", "view", "orders", "dbo.orders"),
            DependencyNode("table:dbo.raw_orders", "table", "raw_orders", "dbo.raw_orders"),
            DependencyNode("procedure:dbo.consume", "procedure", "consume", "dbo.consume"),
        ),
        edges=(
            DependencyEdge("procedure:dbo.refresh", "view:dbo.orders", "READS"),
            DependencyEdge("view:dbo.orders", "table:dbo.raw_orders", "READS"),
            DependencyEdge("procedure:dbo.consume", "procedure:dbo.refresh", "CALLS"),
        ),
    )

    summary = LineageAnalyzer().summarize(graph, "dbo.refresh")

    assert summary.upstream == ("table:dbo.raw_orders", "view:dbo.orders")
    assert summary.downstream == ("procedure:dbo.consume",)
    assert summary.max_upstream_depth == 2
    assert summary.max_downstream_depth == 1
    assert summary.impact_score == 1


def test_marks_node_that_participates_in_cycle() -> None:
    graph = DependencyGraph(
        nodes=(DependencyNode("procedure:a", "procedure", "a", "a"),),
        metadata={"cycles": (("procedure:a", "procedure:a"),)},
    )

    assert LineageAnalyzer().summarize(graph, "a").participates_in_cycle is True
