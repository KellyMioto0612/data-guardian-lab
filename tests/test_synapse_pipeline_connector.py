"""Tests for bounded, read-only Synapse pipeline-run retrieval."""

from datetime import UTC, datetime

import pytest

from src.connectors.synapse_pipeline import (
    SynapseConnectorError,
    SynapsePipelineConnector,
    recent_pipeline_runs,
)


class _Token:
    token = "not-a-real-token"


class _Credential:
    def get_token(self, *_scopes: str) -> _Token:
        return _Token()


def test_queries_pipeline_runs_with_bounded_safe_payload() -> None:
    calls = []

    def transport(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return {
            "value": [
                {
                    "runId": "run-1",
                    "pipelineName": "daily_orders",
                    "status": "Succeeded",
                    "runStart": "2026-09-23T10:00:00Z",
                    "runEnd": "2026-09-23T10:02:30Z",
                }
            ]
        }

    connector = SynapsePipelineConnector("workspace-dev-1", _Credential(), transport=transport)
    runs = recent_pipeline_runs(connector, now=datetime(2026, 9, 23, 12, tzinfo=UTC))

    assert len(runs) == 1
    assert runs[0].status == "Success"
    assert runs[0].duration_seconds == 150
    assert calls[0][0].endswith("queryPipelineRuns?api-version=2020-12-01")
    assert calls[0][2]["lastUpdatedAfter"] == "2026-09-22T12:00:00Z"
    assert "not-a-real-token" not in str(runs[0].metadata)


def test_rejects_invalid_workspace_and_unbounded_lookback() -> None:
    with pytest.raises(ValueError, match="workspace"):
        SynapsePipelineConnector("invalid/workspace", _Credential())
    connector = SynapsePipelineConnector("workspace-dev-1", _Credential(), transport=lambda *_: {})
    with pytest.raises(ValueError, match="lookback"):
        recent_pipeline_runs(connector, lookback_hours=169)
    with pytest.raises(ValueError, match="seven days"):
        connector.query_pipeline_runs(
            last_updated_after=datetime(2026, 9, 1, tzinfo=UTC),
            last_updated_before=datetime(2026, 9, 9, tzinfo=UTC),
        )


def test_rejects_partial_pagination_instead_of_reporting_incomplete_rates() -> None:
    connector = SynapsePipelineConnector(
        "workspace-dev-1", _Credential(), max_pages=1,
        transport=lambda *_: {"value": [], "continuationToken": "more"},
    )
    with pytest.raises(SynapseConnectorError, match="incomplete"):
        recent_pipeline_runs(connector, now=datetime(2026, 9, 23, 12, tzinfo=UTC))
