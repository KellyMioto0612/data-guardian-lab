"""Structural similarity analysis for persistent SQL Guardian assets."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from src.monitor.scanners.sql_parser import ParsedEntity


@dataclass(frozen=True)
class GuardianDNA:
    """Non-reversible structural fingerprint for a parsed SQL asset."""

    object_id: str
    entity_type: str
    fingerprint: str
    features: frozenset[str]


@dataclass(frozen=True)
class SimilarityCandidate:
    """A review candidate, not an automatic duplicate decision."""

    left_object_id: str
    right_object_id: str
    score: float
    shared_feature_count: int


class GuardianDNAAnalyzer:
    """Compare SQL assets by structure while deliberately omitting SQL text."""

    _KEYWORDS = ("SELECT", "DISTINCT", "WHERE", "GROUP BY", "HAVING", "ORDER BY", "CASE", "UNION")

    def fingerprint(self, entity: ParsedEntity) -> GuardianDNA:
        object_id = entity.qualified_name or entity.entity_fingerprint_seed or "statement"
        features = self._features(entity)
        digest = hashlib.sha256("|".join(sorted(features)).encode()).hexdigest()
        return GuardianDNA(object_id, entity.entity_type, digest, frozenset(features))

    def find_similar(
        self, entities: tuple[ParsedEntity, ...] | list[ParsedEntity], *, threshold: float = 0.8
    ) -> tuple[SimilarityCandidate, ...]:
        """Return high-similarity candidates of the same persistent asset type."""
        dna = tuple(self.fingerprint(entity) for entity in entities)
        candidates: list[SimilarityCandidate] = []
        for index, left in enumerate(dna):
            for right in dna[index + 1 :]:
                if left.entity_type != right.entity_type or left.object_id == right.object_id:
                    continue
                shared = left.features & right.features
                union = left.features | right.features
                score = len(shared) / len(union) if union else 0.0
                if len(shared) >= 4 and score >= threshold:
                    candidates.append(
                        SimilarityCandidate(
                            left.object_id,
                            right.object_id,
                            round(score, 2),
                            len(shared),
                        )
                    )
        return tuple(sorted(candidates, key=lambda item: (-item.score, item.left_object_id)))

    def _features(self, entity: ParsedEntity) -> set[str]:
        normalized = (entity.normalized_sql or "").upper()
        features = {
            f"entity:{entity.entity_type.lower()}",
            f"statement:{entity.statement_type.upper()}",
            f"reads:{len(entity.tables_read)}",
            f"writes:{len(entity.tables_written)}",
            f"ctes:{len(entity.ctes)}",
            f"calls:{len(entity.called_procedures)}",
        }
        features.update(f"join:{join.join_type.upper()}" for join in entity.joins)
        features.update(
            f"keyword:{keyword.lower().replace(' ', '_')}"
            for keyword in self._KEYWORDS
            if re.search(rf"\b{keyword}\b", normalized)
        )
        return features


__all__ = ["GuardianDNA", "GuardianDNAAnalyzer", "SimilarityCandidate"]
