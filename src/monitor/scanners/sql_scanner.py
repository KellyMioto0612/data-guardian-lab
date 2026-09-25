"""Orchestrate SQL parsing, analysis, and domain adaptation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from src.analyzers.asset_classifier import AssetClassifier
from src.analyzers.dependency_graph import DependencyGraphBuilder
from src.analyzers.guardian_dna import GuardianDNAAnalyzer
from src.analyzers.lineage import LineageAnalyzer
from src.analyzers.sql_evidence import SQLEvidenceAnalyzer
from src.analyzers.sql_metrics_calculator import SQLMetricsCalculator
from src.analyzers.tdi_engine import calculate_tdi
from src.factories.guardian_object_factory import GuardianObjectFactory
from src.factories.observation_factory import ObservationFactory
from src.models.pipeline_run import PipelineRun
from src.monitor.scanners.sql_parser import ParsedEntity, ParsedSQL, SQLParser
from src.monitor.scanners.tsql_preprocessor import TSQLPreprocessor

_SUPPORTED_SUFFIXES = frozenset({".sql", ".ddl", ".prc", ".vw"})


class SQLScanner:
    """Run the Foundation components over SQL files deterministically."""

    def __init__(self, allowed_root: str | Path | None = None) -> None:
        self.allowed_root = (
            Path(allowed_root) if allowed_root is not None else Path(__file__).resolve().parents[3]
        ).resolve()
        self.parser = SQLParser()
        self.metrics_calculator = SQLMetricsCalculator()
        self.asset_classifier = AssetClassifier()
        self.evidence_analyzer = SQLEvidenceAnalyzer()
        self.dna_analyzer = GuardianDNAAnalyzer()
        self.lineage_analyzer = LineageAnalyzer()
        self.dependency_graph_builder = DependencyGraphBuilder()
        self.guardian_object_factory = GuardianObjectFactory()
        self.observation_factory = ObservationFactory()
        self.preprocessor = TSQLPreprocessor()

    def scan_file(
        self,
        path: str | Path,
        *,
        source_uri: str | None = None,
        revision: str | None = None,
    ) -> PipelineRun:
        """Scan one UTF-8 file, recording failures in the returned run."""
        file_path = self._resolve_allowed(path)
        started, clock = datetime.now(UTC), monotonic()
        try:
            text = file_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            return self._run(
                file_path,
                started,
                clock,
                status="failed",
                error_message=self._error(error),
                processed_files=(file_path.as_posix(),),
                source_uri=source_uri,
                revision=revision,
            )
        if not text.strip():
            return self._run(
                file_path,
                started,
                clock,
                status="ignored",
                processed_files=(),
                source_uri=source_uri,
                revision=revision,
            )
        return self._scan_text(
            text, file_path, started, clock, source_uri=source_uri, revision=revision
        )

    def scan_directory(
        self, path: str | Path, *, source_uri: str | None = None, revision: str | None = None
    ) -> PipelineRun:
        """Recursively scan supported files in stable relative-path order."""
        root = self._resolve_allowed(path)
        if not root.is_dir():
            raise ValueError(f"scan directory is not a directory: {root}")
        files = sorted(
            (
                item
                for item in root.rglob("*")
                if item.is_file()
                and item.suffix.lower() in _SUPPORTED_SUFFIXES
                and self._is_allowed(item)
            ),
            key=lambda item: item.relative_to(root).as_posix(),
        )
        return self._scan_paths(files, root, source_uri=source_uri, revision=revision)

    def scan_repository(
        self, path: str | Path, *, source_uri: str | None = None, revision: str | None = None
    ) -> PipelineRun:
        """Scan a repository directory through :meth:`scan_directory`."""
        return self.scan_directory(path, source_uri=source_uri, revision=revision)

    def _scan_paths(
        self, paths: Iterable[Path], root: Path, *, source_uri: str | None, revision: str | None
    ) -> PipelineRun:
        started, clock = datetime.now(UTC), monotonic()
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
                processed_text = self.preprocessor.process(text)
                parsed = self.parser.parse(processed_text)
            except Exception as error:
                errors.append(f"{relative}: {self._error(error)}")
                continue
            entities.extend(parsed.entities)
            processed.append(relative)
            parse_errors += sum(issue.severity.lower() == "error" for issue in parsed.issues)
            warnings += sum(issue.severity.lower() == "warning" for issue in parsed.issues)
        return self._build_run(
            ParsedSQL(entities=tuple(entities), statement_count=len(entities)),
            root,
            started,
            clock,
            processed,
            parse_errors,
            warnings,
            errors,
            source_uri,
            revision,
        )

    def _scan_text(
        self, text: str, path: Path, started: datetime, clock: float, **provenance
    ) -> PipelineRun:
        try:
            processed_text = self.preprocessor.process(text)
            parsed = self.parser.parse(processed_text)
            return self._build_run(
                parsed,
                path,
                started,
                clock,
                (path.as_posix(),),
                sum(i.severity.lower() == "error" for i in parsed.issues),
                sum(i.severity.lower() == "warning" for i in parsed.issues),
                (),
                provenance.get("source_uri"),
                provenance.get("revision"),
            )
        except Exception as error:  # Parser failures are represented in PipelineRun.
            return self._run(
                path,
                started,
                clock,
                status="failed",
                error_message=self._error(error),
                processed_files=(path.as_posix(),),
                source_uri=provenance.get("source_uri"),
                revision=provenance.get("revision"),
            )

    def _build_run(
        self,
        parsed: ParsedSQL,
        path: Path,
        started: datetime,
        clock: float,
        processed: tuple[str, ...] | list[str],
        parse_errors: int,
        warnings: int,
        errors: tuple[str, ...] | list[str],
        source_uri: str | None,
        revision: str | None,
    ) -> PipelineRun:
        metrics = self.metrics_calculator.calculate(parsed)
        graph = self.dependency_graph_builder.build(parsed)
        asset_entities: list[ParsedEntity] = []
        evidence = []
        classifications: dict[str, int] = {}
        for entity in parsed.entities:
            classification = self.asset_classifier.classify(entity)
            category = classification.category.value
            classifications[category] = classifications.get(category, 0) + 1
            entity_evidence = self.evidence_analyzer.analyze(entity)
            evidence.extend(entity_evidence)
            if classification.include_in_knowledge_graph:
                debt = calculate_tdi(entity_evidence)
                metadata = {
                    **dict(entity.metadata),
                    "evidence": tuple(
                        {
                            "evidence_id": item.evidence_id,
                            "rule_id": item.rule_id,
                            "severity": item.severity.value,
                            "summary": item.summary,
                            "line_start": item.line_start,
                        }
                        for item in entity_evidence
                    ),
                    "technical_debt": {
                        "score": debt.score,
                        "classification": debt.classification.value,
                        "evidence_ids": debt.evidence_ids,
                    },
                }
                asset_entities.append(replace(entity, metadata=metadata))
        similarities = self.dna_analyzer.find_similar(asset_entities)
        candidates_by_object: dict[str, list[dict[str, object]]] = {}
        for candidate in similarities:
            candidates_by_object.setdefault(candidate.left_object_id, []).append(
                {
                    "object_id": candidate.right_object_id,
                    "score": candidate.score,
                    "shared_feature_count": candidate.shared_feature_count,
                }
            )
            candidates_by_object.setdefault(candidate.right_object_id, []).append(
                {
                    "object_id": candidate.left_object_id,
                    "score": candidate.score,
                    "shared_feature_count": candidate.shared_feature_count,
                }
            )
        asset_entities = [
            replace(
                entity,
                metadata={
                    **dict(entity.metadata),
                    "similarity_candidates": tuple(
                        candidates_by_object.get(entity.qualified_name or entity.name or "", ())
                    ),
                },
            )
            for entity in asset_entities
        ]
        asset_entities = [
            replace(
                entity,
                metadata={
                    **dict(entity.metadata),
                    "lineage": self._lineage_metadata(
                        graph, entity.qualified_name or entity.name or ""
                    ),
                },
            )
            for entity in asset_entities
        ]
        objects = tuple(
            self.guardian_object_factory.from_parsed_entity(entity) for entity in asset_entities
        )
        observations = tuple(
            self.observation_factory.from_guardian_object(
                obj, metrics=metrics, dependency_graph=graph, parsed=entity
            )
            for obj, entity in zip(objects, asset_entities)
        )
        error_message = "; ".join(errors) or None
        return self._run(
            path,
            started,
            clock,
            status="failed" if error_message else "completed",
            error_message=error_message,
            observations=observations,
            guardian_objects=objects,
            evidence=tuple(evidence),
            metrics=metrics,
            dependency_graph=graph,
            processed_files=tuple(processed),
            parse_error_count=parse_errors,
            warning_count=warnings,
            metadata={
                "asset_classification_counts": classifications,
                "evidence_count": len(evidence),
                "similarity_candidate_count": len(similarities),
                "lineage_asset_count": len(asset_entities),
            },
            source_uri=source_uri,
            revision=revision,
        )

    @staticmethod
    def _error(error: Exception) -> str:
        return f"{type(error).__name__}: SQL content withheld"

    def _resolve_allowed(self, path: str | Path) -> Path:
        candidate = Path(path).resolve()
        if not self._is_allowed(candidate):
            raise ValueError(f"scan path is outside the allowed root: {candidate}")
        return candidate

    def _is_allowed(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.allowed_root)
        except ValueError:
            return False
        return True

    def _lineage_metadata(self, graph, identifier: str) -> dict[str, object]:
        summary = self.lineage_analyzer.summarize(graph, identifier)
        return {
            "upstream": summary.upstream,
            "downstream": summary.downstream,
            "max_upstream_depth": summary.max_upstream_depth,
            "max_downstream_depth": summary.max_downstream_depth,
            "participates_in_cycle": summary.participates_in_cycle,
            "impact_score": summary.impact_score,
        }

    @staticmethod
    def _run(path: Path, started: datetime, clock: float, **kwargs) -> PipelineRun:
        source_uri = kwargs.pop("source_uri", None)
        revision = kwargs.pop("revision", None)
        metadata = {"path": path.as_posix(), **dict(kwargs.pop("metadata", {}))}
        if source_uri is not None:
            metadata["source_uri"] = source_uri
        if revision is not None:
            metadata["revision"] = revision
        return PipelineRun(
            pipeline_name="sql_scanner",
            run_id=path.as_posix(),
            started_at=started,
            duration_seconds=max(0, int(monotonic() - clock)),
            metadata=metadata,
            **kwargs,
        )


__all__ = ["SQLScanner"]
