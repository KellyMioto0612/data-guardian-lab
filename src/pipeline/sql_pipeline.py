"""Integration facade for complete SQL pipeline executions."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.models.pipeline_run import PipelineRun
from src.monitor.scanners.sql_scanner import SQLScanner


class SQLPipeline:
    """Validate and expose scanner executions as complete ``PipelineRun`` values."""

    def __init__(self, scanner: SQLScanner | None = None) -> None:
        self.scanner = scanner or SQLScanner()

    def run_file(self, path: str | Path, **kwargs: object) -> PipelineRun:
        """Run one file through the scanner and validate its consolidated result."""
        result = self.scanner.scan_file(path, **kwargs)
        return self._validated(result)

    def run_directory(self, path: str | Path, **kwargs: object) -> PipelineRun:
        """Run a directory and validate all aggregate pipeline components."""
        result = self.scanner.scan_directory(path, **kwargs)
        return self._validated(result)

    def run_repository(self, path: str | Path, **kwargs: object) -> PipelineRun:
        """Run a repository through the scanner's repository entry point."""
        result = self.scanner.scan_repository(path, **kwargs)
        return self._validated(result)

    def _validated(self, result: PipelineRun) -> PipelineRun:
        self._validate_metrics(result)
        self._validate_graph(result)
        observations = tuple(result.observations)
        objects = tuple(result.guardian_objects)
        if len(observations) > len(objects):
            raise ValueError("observations cannot exceed guardian_objects")
        processed_files = tuple(dict.fromkeys(result.processed_files))
        status = self._status(result)
        return replace(
            result,
            observations=observations,
            guardian_objects=objects,
            processed_files=processed_files,
            status=status,
        )

    @staticmethod
    def _validate_metrics(result: PipelineRun) -> None:
        if result.metrics is None:
            return
        values = (
            result.metrics.entity_count,
            result.metrics.statement_count,
            result.metrics.join_count,
            result.metrics.cte_count,
        )
        if any(value < 0 for value in values):
            raise ValueError("pipeline metrics cannot be negative")

    @staticmethod
    def _validate_graph(result: PipelineRun) -> None:
        graph = result.dependency_graph
        if graph is None:
            return
        node_ids = tuple(node.node_id for node in graph.nodes)
        edge_ids = tuple(edge.edge_id for edge in graph.edges)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("dependency graph contains duplicate nodes")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("dependency graph contains duplicate edges")
        expected = {}
        for edge in graph.edges:
            expected[edge.source_id] = expected.get(edge.source_id, 0) + 1
        if dict(graph.fan_out_by_node) != expected:
            raise ValueError("dependency graph fan_out_by_node is inconsistent")

    @staticmethod
    def _status(result: PipelineRun) -> str:
        has_errors = bool(result.error_message) or result.parse_error_count > 0
        has_output = bool(result.observations or result.guardian_objects or result.metrics)
        if has_errors and has_output:
            return "PARTIAL"
        if has_errors:
            return "FAILED"
        return "SUCCESS"


__all__ = ["SQLPipeline"]
