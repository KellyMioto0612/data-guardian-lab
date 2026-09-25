"""Consolidated, explainable inventory and priority ranking for Guardian assets."""

from __future__ import annotations

from dataclasses import dataclass

from src.models.evidence import Evidence, EvidenceSeverity
from src.models.guardian_object import GuardianObject

_SEVERITY_RANK = {
    EvidenceSeverity.LOW: 1,
    EvidenceSeverity.MEDIUM: 2,
    EvidenceSeverity.HIGH: 3,
    EvidenceSeverity.CRITICAL: 4,
}


@dataclass(frozen=True)
class AssetInventoryRecord:
    object_id: str
    name: str
    object_type: str
    tdi_score: float
    evidence_count: int
    highest_severity: EvidenceSeverity | None
    similarity_count: int
    downstream_impact: int
    priority_score: float
    criticality: str


def build_asset_inventory(
    assets: tuple[GuardianObject, ...] | list[GuardianObject],
    evidence: tuple[Evidence, ...] | list[Evidence],
) -> tuple[AssetInventoryRecord, ...]:
    """Build one safe, ranked record per asset from existing analysis output."""
    evidence_by_object: dict[str, list[Evidence]] = {}
    for item in evidence:
        evidence_by_object.setdefault(item.object_id, []).append(item)
    records = tuple(_record(asset, evidence_by_object.get(asset.object_id, [])) for asset in assets)
    return tuple(sorted(records, key=lambda item: (-item.priority_score, item.name)))


def filter_asset_inventory(
    records: tuple[AssetInventoryRecord, ...] | list[AssetInventoryRecord],
    *,
    object_types: set[str] | None = None,
    severities: set[str] | None = None,
    criticalities: set[str] | None = None,
) -> tuple[AssetInventoryRecord, ...]:
    """Filter inventory using explicit UI selections."""
    return tuple(
        item
        for item in records
        if (not object_types or item.object_type in object_types)
        and (
            not severities
            or (item.highest_severity.value if item.highest_severity else "none") in severities
        )
        and (not criticalities or item.criticality in criticalities)
    )


def _record(asset: GuardianObject, evidence: list[Evidence]) -> AssetInventoryRecord:
    metadata = asset.metadata
    debt = metadata.get("technical_debt", {})
    lineage = metadata.get("lineage", {})
    similarities = metadata.get("similarity_candidates", ())
    highest = max((item.severity for item in evidence), key=_SEVERITY_RANK.get, default=None)
    tdi_score = float(debt.get("score", 0.0))
    impact = int(lineage.get("impact_score", 0))
    priority = min(
        100.0,
        (0.6 * tdi_score)
        + (10 * _SEVERITY_RANK.get(highest, 0))
        + (5 * impact)
        + (3 * len(similarities)),
    )
    criticality = (
        "critical"
        if priority >= 80
        else "high"
        if priority >= 55
        else "medium"
        if priority >= 25
        else "low"
    )
    return AssetInventoryRecord(
        object_id=asset.object_id,
        name=asset.name,
        object_type=asset.object_type,
        tdi_score=tdi_score,
        evidence_count=len(evidence),
        highest_severity=highest,
        similarity_count=len(similarities),
        downstream_impact=impact,
        priority_score=round(priority, 2),
        criticality=criticality,
    )


__all__ = ["AssetInventoryRecord", "build_asset_inventory", "filter_asset_inventory"]
