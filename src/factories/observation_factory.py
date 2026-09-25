"""Adapt canonical Guardian objects into immutable observations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.analyzers.dependency_graph import DependencyGraph
from src.models.guardian_object import GuardianObject
from src.models.sql_metrics import SQLEntityMetrics, SQLMetrics
from src.monitor.guardian_scout import Observation
from src.monitor.scanners.sql_parser import ParsedEntity


class ObservationFactory:
    """Build an observation while preserving the supplied domain identity."""

    def from_guardian_object(
        self,
        guardian_object: GuardianObject,
        *,
        metrics: SQLMetrics | None = None,
        dependency_graph: DependencyGraph | None = None,
        parsed: ParsedEntity | None = None,
    ) -> Observation:
        """Adapt a GuardianObject without recalculating identity or hashes."""
        metadata: dict[str, Any] = dict(guardian_object.metadata)
        metadata["object_id"] = guardian_object.object_id
        metadata["object_type"] = guardian_object.object_type
        metadata["database"] = guardian_object.database
        metadata["schema"] = guardian_object.schema
        metadata["tags"] = dict(guardian_object.tags)

        if parsed is not None:
            metadata.update(
                {
                    "qualified_name": parsed.qualified_name,
                    "source": parsed.source,
                    "confidence_score": parsed.confidence_score,
                    "entity_fingerprint_seed": parsed.entity_fingerprint_seed,
                }
            )

        entity = self._matching_entity(metrics, parsed, guardian_object)
        if entity is not None:
            metadata.update(
                {
                    "dependency_count": entity.dependency_count,
                    "join_count": entity.join_count,
                    "cte_count": entity.cte_count,
                    "called_procedure_count": entity.called_procedure_count,
                    "fan_out": entity.dependency_fan_out,
                }
            )

        if metrics is not None:
            metadata.setdefault("metrics", metrics)
            metadata.setdefault("aggregate_dependency_count", metrics.dependency_count)
            metadata.setdefault("aggregate_join_count", metrics.join_count)
            metadata.setdefault("aggregate_cte_count", metrics.cte_count)
            metadata.setdefault("aggregate_called_procedure_count", metrics.called_procedure_count)

        if dependency_graph is not None:
            metadata["dependency_graph_fan_out"] = dependency_graph.fan_out_by_node.get(
                guardian_object.object_id,
                dependency_graph.fan_out_by_node.get(
                    f"{guardian_object.object_type}:{guardian_object.object_id}", 0
                ),
            )

        return Observation(
            name=guardian_object.name,
            value=0.0,
            threshold=1.0,
            observed_at=datetime.now(UTC),
            metadata=metadata,
        )

    @staticmethod
    def _matching_entity(
        metrics: SQLMetrics | None,
        parsed: ParsedEntity | None,
        guardian_object: GuardianObject,
    ) -> SQLEntityMetrics | None:
        if metrics is None:
            return None
        candidates = tuple(metrics.entities)
        if parsed is not None:
            return next(
                (
                    entity
                    for entity in candidates
                    if entity.qualified_name == parsed.qualified_name or entity.name == parsed.name
                ),
                None,
            )
        return next(
            (
                entity
                for entity in candidates
                if entity.qualified_name == guardian_object.object_id
                or entity.name == guardian_object.name
            ),
            None,
        )


__all__ = ["ObservationFactory"]
