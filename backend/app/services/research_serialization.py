"""Converts stored Phase 2 rows into API schemas.

Freshness is computed here rather than stored, so changing the configured
thresholds re-classifies existing evidence without a migration.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models import DecisionMaker, Evidence, Opportunity, ResearchRun, Signal
from app.schemas.research import (
    DecisionMakerRead,
    EvidenceRead,
    EvidenceSourceRef,
    OpportunityRead,
    ResearchRunRead,
    SignalRead,
)
from app.services import freshness as freshness_service


def evidence_to_schema(item: Evidence, *, now: datetime | None = None) -> EvidenceRead:
    now = now or datetime.now(UTC)
    result = freshness_service.classify(item.published_at, item.observed_at, now=now)
    payload = EvidenceRead.model_validate(item, from_attributes=True)
    payload.freshness = str(result.freshness)
    payload.age_days = result.age_days
    payload.freshness_basis = result.basis
    payload.source = (
        EvidenceSourceRef(
            id=item.source.id,
            url=item.source.url,
            title=item.source.title,
            type=item.source.source_type,
            reliability=item.source.source_reliability,
        )
        if item.source
        else None
    )
    return payload


def signal_to_schema(signal: Signal) -> SignalRead:
    payload = SignalRead.model_validate(signal, from_attributes=True)
    payload.evidence_ids = [link.evidence_id for link in signal.evidence_links]
    return payload


def opportunity_to_schema(opportunity: Opportunity) -> OpportunityRead:
    payload = OpportunityRead.model_validate(opportunity, from_attributes=True)
    payload.capability_name = opportunity.capability.name if opportunity.capability else None
    payload.capability_category = (
        opportunity.capability.category if opportunity.capability else None
    )
    payload.evidence_ids = [link.evidence_id for link in opportunity.evidence_links]
    payload.signal_ids = [link.signal_id for link in opportunity.signal_links]
    return payload


def decision_maker_to_schema(person: DecisionMaker) -> DecisionMakerRead:
    payload = DecisionMakerRead.model_validate(person, from_attributes=True)
    payload.source_url = person.source.url if person.source else person.profile_url
    return payload


def run_to_schema(run: ResearchRun) -> ResearchRunRead:
    payload = ResearchRunRead.model_validate(run, from_attributes=True)
    company = getattr(run, "company", None)
    if company is not None:
        payload.company_name = company.name
        payload.company_domain = company.canonical_domain
    return payload
