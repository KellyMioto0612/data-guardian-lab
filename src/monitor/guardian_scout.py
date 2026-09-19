"""Lightweight polling orchestration for data-platform health signals."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


class ObservationSource(Protocol):
    def collect(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Observation:
    name: str
    value: float
    threshold: float
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class GuardianScout:
    """Collect observations without embedding vendor-specific logic."""

    def __init__(self, source: ObservationSource) -> None:
        self.source = source

    def run(self) -> list[Observation]:
        payload = self.source.collect()
        return [
            Observation(name, float(signal["value"]), float(signal["threshold"]), metadata=dict(signal.get("metadata", {})))
            for name, signal in payload.items()
        ]
