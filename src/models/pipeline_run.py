"""Normalized pipeline execution model."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from src.analyzers.dependency_graph import DependencyGraph
from src.models.guardian_object import GuardianObject
from src.models.sql_metrics import SQLMetrics
from src.monitor.guardian_scout import Observation


@dataclass(frozen=True)
class PipelineRun:
    pipeline_name: str
    run_id: str
    status: str
    started_at: datetime
    duration_seconds: int
    error_message: str | None = None
    observations: tuple[Observation, ...] = ()
    guardian_objects: tuple[GuardianObject, ...] = ()
    metrics: SQLMetrics | None = None
    dependency_graph: DependencyGraph | None = None
    processed_files: tuple[str, ...] = ()
    parse_error_count: int = 0
    warning_count: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.parse_error_count < 0:
            raise ValueError("parse_error_count must be non-negative")
        if self.warning_count < 0:
            raise ValueError("warning_count must be non-negative")
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "guardian_objects", tuple(self.guardian_objects))
        object.__setattr__(self, "processed_files", tuple(self.processed_files))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()
        return data
