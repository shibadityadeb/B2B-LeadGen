"""Matches observed signals to UBM capabilities.

The rule is a join, not a branch: a capability declares the signal types it
responds to, and a company exhibiting one of those signals produces a
*hypothesis*. Industry is never consulted.

Output wording is deliberately provisional. These are things worth looking
into, not established needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import UbmCapability
from app.models.enums import ConfidenceLevel, Freshness, OpportunityStatus
from app.services import confidence as confidence_service
from app.services import freshness as freshness_service
from app.services.signal_engine import DerivedSignal


@dataclass
class MatchedOpportunity:
    capability_id: int
    capability_name: str
    title: str
    description: str
    why_relevant: str
    signal_types: list[str]
    signal_ids: list[int] = field(default_factory=list)
    evidence_ids: list[int] = field(default_factory=list)
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    confidence_components: dict = field(default_factory=dict)
    freshness: Freshness = Freshness.UNKNOWN
    status: OpportunityStatus = OpportunityStatus.CANDIDATE
    evidence_count: int = 0


def _components_of(signal: DerivedSignal) -> dict[str, float]:
    """The signal's confidence breakdown, or a fallback derived from its score.

    A signal persisted without components (an older row, or a caller that did
    not populate them) would otherwise be read as all-zeros and drag the
    hypothesis to zero confidence, which is worse than approximating.
    """
    components = (signal.confidence_components or {}).get("components") or {}
    if components:
        return components
    return {key: signal.confidence for key in confidence_service.WEIGHTS}


def _signal_summary(signals: list[DerivedSignal]) -> str:
    """Plain-language list of what was observed, e.g.
    'geographic expansion and event activity'."""
    titles = [signal.title.lower() for signal in signals]
    if len(titles) == 1:
        return titles[0]
    if len(titles) == 2:
        return f"{titles[0]} and {titles[1]}"
    return f"{', '.join(titles[:-1])} and {titles[-1]}"


def _status(
    confidence_level: ConfidenceLevel, signal_count: int, distinct_sources: int
) -> OpportunityStatus:
    """A hypothesis is only 'supported' when independent sources agree.

    Requiring several signals alone is too weak: one press page can produce
    many signals at once, and a single self-reported page should not promote
    a hypothesis past 'candidate'.
    """
    if confidence_level == ConfidenceLevel.HIGH and signal_count >= 2 and distinct_sources >= 2:
        return OpportunityStatus.SUPPORTED
    if confidence_level == ConfidenceLevel.LOW:
        return OpportunityStatus.UNCERTAIN
    return OpportunityStatus.CANDIDATE


def match(
    signals: list[DerivedSignal],
    capabilities: list[UbmCapability],
    *,
    company_name: str,
    min_confidence: float = 0.0,
) -> list[MatchedOpportunity]:
    """Produce one hypothesis per capability whose declared signal types are present."""
    by_type: dict[str, DerivedSignal] = {signal.signal_type: signal for signal in signals}
    matches: list[MatchedOpportunity] = []

    for capability in capabilities:
        if not capability.active:
            continue

        relevant = [
            by_type[signal_type]
            for signal_type in (capability.signal_types or [])
            if signal_type in by_type
        ]
        if not relevant:
            continue

        # Strongest signals first, so the rationale leads with the best basis.
        relevant.sort(key=lambda signal: (signal.strength, signal.confidence), reverse=True)

        evidence_ids: list[int] = []
        for signal in relevant:
            for evidence_id in signal.evidence_ids:
                if evidence_id not in evidence_ids:
                    evidence_ids.append(evidence_id)

        group_freshness = freshness_service.best([signal.freshness for signal in relevant])
        # If no supporting signal rests on a genuinely dated source, the
        # hypothesis does not get full recency credit either.
        group_basis = (
            "published_at"
            if any(
                (signal.confidence_components or {}).get("components", {}).get("recency", 0) > 0.5
                for signal in relevant
            )
            else "observed_at"
        )

        parts = [
            confidence_service.ConfidenceResult(
                score=signal.confidence,
                level=ConfidenceLevel(signal.confidence_level),
                components=_components_of(signal),
            )
            for signal in relevant
        ]
        aggregated = confidence_service.aggregate(
            parts,
            distinct_sources=len(evidence_ids),
            freshness=str(group_freshness),
            freshness_basis=group_basis,
        )
        # A capability's own weight nudges ordering without inventing certainty.
        weighted = min(1.0, aggregated.score * (capability.weight or 1.0))

        summary = _signal_summary(relevant)
        template = capability.rationale_template or (
            "{company} shows {signal_summary}. This may make {capability} relevant."
        )
        why_relevant = template.format(
            company=company_name,
            signal_summary=summary,
            capability=capability.name,
        )

        level = confidence_service._level(weighted)
        if weighted < min_confidence:
            continue

        distinct_sources = max((signal.distinct_sources for signal in relevant), default=1)

        matches.append(
            MatchedOpportunity(
                capability_id=capability.id,
                capability_name=capability.name,
                title=f"Potential {capability.name.lower()} opportunity",
                description=capability.description,
                why_relevant=why_relevant,
                signal_types=[signal.signal_type for signal in relevant],
                evidence_ids=evidence_ids,
                confidence=weighted,
                confidence_level=level,
                confidence_components=aggregated.dict(),
                freshness=group_freshness,
                status=_status(level, len(relevant), distinct_sources),
                evidence_count=len(evidence_ids),
            )
        )

    matches.sort(key=lambda item: (item.confidence, item.evidence_count), reverse=True)
    return matches
