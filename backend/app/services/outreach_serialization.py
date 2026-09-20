"""Converts Phase 3 rows into API schemas."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Evidence, Outreach, OutreachVersion
from app.schemas.outreach import (
    ClaimEvidenceRef,
    OutreachClaimRead,
    OutreachRead,
    OutreachVersionRead,
)
from app.services import freshness as freshness_service


def outreach_to_schema(outreach: Outreach, *, now: datetime | None = None) -> OutreachRead:
    now = now or datetime.now(UTC)
    payload = OutreachRead.model_validate(outreach, from_attributes=True)

    company = getattr(outreach, "company", None)
    if company is not None:
        payload.company_name = company.name
        payload.company_domain = company.canonical_domain
        payload.company_industry = company.industry

    opportunity = getattr(outreach, "opportunity", None)
    if opportunity is not None:
        payload.opportunity_title = opportunity.title
        capability = getattr(opportunity, "capability", None)
        if capability is not None:
            payload.capability_name = capability.name

    campaign = getattr(outreach, "campaign", None)
    if campaign is not None:
        payload.campaign_name = campaign.name

    recipient = getattr(outreach, "decision_maker", None)
    if recipient is not None:
        payload.recipient_role = recipient.role

    if outreach.next_follow_up_at:
        due = (
            outreach.next_follow_up_at
            if outreach.next_follow_up_at.tzinfo
            else outreach.next_follow_up_at.replace(tzinfo=UTC)
        )
        payload.follow_up_due = due <= now

    return payload


async def version_to_schema(
    session: AsyncSession, version: OutreachVersion
) -> OutreachVersionRead:
    """Includes each claim's evidence, which is what the review sidebar shows."""
    evidence_ids: set[int] = set()
    for claim in version.claims:
        for link in claim.evidence_links:
            evidence_ids.add(link.evidence_id)

    evidence_by_id: dict[int, Evidence] = {}
    if evidence_ids:
        from sqlalchemy.orm import selectinload

        rows = await session.scalars(
            select(Evidence)
            .where(Evidence.id.in_(evidence_ids))
            .options(selectinload(Evidence.source))
        )
        evidence_by_id = {row.id: row for row in rows}

    claims: list[OutreachClaimRead] = []
    for claim in version.claims:
        refs: list[ClaimEvidenceRef] = []
        for link in claim.evidence_links:
            item = evidence_by_id.get(link.evidence_id)
            if item is None:
                # The evidence was deleted; say so rather than hiding it.
                refs.append(ClaimEvidenceRef(evidence_id=link.evidence_id))
                continue
            result = freshness_service.classify(item.published_at, item.observed_at)
            refs.append(
                ClaimEvidenceRef(
                    evidence_id=item.id,
                    claim=item.claim,
                    excerpt=item.excerpt,
                    source_url=item.source.url if item.source else None,
                    source_title=item.source.title if item.source else None,
                    published_at=item.published_at,
                    freshness=str(result.freshness),
                    freshness_basis=result.basis,
                )
            )
        claims.append(
            OutreachClaimRead(
                id=claim.id,
                text=claim.text,
                kind=claim.kind,
                requires_evidence=claim.requires_evidence,
                evidence=refs,
            )
        )

    payload = OutreachVersionRead.model_validate(version, from_attributes=True)
    payload.claims = claims
    return payload
