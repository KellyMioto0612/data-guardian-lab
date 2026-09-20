"""Adapt parsed SQL entities into canonical Guardian objects."""

from __future__ import annotations

from collections.abc import Mapping

from src.models.guardian_object import GuardianObject
from src.monitor.scanners.sql_parser import ParsedEntity


class GuardianObjectFactory:
    """Create immutable domain objects without recomputing parser identity."""

    def from_parsed_entity(self, entity: ParsedEntity) -> GuardianObject:
        """Adapt one parser entity to a :class:`GuardianObject`."""
        object_id = (
            entity.qualified_name
            or entity.entity_fingerprint_seed
            or entity.name
            or "statement"
        )
        name = entity.name or (entity.qualified_name or object_id).rsplit(".", 1)[-1]
        metadata = dict(entity.metadata)
        tags = metadata.pop("tags", {})
        if not isinstance(tags, Mapping):
            tags = {}

        provenance = {
            "source": entity.source,
            "confidence_score": entity.confidence_score,
        }
        metadata.setdefault("provenance", provenance)

        return GuardianObject(
            object_id=object_id,
            object_type=entity.entity_type.strip().lower(),
            name=name,
            platform="sql",
            database=entity.database,
            schema=entity.schema,
            tags=dict(tags),
            metadata=metadata,
        )


__all__ = ["GuardianObjectFactory"]
