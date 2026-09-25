"""Explainable Technical Debt Index for Guardian assets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.models.evidence import Evidence, EvidenceSeverity


class TDIClass(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class TDIResult:
    score: float
    classification: TDIClass
    evidence_ids: tuple[str, ...]


_PENALTIES = {
    EvidenceSeverity.LOW: 5.0,
    EvidenceSeverity.MEDIUM: 15.0,
    EvidenceSeverity.HIGH: 30.0,
    EvidenceSeverity.CRITICAL: 50.0,
}


def calculate_tdi(evidence: tuple[Evidence, ...] | list[Evidence]) -> TDIResult:
    """Return a 0-100 debt score; larger values indicate greater technical debt."""
    score = round(min(100.0, sum(_PENALTIES[item.severity] for item in evidence)), 2)
    classification = (
        TDIClass.LOW
        if score < 20
        else TDIClass.MODERATE
        if score < 50
        else TDIClass.HIGH
        if score < 80
        else TDIClass.CRITICAL
    )
    return TDIResult(score, classification, tuple(item.evidence_id for item in evidence))


__all__ = ["TDIClass", "TDIResult", "calculate_tdi"]
