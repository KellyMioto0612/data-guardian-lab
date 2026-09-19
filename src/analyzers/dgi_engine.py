"""Data Governance Index calculation for Guardian Objects."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Sequence

from src.models.guardian_object import GuardianObject
from src.monitor.guardian_scout import Observation


class DGIClass(StrEnum):
    """DGI classification bands."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


@dataclass(frozen=True)
class CriterionResult:
    """Result produced by one DGI criterion."""

    name: str
    score: float
    reason: str
    weight: float


@dataclass(frozen=True)
class DGIResult:
    """Final DGI evaluation."""

    guardian_object: GuardianObject
    observation: Observation
    score: float
    classification: DGIClass
    reasons: tuple[str, ...]


DGICriterion = Callable[
    [GuardianObject, Observation],
    CriterionResult,
]


def _clamp_score(score: float) -> float:
    """Keep a score inside the official 0-100 range."""
    return round(max(0.0, min(100.0, score)), 2)


def _validate_threshold(observation: Observation) -> None:
    """Reject observations without a valid positive threshold."""
    if observation.threshold <= 0:
        raise ValueError("threshold must be greater than zero")


def _calculate_observation_score(observation: Observation) -> float:
    """Calculate the operational health score from value and threshold."""
    _validate_threshold(observation)

    if observation.value <= observation.threshold:
        return 100.0

    if observation.value >= 2 * observation.threshold:
        return 0.0

    score = 100.0 - (
        (observation.value - observation.threshold)
        / observation.threshold
        * 100.0
    )
    return _clamp_score(score)


def _is_present(value: object) -> bool:
    """Check whether a governance field contains meaningful data."""
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() != "unknown"

    return True


def _calculate_object_completeness(
    guardian_object: GuardianObject,
) -> float:
    """Score the five mandatory GuardianObject governance fields."""
    required_fields = (
        guardian_object.object_id,
        guardian_object.name,
        guardian_object.platform,
        guardian_object.owner,
        guardian_object.domain,
    )
    present_fields = sum(
        _is_present(value) for value in required_fields
    )
    return _clamp_score(present_fields / len(required_fields) * 100.0)


def _observation_criterion(
    _: GuardianObject,
    observation: Observation,
) -> CriterionResult:
    score = _calculate_observation_score(observation)
    return CriterionResult(
        name="observation_health",
        score=score,
        reason=(
            f"DG-RSN-001 observation health for "
            f"'{observation.name}': {score:g}"
        ),
        weight=0.60,
    )


def _object_completeness_criterion(
    guardian_object: GuardianObject,
    _: Observation,
) -> CriterionResult:
    score = _calculate_object_completeness(guardian_object)
    return CriterionResult(
        name="object_completeness",
        score=score,
        reason=(
            f"DG-RSN-002 GuardianObject completeness for "
            f"'{guardian_object.object_id}': {score:g}"
        ),
        weight=0.40,
    )


def _validate_criterion(result: CriterionResult) -> None:
    """Validate a criterion before it participates in the weighted score."""
    if result.weight < 0:
        raise ValueError("criterion weight must not be negative")

    if result.weight == 0:
        return

    if result.score < 0 or result.score > 100:
        raise ValueError("criterion score must be between 0 and 100")


def _calculate_weighted_score(
    results: Sequence[CriterionResult],
) -> float:
    """Combine criterion scores using their explicit weights."""
    active_results = tuple(
        result for result in results if result.weight > 0
    )

    if not active_results:
        raise ValueError("at least one criterion with a positive weight is required")

    for result in active_results:
        _validate_criterion(result)

    total_weight = sum(result.weight for result in active_results)
    weighted_score = sum(
        result.score * result.weight for result in active_results
    ) / total_weight

    return _clamp_score(weighted_score)


def _classify(score: float) -> DGIClass:
    """Convert a normalized DGI score into the official A-E class."""
    if score >= 90:
        return DGIClass.A
    if score >= 75:
        return DGIClass.B
    if score >= 60:
        return DGIClass.C
    if score >= 40:
        return DGIClass.D
    return DGIClass.E


def calculate_dgi(
    guardian_object: GuardianObject,
    observation: Observation,
    criteria: Sequence[DGICriterion] | None = None,
) -> DGIResult:
    """Calculate the DGI for one GuardianObject and one Observation.

    When ``criteria`` is omitted, the official default formula is used:

        DGI = ObservationScore * 0.60
            + ObjectCompletenessScore * 0.40

    Custom criteria can be injected without changing the result contract.
    """
    active_criteria = tuple(
        criteria
        if criteria is not None
        else (
            _observation_criterion,
            _object_completeness_criterion,
        )
    )

    if not active_criteria:
        raise ValueError("at least one DGI criterion is required")

    criterion_results = tuple(
        criterion(guardian_object, observation)
        for criterion in active_criteria
    )
    score = _calculate_weighted_score(criterion_results)

    return DGIResult(
        guardian_object=guardian_object,
        observation=observation,
        score=score,
        classification=_classify(score),
        reasons=tuple(
            result.reason for result in criterion_results
        ),
    )
