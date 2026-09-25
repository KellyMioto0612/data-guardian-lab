from datetime import UTC, datetime

import pytest

from src.analyzers.dgi_engine import (
    CriterionResult,
    DGIClass,
    calculate_dgi,
)
from src.models.guardian_object import GuardianObject
from src.monitor.guardian_scout import Observation


def make_guardian_object(
    *,
    owner: str | None = "data-team",
    domain: str | None = "sales",
) -> GuardianObject:
    return GuardianObject(
        object_id="pipeline-orders",
        object_type="pipeline",
        name="orders_pipeline",
        platform="synapse",
        owner=owner,
        domain=domain,
    )


def make_observation(
    value: float,
    threshold: float = 10.0,
) -> Observation:
    return Observation(
        name="failed_runs",
        value=value,
        threshold=threshold,
        observed_at=datetime.now(UTC),
    )


def test_returns_dgi_100_for_healthy_observation_and_complete_object() -> None:
    result = calculate_dgi(
        make_guardian_object(),
        make_observation(value=0),
    )

    assert result.score == 100.0
    assert result.classification is DGIClass.A
    assert result.guardian_object.object_id == "pipeline-orders"
    assert result.observation.name == "failed_runs"
    assert "DG-RSN-001" in result.reasons[0]
    assert "DG-RSN-002" in result.reasons[1]


def test_calculates_intermediate_dgi() -> None:
    result = calculate_dgi(
        make_guardian_object(),
        make_observation(value=15),
    )

    assert result.score == 70.0
    assert result.classification is DGIClass.C


def test_calculates_critical_dgi() -> None:
    result = calculate_dgi(
        make_guardian_object(owner=None, domain=None),
        make_observation(value=20),
    )

    assert result.score == 24.0
    assert result.classification is DGIClass.E


@pytest.mark.parametrize(
    ("value", "owner", "domain", "expected_class"),
    [
        (0, "data-team", "sales", DGIClass.A),
        (12, "data-team", "sales", DGIClass.B),
        (15, "data-team", "sales", DGIClass.C),
        (18, "data-team", "sales", DGIClass.D),
        (20, None, None, DGIClass.E),
    ],
)
def test_classifies_all_dgi_bands(
    value: float,
    owner: str | None,
    domain: str | None,
    expected_class: DGIClass,
) -> None:
    result = calculate_dgi(
        make_guardian_object(owner=owner, domain=domain),
        make_observation(value=value),
    )

    assert result.classification is expected_class


def test_value_equal_to_threshold_scores_observation_as_healthy() -> None:
    result = calculate_dgi(
        make_guardian_object(),
        make_observation(value=10),
    )

    assert result.score == 100.0
    assert result.classification is DGIClass.A


def test_value_equal_to_twice_threshold_scores_observation_as_zero() -> None:
    result = calculate_dgi(
        make_guardian_object(),
        make_observation(value=20),
    )

    assert result.score == 40.0
    assert result.classification is DGIClass.D


def test_rejects_zero_threshold() -> None:
    with pytest.raises(ValueError, match="threshold"):
        calculate_dgi(
            make_guardian_object(),
            make_observation(value=1, threshold=0),
        )


def test_incomplete_guardian_object_reduces_dgi() -> None:
    complete_result = calculate_dgi(
        make_guardian_object(),
        make_observation(value=0),
    )
    incomplete_result = calculate_dgi(
        make_guardian_object(owner=None, domain=None),
        make_observation(value=0),
    )

    assert complete_result.score == 100.0
    assert incomplete_result.score == 84.0
    assert incomplete_result.score < complete_result.score


def test_accepts_injected_criterion() -> None:
    def custom_criterion(
        _: GuardianObject,
        __: Observation,
    ) -> CriterionResult:
        return CriterionResult(
            name="custom_criterion",
            score=80.0,
            reason="DG-RSN-100 custom criterion passed",
            weight=1.0,
        )

    result = calculate_dgi(
        make_guardian_object(),
        make_observation(value=0),
        criteria=[custom_criterion],
    )

    assert result.score == 80.0
    assert result.classification is DGIClass.B
    assert result.reasons == ("DG-RSN-100 custom criterion passed",)


@pytest.mark.parametrize(
    "value",
    [-100, 0, 10, 15, 20, 1000],
)
def test_score_remains_between_zero_and_hundred(value: float) -> None:
    result = calculate_dgi(
        make_guardian_object(),
        make_observation(value=value),
    )

    assert 0.0 <= result.score <= 100.0
