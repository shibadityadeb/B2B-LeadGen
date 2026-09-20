"""Derives business signals from stored evidence.

A signal is an aggregation, not a new assertion: it groups related evidence
items and reports what they collectively indicate, keeping every evidence id
so the reasoning can be walked backwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.models import Evidence
from app.models.enums import ConfidenceLevel, EpistemicStatus, Freshness
from app.services import confidence as confidence_service
from app.services import freshness as freshness_service
from app.services.evidence_taxonomy import SIGNAL_GROUPS, signal_type_for


@dataclass
class DerivedSignal:
    signal_type: str
    title: str
    description: str
    evidence_ids: list[int]
    strength: float
    freshness: Freshness
    confidence: float
    confidence_level: ConfidenceLevel
    confidence_components: dict
    latest_evidence_at: datetime | None
    evidence_count: int
    #: How many *different* sources back this signal. Corroboration across
    #: sources is the thing that distinguishes a fact from a self-report.
    distinct_sources: int = 1
    notes: list[str] = field(default_factory=list)


def _strength(evidence_items: list[Evidence], distinct_sources: int) -> float:
    """How pronounced the signal is: more evidence, from more sources, with
    firmer epistemic status, all push it up. Saturates at 1.0."""
    direct = sum(
        1 for item in evidence_items if item.epistemic_status == EpistemicStatus.KNOWN
    )
    volume = min(1.0, len(evidence_items) / 4)
    breadth = min(1.0, distinct_sources / 3)
    directness = direct / len(evidence_items) if evidence_items else 0.0
    return round(0.45 * volume + 0.3 * breadth + 0.25 * directness, 3)


def _describe(title: str, company_name: str, evidence_items: list[Evidence]) -> str:
    """A factual sentence about what was observed — no interpretation."""
    count = len(evidence_items)
    sources = len({item.source_id for item in evidence_items})
    plural = "observation" if count == 1 else "observations"
    source_text = "1 source" if sources == 1 else f"{sources} sources"
    return (
        f"{title} for {company_name}, based on {count} {plural} "
        f"across {source_text}."
    )


def derive_signals(
    evidence_items: list[Evidence],
    *,
    company_name: str,
    contradicted_evidence_ids: set[int] | None = None,
    now: datetime | None = None,
) -> list[DerivedSignal]:
    """Group evidence into signals, strongest first."""
    contradicted_evidence_ids = contradicted_evidence_ids or set()

    grouped: dict[str, list[Evidence]] = {}
    for item in evidence_items:
        signal_type = signal_type_for(item.evidence_type)
        if signal_type is None:
            continue  # identity facts and unmapped types are not signals
        grouped.setdefault(signal_type, []).append(item)

    signals: list[DerivedSignal] = []
    for signal_type, members in grouped.items():
        title = SIGNAL_GROUPS[signal_type][0]
        distinct_sources = len({item.source_id for item in members})

        freshness_results = [
            freshness_service.classify(item.published_at, item.observed_at, now=now)
            for item in members
        ]
        group_freshness = freshness_service.best(
            [result.freshness for result in freshness_results]
        )

        contradicted = any(item.id in contradicted_evidence_ids for item in members)

        parts = [
            confidence_service.score_evidence(
                reliability=item.source.source_reliability if item.source else "unknown",
                epistemic_status=item.epistemic_status,
                freshness=str(result.freshness),
                corroborating_sources=1,
                contradicted=item.id in contradicted_evidence_ids,
                freshness_basis=result.basis,
            )
            for item, result in zip(members, freshness_results, strict=True)
        ]
        # The group inherits the strongest basis available: if any member is
        # genuinely dated, the group is not treated as undated.
        group_basis = (
            "published_at"
            if any(result.basis == "published_at" for result in freshness_results)
            else "observed_at"
        )
        aggregated = confidence_service.aggregate(
            parts,
            distinct_sources=distinct_sources,
            freshness=str(group_freshness),
            contradicted=contradicted,
            freshness_basis=group_basis,
        )

        dated = [item.published_at for item in members if item.published_at]
        signals.append(
            DerivedSignal(
                signal_type=signal_type,
                title=title,
                description=_describe(title, company_name, members),
                evidence_ids=[item.id for item in members],
                strength=_strength(members, distinct_sources),
                freshness=group_freshness,
                confidence=aggregated.score,
                confidence_level=aggregated.level,
                confidence_components={
                    **aggregated.dict(),
                    "distinct_sources": distinct_sources,
                },
                latest_evidence_at=max(dated) if dated else None,
                evidence_count=len(members),
                distinct_sources=distinct_sources,
                notes=aggregated.notes,
            )
        )

    signals.sort(key=lambda signal: (signal.strength, signal.confidence), reverse=True)
    return signals
