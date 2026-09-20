"""Transparent evidence-quality scoring.

This is deliberately *not* a model-produced number. A model asked for a
confidence will happily return 95 with no basis. Here the score is a weighted
sum of named components, each of which is stored alongside the result, so any
figure in the UI can be taken apart and argued with.

The output is an internal estimate of evidence quality — not a probability
that the claim is true.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import ConfidenceLevel, EpistemicStatus, Freshness, SourceReliability
from app.services import freshness as freshness_service

# How directly a source speaks for the company.
RELIABILITY_SCORE: dict[str, float] = {
    SourceReliability.FIRST_PARTY: 1.0,
    SourceReliability.PRESS: 0.8,
    SourceReliability.THIRD_PARTY: 0.6,
    SourceReliability.AGGREGATED: 0.4,
    SourceReliability.UNKNOWN: 0.35,
}

# An explicit statement outranks something we inferred from it.
DIRECTNESS_SCORE: dict[str, float] = {
    EpistemicStatus.KNOWN: 1.0,
    EpistemicStatus.INFERRED: 0.65,
    EpistemicStatus.POSSIBLE: 0.4,
    EpistemicStatus.UNKNOWN: 0.2,
}

WEIGHTS: dict[str, float] = {
    "source_quality": 0.30,
    "source_count": 0.20,
    "recency": 0.20,
    "directness": 0.20,
    "agreement": 0.10,
}

HIGH_THRESHOLD = 0.70
MEDIUM_THRESHOLD = 0.45

# A disputed claim can never be "high", whatever its other components say.
# Without this cap the agreement weight alone is too small to demote a claim
# backed by a strong, recent, first-party source.
CONTRADICTED_CEILING = HIGH_THRESHOLD - 0.01


@dataclass
class ConfidenceResult:
    score: float
    level: ConfidenceLevel
    components: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "level": str(self.level),
            "components": {key: round(value, 3) for key, value in self.components.items()},
            "weights": WEIGHTS,
            "notes": self.notes,
        }


def _level(score: float) -> ConfidenceLevel:
    if score >= HIGH_THRESHOLD:
        return ConfidenceLevel.HIGH
    if score >= MEDIUM_THRESHOLD:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _source_count_score(count: int) -> float:
    """Saturating: the second source adds a lot, the fifth adds little."""
    if count <= 0:
        return 0.0
    return min(1.0, 0.55 + 0.15 * (count - 1))


# A page with no publication date tells us when we fetched it, not when the
# event happened. Treating that as "recent" manufactures confidence, so the
# recency component is capped when the date is only a retrieval timestamp.
UNDATED_RECENCY_CEILING = 0.5


def _recency(freshness: str, basis: str | None) -> float:
    score_value = freshness_service.score(freshness)
    if basis and basis != "published_at":
        return min(score_value, UNDATED_RECENCY_CEILING)
    return score_value


def score_evidence(
    *,
    reliability: str,
    epistemic_status: str,
    freshness: str,
    corroborating_sources: int = 1,
    contradicted: bool = False,
    freshness_basis: str | None = None,
) -> ConfidenceResult:
    """Confidence in a single evidence item."""
    components = {
        "source_quality": RELIABILITY_SCORE.get(str(reliability), 0.35),
        "source_count": _source_count_score(corroborating_sources),
        "recency": _recency(freshness, freshness_basis),
        "directness": DIRECTNESS_SCORE.get(str(epistemic_status), 0.3),
        # One source cannot agree with itself; neutral until corroborated.
        "agreement": 0.5 if corroborating_sources <= 1 else 1.0,
    }
    notes: list[str] = []

    if contradicted:
        # A contradiction caps confidence rather than zeroing it: the claim
        # still exists, it is just disputed.
        components["agreement"] = 0.1
        notes.append("Another source contradicts this claim.")

    total = sum(components[key] * WEIGHTS[key] for key in WEIGHTS)
    if contradicted:
        total = min(total, CONTRADICTED_CEILING)

    if str(freshness) == Freshness.UNKNOWN:
        notes.append("No publication date was found, so recency is an estimate.")
    elif freshness_basis and freshness_basis != "published_at":
        notes.append(
            "The source carries no publication date; freshness reflects when the "
            "page was retrieved, so recency is discounted."
        )

    return ConfidenceResult(score=total, level=_level(total), components=components, notes=notes)


def aggregate(
    results: list[ConfidenceResult],
    *,
    distinct_sources: int,
    freshness: str,
    contradicted: bool = False,
    freshness_basis: str | None = None,
) -> ConfidenceResult:
    """Confidence in something derived from several evidence items.

    Uses the mean of the parts for quality and directness — a weak item drags
    the group down — while source count and recency are computed for the group
    as a whole.
    """
    if not results:
        return ConfidenceResult(score=0.0, level=ConfidenceLevel.LOW, components={}, notes=[])

    def mean(key: str) -> float:
        values = [item.components.get(key, 0.0) for item in results]
        return sum(values) / len(values)

    components = {
        "source_quality": mean("source_quality"),
        "source_count": _source_count_score(distinct_sources),
        "recency": _recency(freshness, freshness_basis),
        "directness": mean("directness"),
        "agreement": 1.0 if distinct_sources > 1 else 0.5,
    }
    notes: list[str] = []

    if contradicted:
        components["agreement"] = 0.1
        notes.append("Supporting evidence includes a contradiction.")
    if distinct_sources <= 1:
        notes.append("Supported by a single source only.")

    total = sum(components[key] * WEIGHTS[key] for key in WEIGHTS)
    if contradicted:
        total = min(total, CONTRADICTED_CEILING)
    return ConfidenceResult(score=total, level=_level(total), components=components, notes=notes)
