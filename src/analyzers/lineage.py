"""Impact-oriented traversal over the immutable SQL dependency graph."""

from __future__ import annotations

from dataclasses import dataclass

from src.analyzers.dependency_graph import DependencyGraph


@dataclass(frozen=True)
class LineageSummary:
    """Safe dependency and impact summary for one Guardian asset."""

    object_id: str
    upstream: tuple[str, ...]
    downstream: tuple[str, ...]
    max_upstream_depth: int
    max_downstream_depth: int
    participates_in_cycle: bool

    @property
    def impact_score(self) -> int:
        """A transparent priority signal based on downstream reach."""
        return len(self.downstream)


class LineageAnalyzer:
    """Resolve direct and transitive impact without mutating the graph."""

    def summarize(self, graph: DependencyGraph, identifier: str) -> LineageSummary:
        node_id = self._resolve_node_id(graph, identifier)
        if node_id is None:
            return LineageSummary(identifier, (), (), 0, 0, False)
        forward: dict[str, set[str]] = {}
        reverse: dict[str, set[str]] = {}
        for edge in graph.edges:
            forward.setdefault(edge.source_id, set()).add(edge.target_id)
            reverse.setdefault(edge.target_id, set()).add(edge.source_id)
        upstream, upstream_depth = self._walk(node_id, forward)
        downstream, downstream_depth = self._walk(node_id, reverse)
        cycles = graph.metadata.get("cycles", ())
        in_cycle = any(node_id in cycle for cycle in cycles if isinstance(cycle, tuple))
        return LineageSummary(
            object_id=identifier,
            upstream=tuple(sorted(upstream)),
            downstream=tuple(sorted(downstream)),
            max_upstream_depth=upstream_depth,
            max_downstream_depth=downstream_depth,
            participates_in_cycle=in_cycle,
        )

    @staticmethod
    def _resolve_node_id(graph: DependencyGraph, identifier: str) -> str | None:
        matches = [
            node.node_id
            for node in graph.nodes
            if identifier in {node.node_id, node.qualified_name, node.name}
        ]
        return sorted(matches)[0] if matches else None

    @staticmethod
    def _walk(root: str, adjacency: dict[str, set[str]]) -> tuple[set[str], int]:
        discovered: set[str] = set()
        frontier = {root}
        depth = 0
        while frontier:
            next_frontier = set().union(*(adjacency.get(item, set()) for item in frontier))
            next_frontier -= discovered | {root}
            if not next_frontier:
                break
            discovered.update(next_frontier)
            frontier = next_frontier
            depth += 1
        return discovered, depth


__all__ = ["LineageAnalyzer", "LineageSummary"]
