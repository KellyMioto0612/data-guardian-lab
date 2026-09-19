"""Explainable risk classification for normalized observations."""

from dataclasses import dataclass
from enum import StrEnum

from src.monitor.guardian_scout import Observation


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    score: float
    reasons: tuple[str, ...]


def classify(observation: Observation) -> RiskAssessment:
    if observation.threshold <= 0:
        raise ValueError("threshold must be greater than zero")
    score = max(0.0, observation.value / observation.threshold * 100)
    if score >= 200:
        level = RiskLevel.CRITICAL
    elif score >= 150:
        level = RiskLevel.HIGH
    elif score >= 100:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW
    reason = f"{observation.name}: {observation.value:g} / {observation.threshold:g}"
    return RiskAssessment(level, round(score, 2), (reason,))
