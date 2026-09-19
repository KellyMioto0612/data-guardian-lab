"""Normalized pipeline execution model."""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PipelineRun:
    pipeline_name: str
    run_id: str
    status: str
    started_at: datetime
    duration_seconds: int
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()
        return data
