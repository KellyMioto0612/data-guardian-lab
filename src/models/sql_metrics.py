"""Immutable SQL metrics models."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


def _validate_non_negative(name: str, value: int | float | None) -> None:
    if value is not None and value < 0:
        raise ValueError(f"{name} must be non-negative")


def _validate_ratio(name: str, value: float | None) -> None:
    if value is not None and not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")


def _freeze_mapping(value: Mapping[str, object] | None) -> Mapping[str, object]:
    if value is None:
        value = {}
    return MappingProxyType(dict(sorted(value.items(), key=lambda item: str(item[0]))))


def _sorted_tuple(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    return tuple(sorted(values or ()))


@dataclass(frozen=True)
class JoinTypeCounts:
    """Deterministic distribution of JOIN types."""

    inner: int = 0
    left: int = 0
    right: int = 0
    full: int = 0
    cross: int = 0
    natural: int = 0
    unknown: int = 0

    def __post_init__(self) -> None:
        for name in ("inner", "left", "right", "full", "cross", "natural", "unknown"):
            _validate_non_negative(name, getattr(self, name))

    @property
    def total(self) -> int:
        return sum((self.inner, self.left, self.right, self.full, self.cross, self.natural, self.unknown))

    def as_mapping(self) -> Mapping[str, int]:
        return MappingProxyType({
            "CROSS": self.cross,
            "FULL": self.full,
            "INNER": self.inner,
            "LEFT": self.left,
            "NATURAL": self.natural,
            "RIGHT": self.right,
            "UNKNOWN": self.unknown,
        })


@dataclass(frozen=True)
class DependencyFanOut:
    """Fan-out observed for one dependency object."""

    object_id: str
    fan_out: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_negative("fan_out", self.fan_out)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class MetricMetadata:
    """Optional provenance and implementation metadata for metrics."""

    source: str = "parsed_sql"
    confidence_score: float | None = None
    values: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_ratio("confidence_score", self.confidence_score)
        object.__setattr__(self, "values", _freeze_mapping(self.values))


@dataclass(frozen=True)
class SQLEntityMetrics:
    """Metrics calculated for one parsed SQL entity."""

    name: str | None = None
    entity_type: str = "sql_script"
    statement_type: str | None = None
    qualified_name: str | None = None
    statement_count: int = 1
    procedure_count: int = 0
    view_count: int = 0
    script_count: int = 0
    cte_count: int = 0
    recursive_cte_count: int = 0
    max_cte_depth: int | None = 0
    join_count: int = 0
    join_types: JoinTypeCounts | Mapping[str, int] = field(default_factory=JoinTypeCounts)
    cross_join_count: int = 0
    joins_without_condition: int = 0
    read_table_count: int = 0
    written_table_count: int = 0
    unique_table_count: int = 0
    table_reference_count: int = 0
    dependency_count: int = 0
    dependency_fan_out: int = 0
    dependency_fan_out_by_object: Mapping[str, int] = field(default_factory=dict)
    called_procedure_count: int = 0
    tables_read: tuple[str, ...] = ()
    tables_written: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    called_procedures: tuple[str, ...] = ()
    cte_names: tuple[str, ...] = ()
    cte_reuse_index: float | None = None
    parse_error_count: int = 0
    warning_count: int = 0
    complexity_score: float | None = None
    content_hash: str | None = None
    semantic_hash: str | None = None
    metadata: MetricMetadata | Mapping[str, object] = field(default_factory=MetricMetadata)

    def __post_init__(self) -> None:
        counters = (
            "statement_count", "procedure_count", "view_count", "script_count",
            "cte_count", "recursive_cte_count", "join_count", "cross_join_count",
            "joins_without_condition", "read_table_count", "written_table_count",
            "unique_table_count", "table_reference_count", "dependency_count",
            "dependency_fan_out", "called_procedure_count", "parse_error_count",
            "warning_count",
        )
        for name in counters:
            _validate_non_negative(name, getattr(self, name))
        _validate_non_negative("max_cte_depth", self.max_cte_depth)
        _validate_ratio("cte_reuse_index", self.cte_reuse_index)
        join_types = self.join_types
        if isinstance(join_types, Mapping):
            join_types = JoinTypeCounts(
                inner=int(join_types.get("INNER", join_types.get("inner", 0))),
                left=int(join_types.get("LEFT", join_types.get("left", 0))),
                right=int(join_types.get("RIGHT", join_types.get("right", 0))),
                full=int(join_types.get("FULL", join_types.get("full", 0))),
                cross=int(join_types.get("CROSS", join_types.get("cross", 0))),
                natural=int(join_types.get("NATURAL", join_types.get("natural", 0))),
                unknown=int(join_types.get("UNKNOWN", join_types.get("unknown", 0))),
            )
        object.__setattr__(self, "join_types", join_types)
        object.__setattr__(self, "dependency_fan_out_by_object", _freeze_mapping(self.dependency_fan_out_by_object))
        object.__setattr__(self, "tables_read", _sorted_tuple(self.tables_read))
        object.__setattr__(self, "tables_written", _sorted_tuple(self.tables_written))
        object.__setattr__(self, "dependencies", _sorted_tuple(self.dependencies))
        object.__setattr__(self, "called_procedures", _sorted_tuple(self.called_procedures))
        object.__setattr__(self, "cte_names", _sorted_tuple(self.cte_names))
        if isinstance(self.metadata, Mapping):
            object.__setattr__(self, "metadata", MetricMetadata(values=self.metadata))


@dataclass(frozen=True)
class SQLMetrics:
    """Aggregate metrics for a ParsedSQL document."""

    entity_count: int = 0
    procedure_count: int = 0
    view_count: int = 0
    script_count: int = 0
    statement_count: int = 0
    cte_count: int = 0
    recursive_cte_count: int = 0
    max_cte_depth: int | None = 0
    join_count: int = 0
    join_types: JoinTypeCounts | Mapping[str, int] = field(default_factory=JoinTypeCounts)
    cross_join_count: int = 0
    joins_without_condition: int = 0
    read_table_count: int = 0
    written_table_count: int = 0
    unique_table_count: int = 0
    table_reference_count: int = 0
    dependency_count: int = 0
    dependency_fan_out: int = 0
    dependency_fan_out_by_object: Mapping[str, int] = field(default_factory=dict)
    called_procedure_count: int = 0
    parse_error_count: int = 0
    warning_count: int = 0
    tables_read: tuple[str, ...] = ()
    tables_written: tuple[str, ...] = ()
    unique_tables: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    entities: tuple[SQLEntityMetrics, ...] = ()
    complexity_score: float | None = None
    content_hash: str | None = None
    semantic_hash: str | None = None
    metadata: MetricMetadata | Mapping[str, object] = field(default_factory=MetricMetadata)

    def __post_init__(self) -> None:
        counters = (
            "entity_count", "procedure_count", "view_count", "script_count",
            "statement_count", "cte_count", "recursive_cte_count", "join_count",
            "cross_join_count", "joins_without_condition", "read_table_count",
            "written_table_count", "unique_table_count", "table_reference_count",
            "dependency_count", "dependency_fan_out", "called_procedure_count",
            "parse_error_count", "warning_count",
        )
        for name in counters:
            _validate_non_negative(name, getattr(self, name))
        _validate_non_negative("max_cte_depth", self.max_cte_depth)
        join_types = self.join_types
        if isinstance(join_types, Mapping):
            join_types = JoinTypeCounts(
                inner=int(join_types.get("INNER", join_types.get("inner", 0))),
                left=int(join_types.get("LEFT", join_types.get("left", 0))),
                right=int(join_types.get("RIGHT", join_types.get("right", 0))),
                full=int(join_types.get("FULL", join_types.get("full", 0))),
                cross=int(join_types.get("CROSS", join_types.get("cross", 0))),
                natural=int(join_types.get("NATURAL", join_types.get("natural", 0))),
                unknown=int(join_types.get("UNKNOWN", join_types.get("unknown", 0))),
            )
        object.__setattr__(self, "join_types", join_types)
        object.__setattr__(self, "dependency_fan_out_by_object", _freeze_mapping(self.dependency_fan_out_by_object))
        object.__setattr__(self, "tables_read", _sorted_tuple(self.tables_read))
        object.__setattr__(self, "tables_written", _sorted_tuple(self.tables_written))
        object.__setattr__(self, "unique_tables", _sorted_tuple(self.unique_tables))
        object.__setattr__(self, "dependencies", _sorted_tuple(self.dependencies))
        object.__setattr__(self, "entities", tuple(sorted(self.entities, key=lambda item: (item.qualified_name or "", item.name or ""))))
        if isinstance(self.metadata, Mapping):
            object.__setattr__(self, "metadata", MetricMetadata(values=self.metadata))


__all__ = [
    "DependencyFanOut",
    "JoinTypeCounts",
    "MetricMetadata",
    "SQLEntityMetrics",
    "SQLMetrics",
]
