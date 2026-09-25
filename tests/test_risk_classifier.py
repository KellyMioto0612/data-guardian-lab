from datetime import UTC, datetime

import pytest

from src.analyzers.risk_classifier import RiskLevel, classify
from src.monitor.guardian_scout import Observation


def observation(value: float, threshold: float = 10) -> Observation:
    return Observation("pipeline_latency", value, threshold, datetime.now(UTC))


def test_classifies_risk_by_threshold_distance() -> None:
    assert classify(observation(5)).level is RiskLevel.LOW
    assert classify(observation(10)).level is RiskLevel.MEDIUM
    assert classify(observation(15)).level is RiskLevel.HIGH
    assert classify(observation(20)).level is RiskLevel.CRITICAL


def test_assessment_contains_explainable_score_and_reason() -> None:
    assessment = classify(observation(12))
    assert assessment.score == 120.0
    assert assessment.reasons == ("pipeline_latency: 12 / 10",)


def test_rejects_invalid_threshold() -> None:
    with pytest.raises(ValueError, match="threshold"):
        classify(observation(1, threshold=0))
