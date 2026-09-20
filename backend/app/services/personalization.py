"""Selects what an outreach message should actually say.

The rule this module exists to enforce: a personalization point may only be
built from a stored evidence row. It never paraphrases from memory, never
invents a company event and never asserts anything that is not already in the
database with a source URL behind it.

It deliberately selects **one or two strong points** rather than everything
available — an email stuffed with facts reads like a mail merge.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from app.models import Company, DecisionMaker, Evidence, Opportunity, Signal, UbmCapability
from app.models.enums import EpistemicStatus, ObservationState
from app.services import freshness as freshness_service

# Evidence types that read naturally as "something the company recently did".
# Ordered by how concrete they are to a reader; industry never appears.
_ANGLE_PRIORITY: tuple[str, ...] = (
    "new_store",
    "geographic_expansion",
    "new_location",
    "new_market",
    "product_launch",
    "service_launch",
    "event_organization",
    "event_participation",
    "sponsorship",
    "campaign",
    "partnership",
    "funding",
    "marketing_hiring",
    "hiring",
    "community_activity",
    "digital_activity",
    "award",
)

_WHITESPACE = re.compile(r"\s+")


@dataclass
class PersonalizationPoint:
    """One thing the email may refer to, and the evidence that allows it."""

    #: Short neutral description, e.g. "opening a new store or showroom".
    observation: str
    #: Verbatim source text, shown in the review UI for verification.
    excerpt: str
    evidence_ids: list[int]
    evidence_type: str
    source_url: str | None
    published_at: str | None
    freshness: str
    freshness_basis: str
    epistemic_status: str

    def dict(self) -> dict:
        return asdict(self)


@dataclass
class PersonalizationData:
    recipient: dict
    company_reference: dict | None
    business_signal: dict | None
    relevant_ubm_capability: dict
    conversation_angle: str
    points: list[PersonalizationPoint] = field(default_factory=list)
    #: Things the writer must not assert, surfaced to the reviewer.
    uncertainties: list[str] = field(default_factory=list)

    def dict(self) -> dict:
        return {
            "recipient": self.recipient,
            "company_reference": self.company_reference,
            "business_signal": self.business_signal,
            "relevant_ubm_capability": self.relevant_ubm_capability,
            "conversation_angle": self.conversation_angle,
            "points": [point.dict() for point in self.points],
            "uncertainties": self.uncertainties,
        }

    @property
    def evidence_ids(self) -> list[int]:
        ids: list[int] = []
        for point in self.points:
            for evidence_id in point.evidence_ids:
                if evidence_id not in ids:
                    ids.append(evidence_id)
        return ids


# How each evidence type is described in plain language. This is wording, not
# business logic: the *fact* comes from the excerpt, this only phrases it.
_OBSERVATION_PHRASING: dict[str, str] = {
    "new_store": "new store opening",
    "new_location": "new location",
    "geographic_expansion": "expansion into a new area",
    "new_market": "move into a new market",
    "product_launch": "recent product launch",
    "service_launch": "recent service launch",
    "event_organization": "recent event",
    "event_participation": "presence at a recent exhibition",
    "sponsorship": "recent sponsorship",
    "campaign": "recent campaign",
    "partnership": "new partnership",
    "acquisition": "recent acquisition",
    "funding": "recent funding round",
    "investment": "announced investment",
    "marketing_hiring": "hiring on the marketing side",
    "hiring": "current hiring",
    "community_activity": "community work",
    "digital_activity": "digital and e-commerce activity",
    "content_activity": "content publishing",
    "customer_growth": "customer growth",
    "award": "recent recognition",
    "leadership_change": "recent leadership change",
    "seasonal_activity": "seasonal activity",
    "press_activity": "recent press coverage",
    "company_identity": "company background published on the site",
}


# Company names inherited from discovery are sometimes listicle titles
# ("25 Best Jewellery Shops in Indore"). Addressing a real person with that
# would be obviously machine-generated, so it is trimmed for display. The
# user can still edit the subject and body afterwards.
_LISTICLE_PREFIX = re.compile(r"^\s*(?:top\s+)?\d+\s+(?:best\s+)?", re.IGNORECASE)
_LISTICLE_SUFFIX = re.compile(
    r"\s+(?:shops?|stores?|showrooms?|dealers?|manufacturers?|companies|brands?|"
    r"jewellers?|retailers?|suppliers?)\s+in\s+[A-Z][\w\s,]*$",
    re.IGNORECASE,
)
_TRAILING_LOCATION = re.compile(r"\s+in\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?\s*$")
#: Words that are a category, not a company.
_GENERIC_NAME_WORDS = {
    "jewellery", "jewelry", "retail", "company", "companies", "brands",
    "stores", "shops", "services", "solutions", "group",
}


def email_display_name(company: Company) -> str:
    """A company name safe to address in an email.

    Falls back to the registrable domain when trimming leaves nothing
    recognisable — a domain reads better than a listicle headline.
    """
    def from_domain() -> str:
        label = company.canonical_domain.split(".", 1)[0].replace("-", " ")
        return " ".join(word.capitalize() for word in label.split())

    name = _clean(company.name)

    # A title that begins with a count ("25 Best Jewellery Shops…") is a
    # listicle headline and never contains the company's own name, so
    # trimming it would leave a generic word. Use the domain instead.
    if _LISTICLE_PREFIX.match(name):
        return from_domain()

    name = _LISTICLE_SUFFIX.sub("", name)
    name = _TRAILING_LOCATION.sub("", name).strip(" -–—,|")

    # A single generic word left over is not a usable name either.
    if len(name) < 3 or name.lower() in _GENERIC_NAME_WORDS:
        return from_domain()
    return name


def _phrase(evidence_type: str) -> str:
    return _OBSERVATION_PHRASING.get(evidence_type, "recent activity")


def _clean(value: str | None) -> str:
    return _WHITESPACE.sub(" ", (value or "").strip())


def _rank(item: Evidence, now: datetime) -> tuple:
    """Order evidence by how usable it is in an email.

    Preference order: still-present over stale, explicit over hedged, priority
    type, dated over undated, then confidence.
    """
    result = freshness_service.classify(item.published_at, item.observed_at, now=now)
    try:
        type_rank = _ANGLE_PRIORITY.index(item.evidence_type)
    except ValueError:
        type_rank = len(_ANGLE_PRIORITY)

    return (
        item.observation_state == ObservationState.NOT_FOUND,  # False sorts first
        item.epistemic_status != EpistemicStatus.KNOWN,
        type_rank,
        result.basis != "published_at",
        -(item.confidence or 0.0),
    )


def build_personalization(
    *,
    company: Company,
    opportunity: Opportunity,
    capability: UbmCapability,
    evidence: list[Evidence],
    signals: list[Signal],
    recipient: DecisionMaker | None,
    max_points: int = 2,
    now: datetime | None = None,
) -> PersonalizationData:
    """Choose the one or two observations this email will be built on."""
    now = now or datetime.now(UTC)

    usable = [
        item
        for item in evidence
        if item.excerpt
        # A claim we can no longer see on the web should not be asserted.
        and item.observation_state != ObservationState.NOT_FOUND
        # Identity facts describe the company, not a reason to write today.
        and item.evidence_type != "company_identity"
    ]
    usable.sort(key=lambda item: _rank(item, now))

    points: list[PersonalizationPoint] = []
    used_types: set[str] = set()
    for item in usable:
        # Two points about the same kind of event read repetitively.
        if item.evidence_type in used_types:
            continue
        result = freshness_service.classify(item.published_at, item.observed_at, now=now)
        points.append(
            PersonalizationPoint(
                observation=_phrase(item.evidence_type),
                excerpt=_clean(item.excerpt),
                evidence_ids=[item.id],
                evidence_type=item.evidence_type,
                source_url=item.source.url if item.source else None,
                published_at=item.published_at.isoformat() if item.published_at else None,
                freshness=str(result.freshness),
                freshness_basis=result.basis,
                epistemic_status=item.epistemic_status,
            )
        )
        used_types.add(item.evidence_type)
        if len(points) >= max_points:
            break

    # The recipient is reported exactly as stored: an unnamed role stays
    # unnamed, because the greeting must never invent a person.
    recipient_data = {
        "decision_maker_id": recipient.id if recipient else None,
        "name": recipient.name if recipient else None,
        "role": recipient.role if recipient else None,
        "role_category": recipient.role_category if recipient else None,
        "email": recipient.email if recipient else None,
        "verification_status": recipient.verification_status if recipient else None,
        "source_url": (
            recipient.source.url if recipient and recipient.source else None
        ),
    }

    strongest_signal = max(signals, key=lambda s: (s.strength, s.confidence), default=None)

    uncertainties: list[str] = []
    if not points:
        uncertainties.append(
            "No usable public evidence was found for this company, so the message "
            "cannot be personalized with a specific observation."
        )
    if recipient is None:
        uncertainties.append("No decision maker has been selected for this outreach.")
    elif not recipient.name:
        uncertainties.append(
            "The recipient's name is not published, so the greeting addresses the role."
        )
    if recipient is not None and not recipient.email:
        uncertainties.append(
            "No public email address was found for this person. One must be supplied "
            "manually before a Gmail draft can be created."
        )
    for point in points:
        if point.freshness_basis != "published_at":
            uncertainties.append(
                f"The source for “{point.observation}” carries no publication date, so "
                "its recency is estimated from when the page was retrieved."
            )
        if point.epistemic_status != EpistemicStatus.KNOWN:
            uncertainties.append(
                f"“{point.observation}” is described as a plan or intention rather than "
                "a completed event."
            )

    angle = _conversation_angle(points, capability, opportunity)

    return PersonalizationData(
        recipient=recipient_data,
        company_reference=points[0].dict() if points else None,
        business_signal=(
            {
                "signal_id": strongest_signal.id,
                "signal_type": strongest_signal.signal_type,
                "title": strongest_signal.title,
                "freshness": strongest_signal.freshness,
                "evidence_ids": [link.evidence_id for link in strongest_signal.evidence_links],
            }
            if strongest_signal
            else None
        ),
        relevant_ubm_capability={
            "id": capability.id,
            "name": capability.name,
            "category": capability.category,
            "description": capability.description,
        },
        conversation_angle=angle,
        points=points,
        uncertainties=list(dict.fromkeys(uncertainties)),
    )


def _conversation_angle(
    points: list[PersonalizationPoint], capability: UbmCapability, opportunity: Opportunity
) -> str:
    """A one-line statement of why this message is being written.

    Phrased provisionally — it is a reason to ask a question, not a diagnosis.
    """
    if not points:
        return (
            f"No specific public observation is available; {capability.name} is suggested "
            "only by the opportunity hypothesis."
        )
    lead = points[0].observation
    if len(points) > 1:
        return (
            f"{lead.capitalize()} and {points[1].observation} suggest a moment where "
            f"{capability.name.lower()} could be worth a conversation."
        )
    return (
        f"{lead.capitalize()} suggests a moment where {capability.name.lower()} could be "
        "worth a conversation."
    )
