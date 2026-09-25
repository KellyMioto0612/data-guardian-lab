"""Read-only Synapse pipeline-run connector using Microsoft Entra tokens."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.models.pipeline_run import PipelineRun

_WORKSPACE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$", re.IGNORECASE)
_SCOPE = "https://dev.azuresynapse.net/.default"
_API_VERSION = "2020-12-01"


class TokenCredential(Protocol):
    def get_token(self, *scopes: str) -> Any: ...


class SynapseConnectorError(RuntimeError):
    """Safe operational error without response bodies, SQL or tokens."""


class SynapsePipelineConnector:
    """Fetch bounded pipeline-run metadata; it cannot create or alter Synapse resources."""

    def __init__(
        self,
        workspace: str,
        credential: TokenCredential,
        *,
        timeout_seconds: float = 20.0,
        max_pages: int = 10,
        transport: (
            Callable[[str, Mapping[str, str], Mapping[str, object], float], Mapping[str, object]]
            | None
        ) = None,
    ) -> None:
        if not _WORKSPACE.fullmatch(workspace):
            raise ValueError("Invalid Synapse workspace name")
        if timeout_seconds <= 0 or max_pages <= 0:
            raise ValueError("timeout_seconds and max_pages must be positive")
        self.workspace = workspace
        self.credential = credential
        self.timeout_seconds = timeout_seconds
        self.max_pages = max_pages
        self.transport = transport or self._post

    def query_pipeline_runs(
        self, *, last_updated_after: datetime, last_updated_before: datetime
    ) -> list[PipelineRun]:
        """Read pipeline-run metadata in a bounded time range and page count."""
        after = self._utc(last_updated_after)
        before = self._utc(last_updated_before)
        if after >= before:
            raise ValueError("last_updated_after must be before last_updated_before")
        if before - after > timedelta(days=7):
            raise ValueError("Synapse query interval cannot exceed seven days")
        token = self.credential.get_token(_SCOPE).token
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload: dict[str, object] = {
            "lastUpdatedAfter": self._iso(after),
            "lastUpdatedBefore": self._iso(before),
            "orderBy": [{"orderBy": "RunStart", "order": "DESC"}],
        }
        runs: list[PipelineRun] = []
        for page in range(self.max_pages):
            response = self.transport(self._url, headers, payload, self.timeout_seconds)
            values = response.get("value", ())
            if not isinstance(values, list):
                raise SynapseConnectorError("Synapse response has an invalid pipeline-run payload")
            runs.extend(self._to_pipeline_run(item, index) for index, item in enumerate(values))
            continuation = response.get("continuationToken")
            if not continuation:
                break
            if page == self.max_pages - 1:
                raise SynapseConnectorError(
                    "Synapse pagination limit reached; results are incomplete"
                )
            payload["continuationToken"] = str(continuation)
        return runs

    @property
    def _url(self) -> str:
        return f"https://{self.workspace}.dev.azuresynapse.net/queryPipelineRuns?api-version={_API_VERSION}"

    def _to_pipeline_run(self, value: object, index: int) -> PipelineRun:
        if not isinstance(value, Mapping):
            raise SynapseConnectorError("Synapse response contains an invalid pipeline run")
        started = self._timestamp(value.get("runStart") or value.get("lastUpdated"))
        ended = self._timestamp(value.get("runEnd")) if value.get("runEnd") else None
        duration = max(0, int((ended - started).total_seconds())) if ended else 0
        run_id = str(value.get("runId") or f"synapse-run-{index}")
        pipeline_name = str(value.get("pipelineName") or "unnamed-pipeline")
        return PipelineRun(
            pipeline_name=pipeline_name,
            run_id=run_id,
            status=self._status(str(value.get("status") or "Unknown")),
            started_at=started,
            duration_seconds=duration,
            metadata={"workspace": self.workspace, "source": "synapse_pipeline_runs"},
        )

    def _post(
        self, url: str, headers: Mapping[str, str], payload: Mapping[str, object], timeout: float
    ) -> Mapping[str, object]:
        request = Request(
            url,
            data=json.dumps(payload).encode(),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - validated Synapse URL.
                if response.status != 200:
                    raise SynapseConnectorError(
                        f"Synapse request failed with HTTP {response.status}"
                    )
                payload = json.loads(response.read().decode())
        except HTTPError as error:
            raise SynapseConnectorError(f"Synapse request failed with HTTP {error.code}") from error
        except URLError as error:
            raise SynapseConnectorError("Synapse network request failed") from error
        if not isinstance(payload, dict):
            raise SynapseConnectorError("Synapse response has an invalid payload")
        return payload

    @staticmethod
    def _status(value: str) -> str:
        return {
            "Succeeded": "Success",
            "Failed": "Failed",
            "Cancelled": "Failed",
            "InProgress": "Running",
            "Queued": "Running",
        }.get(value, value)

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise SynapseConnectorError("Synapse pipeline run has no valid timestamp")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise SynapseConnectorError("Synapse pipeline run has an invalid timestamp") from error
        return SynapsePipelineConnector._utc(parsed)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")


def recent_pipeline_runs(
    connector: SynapsePipelineConnector, *, lookback_hours: int = 24, now: datetime | None = None
) -> list[PipelineRun]:
    """Read at most the requested lookback interval, defaulting to 24 hours."""
    if lookback_hours <= 0 or lookback_hours > 168:
        raise ValueError("lookback_hours must be between 1 and 168")
    end = SynapsePipelineConnector._utc(now or datetime.now(UTC))
    return connector.query_pipeline_runs(
        last_updated_after=end - timedelta(hours=lookback_hours), last_updated_before=end
    )


__all__ = ["SynapseConnectorError", "SynapsePipelineConnector", "recent_pipeline_runs"]
