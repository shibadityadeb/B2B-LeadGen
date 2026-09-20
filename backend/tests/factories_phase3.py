"""Mock providers and builders for Phase 3 tests.

No real email is ever sent or drafted: the delivery provider here is a fake
that records calls in memory.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.errors import ProviderError
from app.models import Opportunity, OpportunityEvidence, SenderProfile, UbmCapability
from app.providers.outreach.base import (
    DraftMessage,
    DraftResult,
    OutreachDeliveryProvider,
    OutreachProviderStatus,
)
from app.services.fingerprints import opportunity_fingerprint
from tests.factories_phase2 import make_company, make_evidence, make_source  # noqa: F401


class FakeDeliveryProvider(OutreachDeliveryProvider):
    """Records drafts instead of contacting Gmail.

    Note there is no `send` method to fake — the interface has none.
    """

    name = "fake_gmail"

    def __init__(self, *, connected: bool = True, failing: bool = False):
        self._connected = connected
        self.failing = failing
        self.drafts: dict[str, DraftMessage] = {}
        self.created: list[DraftMessage] = []
        self.deleted: list[str] = []
        self._counter = 0

    @property
    def connected(self) -> bool:
        return self._connected

    async def create_draft(self, message: DraftMessage) -> DraftResult:
        if not self._connected:
            raise ProviderError("Gmail is not connected.", details={"needs_reauth": True})
        if self.failing:
            raise ProviderError("Gmail rejected the request.")
        self._counter += 1
        draft_id = f"draft-{self._counter}"
        self.drafts[draft_id] = message
        self.created.append(message)
        return DraftResult(
            draft_id=draft_id,
            url=f"https://mail.google.com/mail/u/0/#drafts?compose={draft_id}",
            thread_id=f"thread-{self._counter}",
        )

    async def get_draft(self, draft_id: str) -> DraftResult | None:
        if draft_id not in self.drafts:
            return None
        return DraftResult(draft_id=draft_id, url=f"https://mail.google.com/x/{draft_id}")

    async def update_draft(self, draft_id: str, message: DraftMessage) -> DraftResult:
        self.drafts[draft_id] = message
        return DraftResult(draft_id=draft_id)

    async def delete_draft(self, draft_id: str) -> bool:
        self.deleted.append(draft_id)
        return self.drafts.pop(draft_id, None) is not None

    async def status(self) -> OutreachProviderStatus:
        return OutreachProviderStatus(
            self.name, self._connected, "tester@example.com", "fake provider"
        )


async def make_capability(session, **overrides) -> UbmCapability:
    capability = UbmCapability(
        **{
            "slug": overrides.pop("slug", "on-ground-activations"),
            "name": "On-Ground Activations",
            "description": "Localised customer-facing activations that build awareness.",
            "category": "Experiential",
            "signal_types": ["geographic_expansion"],
            "keywords": [],
            "rationale_template": "{company} shows {signal_summary}. This may be relevant.",
            "weight": 1.0,
            "active": True,
            **overrides,
        }
    )
    session.add(capability)
    await session.commit()
    await session.refresh(capability)
    return capability


async def make_opportunity(
    session, company_id: int, capability_id: int, evidence_ids: list[int] | None = None, **overrides
) -> Opportunity:
    opportunity = Opportunity(
        **{
            "company_id": company_id,
            "capability_id": capability_id,
            "title": "Potential on-ground activations opportunity",
            "description": "Localised activations.",
            "why_relevant": "The company shows geographic expansion.",
            "confidence": 0.8,
            "confidence_level": "high",
            "freshness": "recent",
            "status": "candidate",
            "evidence_count": len(evidence_ids or []),
            "fingerprint": opportunity_fingerprint(company_id, capability_id),
            **overrides,
        }
    )
    session.add(opportunity)
    await session.commit()

    for evidence_id in evidence_ids or []:
        session.add(
            OpportunityEvidence(opportunity_id=opportunity.id, evidence_id=evidence_id)
        )
    await session.commit()
    await session.refresh(opportunity, ["evidence_links", "signal_links"])
    return opportunity


async def make_sender(session, **overrides) -> SenderProfile:
    profile = SenderProfile(
        **{
            "name": "Test Sender",
            "role": "Business Development",
            "company": "Upshot Brand Media",
            "email": "sender@example.com",
            "is_default": True,
            **overrides,
        }
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


async def make_person(session, company_id: int, **overrides):
    from app.models import DecisionMaker
    from app.models.enums import VerificationStatus
    from app.services.fingerprints import decision_maker_fingerprint

    name = overrides.pop("name", "Priya Nair")
    role = overrides.pop("role", "Head of Marketing")
    person = DecisionMaker(
        **{
            "company_id": company_id,
            "name": name,
            "role": role,
            "role_category": "marketing",
            "verification_status": VerificationStatus.PUBLIC_COMPANY_SOURCE,
            "confidence": 0.8,
            "confidence_level": "high",
            "fingerprint": decision_maker_fingerprint(company_id, name, role),
            **overrides,
        }
    )
    session.add(person)
    await session.commit()
    await session.refresh(person)
    return person


async def seeded_opportunity(session, *, with_person: bool = True, email: str | None = None):
    """A company with evidence, a capability, an opportunity and a recipient."""
    company = await make_company(session)
    source = await make_source(session, company.id)
    evidence = [
        await make_evidence(
            session,
            company.id,
            source.id,
            evidence_type="new_store",
            claim="Acme opened a store.",
            excerpt="Acme Retail opened two new showrooms in Bhopal this month.",
            published_at=datetime.now(UTC),
        ),
        await make_evidence(
            session,
            company.id,
            source.id,
            evidence_type="campaign",
            claim="Acme ran a campaign.",
            excerpt="Acme Retail launched a regional advertising campaign in March.",
            published_at=datetime.now(UTC),
        ),
    ]
    capability = await make_capability(session)
    opportunity = await make_opportunity(
        session, company.id, capability.id, [item.id for item in evidence]
    )
    await make_sender(session)
    person = (
        await make_person(session, company.id, email=email) if with_person else None
    )
    return company, opportunity, evidence, person
