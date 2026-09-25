"""Traceable, non-sensitive evidence produced by Guardian analyses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


class EvidenceSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Evidence:
    """A rule result that explains an assessment without retaining SQL text."""

    evidence_id: str
    rule_id: str
    object_id: str
    severity: EvidenceSeverity
    summary: str
    line_start: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


__all__ = ["Evidence", "EvidenceSeverity"]
