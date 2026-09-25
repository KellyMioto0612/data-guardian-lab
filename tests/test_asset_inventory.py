"""Tests for consolidated asset inventory and priority filters."""

from src.analyzers.asset_inventory import build_asset_inventory, filter_asset_inventory
from src.models.evidence import Evidence, EvidenceSeverity
from src.models.guardian_object import GuardianObject


def test_inventory_consolidates_priority_signals() -> None:
    asset = GuardianObject(
        object_id="dbo.refresh_orders",
        object_type="procedure",
        name="refresh_orders",
        platform="sql",
        metadata={
            "technical_debt": {"score": 30},
            "lineage": {"impact_score": 2},
            "similarity_candidates": ({"object_id": "dbo.refresh_orders_legacy"},),
        },
    )
    evidence = Evidence("e-1", "SQL-010", asset.object_id, EvidenceSeverity.HIGH, "Safe summary")

    record = build_asset_inventory((asset,), (evidence,))[0]

    assert record.priority_score == 61.0
    assert record.criticality == "high"
    assert record.similarity_count == 1
    assert record.downstream_impact == 2


def test_inventory_filters_by_type_severity_and_criticality() -> None:
    assets = (
        GuardianObject("dbo.v_orders", "view", "v_orders", "sql"),
        GuardianObject(
            "dbo.p_orders",
            "procedure",
            "p_orders",
            "sql",
            metadata={"technical_debt": {"score": 45}},
        ),
    )
    evidence = (
        Evidence("e-low", "SQL-009", "dbo.v_orders", EvidenceSeverity.LOW, "Safe"),
        Evidence("e-high", "SQL-004", "dbo.p_orders", EvidenceSeverity.HIGH, "Safe"),
    )
    records = build_asset_inventory(assets, evidence)

    filtered = filter_asset_inventory(
        records, object_types={"procedure"}, severities={"high"}, criticalities={"high"}
    )

    assert [item.name for item in filtered] == ["p_orders"]


def test_inventory_can_filter_assets_without_evidence() -> None:
    asset = GuardianObject("dbo.v_empty", "view", "v_empty", "sql")

    records = build_asset_inventory((asset,), ())

    assert filter_asset_inventory(records, severities={"none"}) == records
