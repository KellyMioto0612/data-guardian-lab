"""Orchestrate SQL parsing, analysis, and domain adaptation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Iterable

from src.analyzers.dependency_graph import DependencyGraphBuilder
from src.analyzers.sql_metrics_calculator import SQLMetricsCalculator
from src.factories.guardian_object_factory import GuardianObjectFactory
from src.factories.observation_factory import ObservationFactory
from src.models.pipeline_run import PipelineRun
from src.monitor.scanners.sql_parser import ParsedEntity, ParsedSQL, SQLParser


_SUPPORTED_SUFFIXES = frozenset({".sql", ".ddl", ".prc", ".vw"})


class SQLScanner:
    """Run the Foundation components over SQL files deterministically."""

    def __init__(self) -> None:
        self.parser = SQLParser()
        self.metrics_calculator = SQLMetricsCalculator()
        self.dependency_graph_builder = DependencyGraphBuilder()
        self.guardian_object_factory = GuardianObjectFactory()
        self.observation_factory = ObservationFactory()

    def scan_file(
        self,
        path: str | Path,
        *,
        source_uri: str | None = None,
        revision: str | None = None,
    ) -> PipelineRun:
        """Scan one UTF-8 file, recording failures in the returned run."""
        file_path = Path(path)
        started, clock = datetime.now(timezone.utc), monotonic()
        try:
            text = file_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            return self._run(file_path, started, clock, status="failed", error_message=self._error(error), processed_files=(file_path.as_posix(),), source_uri=source_uri, revision=revision)
        if not text.strip():
            return self._run(file_path, started, clock, status="ignored", processed_files=(), source_uri=source_uri, revision=revision)
        return self._scan_text(text, file_path, started, clock, source_uri=source_uri, revision=revision)

    def scan_directory(self, path: str | Path, *, source_uri: str | None = None, revision: str | None = None) -> PipelineRun:
        """Recursively scan supported files in stable relative-path order."""
        root = Path(path)
        files = sorted(
            (item for item in root.rglob("*") if item.is_file() and item.suffix.lower() in _SUPPORTED_SUFFIXES),
            key=lambda item: item.relative_to(root).as_posix(),
        )
        return self._scan_paths(files, root, source_uri=source_uri, revision=revision)

    def scan_repository(self, path: str | Path, *, source_uri: str | None = None, revision: str | None = None) -> PipelineRun:
        """Scan a repository directory through :meth:`scan_directory`."""
        return self.scan_directory(path, source_uri=source_uri, revision=revision)

    def _scan_paths(self, paths: Iterable[Path], root: Path, *, source_uri: str | None, revision: str | None) -> PipelineRun:
        started, clock = datetime.now(timezone.utc), monotonic()
        entities: list[ParsedEntity] = []
        processed: list[str] = []
        errors: list[str] = []
        parse_errors = warnings = 0
        for file_path in paths:
            relative = file_path.relative_to(root).as_posix()
            try:
                text = file_path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError) as error:
                errors.append(f"{relative}: {self._error(error)}")
                continue
            if not text.strip():
                continue
            try:
                parsed = self.parser.parse(text)
            except Exception as error:  # One invalid file must not stop siblings.
                errors.append(f"{relative}: {self._error(error)}")
                continue
            entities.extend(parsed.entities)
            processed.append(relative)
            parse_errors += sum(issue.severity.lower() == "error" for issue in parsed.issues)
            warnings += sum(issue.severity.lower() == "warning" for issue in parsed.issues)
        return self._build_run(ParsedSQL(entities=tuple(entities), statement_count=len(entities)), root, started, clock, processed, parse_errors, warnings, errors, source_uri, revision)

    def _scan_text(self, text: str, path: Path, started: datetime, clock: float, **provenance) -> PipelineRun:
        try:
            parsed = self.parser.parse(text)
            return self._build_run(parsed, path, started, clock, (path.as_posix(),), sum(i.severity.lower() == "error" for i in parsed.issues), sum(i.severity.lower() == "warning" for i in parsed.issues), (), provenance.get("source_uri"), provenance.get("revision"))
        except Exception as error:  # Parser failures are represented in PipelineRun.
            return self._run(path, started, clock, status="failed", error_message=self._error(error), processed_files=(path.as_posix(),), source_uri=provenance.get("source_uri"), revision=provenance.get("revision"))

    def _build_run(self, parsed: ParsedSQL, path: Path, started: datetime, clock: float, processed: tuple[str, ...] | list[str], parse_errors: int, warnings: int, errors: tuple[str, ...] | list[str], source_uri: str | None, revision: str | None) -> PipelineRun:
        metrics = self.metrics_calculator.calculate(parsed)
        graph = self.dependency_graph_builder.build(parsed)
        objects = tuple(self.guardian_object_factory.from_parsed_entity(entity) for entity in parsed.entities)
        observations = tuple(self.observation_factory.from_guardian_object(obj, metrics=metrics, dependency_graph=graph, parsed=entity) for obj, entity in zip(objects, parsed.entities))
        error_message = "; ".join(errors) or None
        return self._run(path, started, clock, status="failed" if error_message else "completed", error_message=error_message, observations=observations, guardian_objects=objects, metrics=metrics, dependency_graph=graph, processed_files=tuple(processed), parse_error_count=parse_errors, warning_count=warnings, source_uri=source_uri, revision=revision)

    @staticmethod
    def _error(error: Exception) -> str:
        return f"{type(error).__name__}: {error}"

    @staticmethod
    def _run(path: Path, started: datetime, clock: float, **kwargs) -> PipelineRun:
        source_uri = kwargs.pop("source_uri", None)
        revision = kwargs.pop("revision", None)
        metadata = {"path": path.as_posix()}
        if source_uri is not None:
            metadata["source_uri"] = source_uri
        if revision is not None:
            metadata["revision"] = revision
        return PipelineRun(pipeline_name="sql_scanner", run_id=path.as_posix(), started_at=started, duration_seconds=max(0, int(monotonic() - clock)), metadata=metadata, **kwargs)


__all__ = ["SQLScanner"]
