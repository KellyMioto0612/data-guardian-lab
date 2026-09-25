"""Canonical domain entity for assets observed by Data Guardian."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class GuardianObject:
    """Identify a data-platform asset independently of its source provider."""

    object_id: str
    object_type: str
    name: str
    platform: str
    workspace: str | None = None
    database: str | None = None
    schema: str | None = None
    path: str | None = None
    owner: str | None = None
    domain: str | None = None
    environment: str = "unknown"
    status: str = "unknown"
    source_system: str | None = None
    source_uri: str | None = None
    tags: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
