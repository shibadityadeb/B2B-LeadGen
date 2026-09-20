"""Builds the structured company intelligence profile and renders it.

Both are deterministic. The brief is a rendering of stored rows — if a line
appears in it, a database row and a source URL stand behind it. Nothing is
generated prose.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, ResearchRun
from app.models.enums import (
    EvidenceType,
    ObservationState,
    RetrievalStatus,
    SourceReliability,
)
from app.repositories.research import (
    ContradictionRepository,
    DecisionMakerRepository,
    EvidenceRepository,
    OpportunityRepository,
    ResearchSourceRepository,
    SignalRepository,
)
from app.services import freshness as freshness_service
from app.services.about_summary import build_about
from app.services.personalization import company_tokens

# Which signal groups feed which section of the profile.
_PROFILE_SECTIONS: dict[str, tuple[str, ...]] = {
    "growth_signals": ("growth_investment", "geographic_expansion"),
    "marketing_signals": ("marketing_activity", "digital_activity", "marketing_hiring"),
    "event_signals": ("event_activity", "sponsorship_activity"),
    "expansion_signals": ("geographic_expansion",),
    "hiring_signals": ("hiring_activity", "marketing_hiring"),
    "partnership_signals": ("partnership_activity",),
}


def _signal_dict(signal) -> dict:
    return {
        "id": signal.id,
        "type": signal.signal_type,
        "title": signal.title,
        "description": signal.description,
        "strength": signal.strength,
        "freshness": signal.freshness,
        "confidence": round(signal.confidence, 3),
        "confidence_level": signal.confidence_level,
        "evidence_count": signal.evidence_count,
        "evidence_ids": [link.evidence_id for link in signal.evidence_links],
        "latest_evidence_at": (
            signal.latest_evidence_at.isoformat() if signal.latest_evidence_at else None
        ),
    }


def _evidence_dict(item, *, now: datetime) -> dict:
    result = freshness_service.classify(item.published_at, item.observed_at, now=now)
    return {
        "id": item.id,
        "claim": item.claim,
        "excerpt": item.excerpt,
        "evidence_type": item.evidence_type,
        "epistemic_status": item.epistemic_status,
        "confidence": round(item.confidence, 3),
        "confidence_level": item.confidence_level,
        "freshness": str(result.freshness),
        "age_days": result.age_days,
        "freshness_basis": result.basis,
        "observation_state": item.observation_state,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "observed_at": item.observed_at.isoformat() if item.observed_at else None,
        "source": {
            "id": item.source.id,
            "url": item.source.url,
            "title": item.source.title,
            "type": item.source.source_type,
            "reliability": item.source.source_reliability,
        }
        if item.source
        else None,
    }


async def build_profile(session: AsyncSession, company: Company, run: ResearchRun) -> dict:
    """Assemble the structured intelligence object from stored rows."""
    now = datetime.now(UTC)

    evidence_items = await EvidenceRepository(session).list_for_company(company.id)
    signals = await SignalRepository(session).list_for_company(company.id)
    opportunities = await OpportunityRepository(session).list_for_company(company.id)
    people = await DecisionMakerRepository(session).list_for_company(company.id)
    conflicts = await ContradictionRepository(session).list_for_company(company.id)
    sources = await ResearchSourceRepository(session).list_for_company(company.id)

    active_evidence = [
        item for item in evidence_items if item.observation_state != ObservationState.NOT_FOUND
    ]

    # Identity facts are reported separately from business events.
    identity: dict = {}
    for item in active_evidence:
        value = item.normalized_value or {}
        attribute = value.get("attribute")
        if attribute and value.get("value") is not None and attribute not in identity:
            identity[attribute] = {
                "value": value["value"],
                "evidence_id": item.id,
                "source_url": item.source.url if item.source else None,
            }

    # A short description of the business, in the company's own words, taken
    # only from pages they published themselves.
    own_pages = [
        (source.url, source.title, source.content)
        for source in sources
        if source.content and source.source_reliability == SourceReliability.FIRST_PARTY
    ]
    about_lines = build_about(
        own_pages, company_name=company.name, tokens=company_tokens(company)
    )

    signal_dicts = [_signal_dict(signal) for signal in signals]
    by_type = {signal["type"]: signal for signal in signal_dicts}

    # "Recent activity" is the freshest directly-observed business events.
    recent = sorted(
        (
            item
            for item in active_evidence
            if item.evidence_type != EvidenceType.COMPANY_IDENTITY
        ),
        key=lambda item: (item.published_at or datetime.min.replace(tzinfo=UTC)),
        reverse=True,
    )[:12]

    uncertainties: list[str] = []
    for conflict in conflicts:
        uncertainties.append(conflict.explanation or f"Conflicting information about {conflict.subject}.")
    undated = sum(1 for item in active_evidence if not item.published_at)
    if undated:
        uncertainties.append(
            f"{undated} of {len(active_evidence)} observations carry no publication date, "
            "so their age is estimated from when the page was retrieved."
        )
    if not any(person.name for person in people):
        uncertainties.append(
            "No individual was named on the public pages retrieved. Roles are reported "
            "without names rather than guessed."
        )
    for note in (run.errors or []):
        if note.get("stage") == "llm_uncertainty" and note.get("message"):
            uncertainties.append(note["message"])

    return {
        "generated_at": now.isoformat(),
        "research_run_id": run.id,
        "company": {
            "id": company.id,
            "name": company.name,
            "industry": company.industry,
            "location": company.location,
            "country": company.country,
            "website": company.website_url,
            "domain": company.canonical_domain,
            "description": company.description,
            "identity_facts": identity,
            # Verbatim sentences from their own site describing what they do.
            "about": [line.dict() for line in about_lines],
        },
        "recent_activity": [_evidence_dict(item, now=now) for item in recent],
        "growth_signals": [by_type[t] for t in _PROFILE_SECTIONS["growth_signals"] if t in by_type],
        "marketing_signals": [
            by_type[t] for t in _PROFILE_SECTIONS["marketing_signals"] if t in by_type
        ],
        "event_signals": [by_type[t] for t in _PROFILE_SECTIONS["event_signals"] if t in by_type],
        "expansion_signals": [
            by_type[t] for t in _PROFILE_SECTIONS["expansion_signals"] if t in by_type
        ],
        "hiring_signals": [by_type[t] for t in _PROFILE_SECTIONS["hiring_signals"] if t in by_type],
        "partnership_signals": [
            by_type[t] for t in _PROFILE_SECTIONS["partnership_signals"] if t in by_type
        ],
        "all_signals": signal_dicts,
        "opportunities": [
            {
                "id": item.id,
                "title": item.title,
                "capability": item.capability.name if item.capability else None,
                "capability_id": item.capability_id,
                "why_relevant": item.why_relevant,
                "confidence_level": item.confidence_level,
                "confidence": round(item.confidence, 3),
                "freshness": item.freshness,
                "status": item.status,
                "evidence_count": item.evidence_count,
                "evidence_ids": [link.evidence_id for link in item.evidence_links],
            }
            for item in opportunities
        ],
        "decision_makers": [
            {
                "id": person.id,
                "name": person.name,
                "role": person.role,
                "role_category": person.role_category,
                "email": person.email,
                "verification_status": person.verification_status,
                "confidence_level": person.confidence_level,
                "source_url": person.source.url if person.source else person.profile_url,
            }
            for person in people
        ],
        "evidence": [_evidence_dict(item, now=now) for item in active_evidence],
        "contradictions": [
            {
                "id": conflict.id,
                "subject": conflict.subject,
                "status": conflict.status,
                "explanation": conflict.explanation,
                "evidence_a_id": conflict.evidence_a_id,
                "evidence_b_id": conflict.evidence_b_id,
            }
            for conflict in conflicts
        ],
        "uncertainties": uncertainties,
        "sources": [
            {
                "id": source.id,
                "url": source.url,
                "title": source.title,
                "type": source.source_type,
                "reliability": source.source_reliability,
                "retrieval_status": source.retrieval_status,
                "published_at": source.published_at.isoformat() if source.published_at else None,
            }
            for source in sources
            if source.retrieval_status == RetrievalStatus.RETRIEVED
        ],
    }


def _bullet(text: str) -> str:
    return f"• {text}"


def render_brief(profile: dict) -> str:
    """Render the profile as Markdown. Pure formatting, no new claims."""
    company = profile["company"]
    lines: list[str] = []

    lines.append(f"# {company['name']}")
    meta = [
        f"**Industry:** {company['industry'] or 'Unknown'}",
        f"**Location:** {company['location'] or 'Unknown'}",
        f"**Website:** {company['website']}",
    ]
    lines.append("  \n".join(meta))
    lines.append("")

    # --- about ---
    lines.append("## About the company")
    about = company.get("about") or []
    if about:
        for line in about:
            lines.append(f"> {line['text']}")
            lines.append(f"  — {line['source_url']}")
            lines.append("")
    elif company.get("description"):
        lines.append(f"> {company['description']}")
    else:
        lines.append("_They do not describe themselves on the pages we read._")
    facts = company.get("identity_facts") or {}
    if facts:
        lines.append("")
        for attribute, detail in facts.items():
            label = attribute.replace("_", " ").capitalize()
            lines.append(_bullet(f"{label}: {detail['value']} — {detail['source_url'] or 'source'}"))
    lines.append("")

    # --- recent activity ---
    lines.append("## Recent activity")
    if profile["recent_activity"]:
        for item in profile["recent_activity"]:
            source = item.get("source") or {}
            when = (
                item["published_at"][:10]
                if item.get("published_at")
                else "no publication date"
            )
            lines.append(_bullet(f"**{item['claim']}**"))
            if item.get("excerpt"):
                lines.append(f"  > {item['excerpt']}")
            basis = (
                "as published"
                if item.get("freshness_basis") == "published_at"
                else "from retrieval date"
            )
            lines.append(
                f"  Evidence: {source.get('url', 'n/a')} · {when} · "
                f"{item['freshness']} ({basis}) · {item['epistemic_status']}"
            )
    else:
        lines.append("_No business activity was observed in the retrieved sources._")
    lines.append("")

    # --- signals ---
    lines.append("## Business signals")
    if profile["all_signals"]:
        for signal in profile["all_signals"]:
            lines.append(
                _bullet(
                    f"**{signal['title']}** — freshness: {signal['freshness']}, "
                    f"confidence: {signal['confidence_level']}, "
                    f"{signal['evidence_count']} evidence item(s)"
                )
            )
    else:
        lines.append("_No signals could be derived from the available evidence._")
    lines.append("")

    # --- opportunities ---
    lines.append("## Potential UBM opportunities")
    lines.append(
        "_These are hypotheses derived from public evidence, not established needs._"
    )
    lines.append("")
    if profile["opportunities"]:
        for index, item in enumerate(profile["opportunities"], start=1):
            lines.append(f"### {index}. {item['title']}")
            lines.append(f"**Relevant capability:** {item['capability']}")
            lines.append(f"**Why this may be relevant:** {item['why_relevant']}")
            lines.append(
                f"**Evidence:** {item['evidence_count']} item(s) · "
                f"**Freshness:** {item['freshness']} · "
                f"**Confidence:** {item['confidence_level']} · "
                f"**Status:** {item['status']}"
            )
            lines.append("")
    else:
        lines.append("_No capability matched the signals observed for this company._")
        lines.append("")

    # --- people ---
    lines.append("## Decision makers")
    if profile["decision_makers"]:
        for person in profile["decision_makers"]:
            name = person["name"] or "_name not published_"
            lines.append(_bullet(f"**{person['role']}** — {name}"))
            detail = [f"verification: {person['verification_status']}"]
            if person.get("email"):
                detail.append(f"email: {person['email']}")
            if person.get("source_url"):
                detail.append(f"source: {person['source_url']}")
            lines.append(f"  {' · '.join(detail)}")
    else:
        lines.append("_No publicly listed roles were found on the retrieved pages._")
    lines.append("")

    # --- uncertainties ---
    lines.append("## Uncertainties")
    if profile["uncertainties"]:
        for note in profile["uncertainties"]:
            lines.append(_bullet(note))
    else:
        lines.append("_No conflicts or notable gaps were recorded._")
    lines.append("")

    # --- sources ---
    lines.append("## Sources")
    if profile["sources"]:
        for source in profile["sources"]:
            title = source["title"] or source["url"]
            lines.append(_bullet(f"[{title}]({source['url']}) — {source['type']}, {source['reliability']}"))
    else:
        lines.append("_No sources were retrieved._")

    return "\n".join(lines)
