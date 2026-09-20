"""Evidence extraction, deduplication, signals, contradictions and matching."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models import UbmCapability
from app.models.enums import (
    ConfidenceLevel,
    ContradictionStatus,
    EpistemicStatus,
    EvidenceType,
    OpportunityStatus,
    SourceReliability,
)
from app.services import capability_matching, contradictions, signal_engine
from app.services.evidence_extraction import (
    deduplicate,
    extract_from_text,
    extract_identity,
    published_date_from_text,
)
from app.services.fingerprints import (
    content_hash,
    evidence_fingerprint,
    normalize_text,
    signal_fingerprint,
)
from tests.factories_phase2 import make_company, make_evidence, make_source


# --------------------------------------------------------------------------- #
# extraction
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text,expected",
    [
        ("The company opened two new showrooms in Bhopal last month.", EvidenceType.NEW_STORE),
        ("We are expanding into Gujarat with a new distribution hub.", EvidenceType.GEOGRAPHIC_EXPANSION),
        ("The brand launched a new product line for the festive season.", EvidenceType.PRODUCT_LAUNCH),
        ("We are hiring a Brand Marketing Manager for our Pune office.", EvidenceType.MARKETING_HIRING),
        ("The firm will exhibit at the India Pharma Expo in March.", EvidenceType.EVENT_PARTICIPATION),
        ("The company partnered with a regional logistics provider.", EvidenceType.PARTNERSHIP),
        ("The group announced the acquisition of a logistics company.", EvidenceType.ACQUISITION),
    ],
)
def test_extracts_business_events(text, expected):
    found = extract_from_text(text, company_name="Acme")
    assert expected in {item.evidence_type for item in found}


def test_extraction_is_industry_agnostic():
    """The same sentence shape must behave identically across sectors."""
    template = "{company} opened two new {noun} in Bhopal last month."
    results = [
        extract_from_text(template.format(company=name, noun=noun), company_name=name)
        for name, noun in [
            ("Acme Jewellers", "showrooms"),
            ("Zenith Hospitals", "clinics"),
            ("Orbit Logistics", "warehouses"),
        ]
    ]
    assert all(found for found in results)
    # Each resolves to a footprint-related type, none to an industry rule.
    for found in results:
        assert found[0].evidence_type in {
            EvidenceType.NEW_STORE,
            EvidenceType.NEW_LOCATION,
            EvidenceType.GEOGRAPHIC_EXPANSION,
        }


def test_hedged_statements_are_possible_not_known():
    found = extract_from_text(
        "The company plans to launch a new product range next year.", company_name="Acme"
    )
    assert found and found[0].epistemic_status == EpistemicStatus.POSSIBLE


def test_direct_statements_are_known():
    found = extract_from_text(
        "The company launched a new product range in April.", company_name="Acme"
    )
    assert found and found[0].epistemic_status == EpistemicStatus.KNOWN


def test_excerpt_is_verbatim_from_the_source():
    """A reader must be able to find the excerpt on the page."""
    sentence = "The company opened two new showrooms in Bhopal last month."
    found = extract_from_text(sentence, company_name="Acme")
    assert found[0].excerpt in sentence


def test_boilerplate_is_not_evidence():
    text = (
        "Copyright © 2026 Acme Retail. All rights reserved. "
        "Please accept our cookie policy and terms of service to continue."
    )
    assert extract_from_text(text, company_name="Acme") == []


def test_nothing_is_extracted_from_empty_input():
    assert extract_from_text(None, company_name="Acme") == []
    assert extract_from_text("", company_name="Acme") == []


def test_no_evidence_when_nothing_is_stated():
    text = "Welcome to our website. Browse our catalogue and find a store near you."
    assert extract_from_text(text, company_name="Acme") == []


def test_identity_facts_are_structured():
    items = extract_identity(
        "Founded in 1998, the company today employs around 450 employees.",
        company_name="Acme",
    )
    values = {item.normalized_value["attribute"]: item.normalized_value["value"] for item in items}
    assert values == {"founded_year": 1998, "employee_count": 450}


def test_quantities_are_captured_when_stated_numerically():
    found = extract_from_text("Acme opened 3 new stores in Indore.", company_name="Acme")
    assert found[0].normalized_value.get("quantity") == 3


def test_published_date_parsing_rejects_nonsense():
    assert published_date_from_text("Published 2026-03-14 by staff") is not None
    assert published_date_from_text("Order #12345678 shipped") is None
    assert published_date_from_text(None) is None


# --------------------------------------------------------------------------- #
# deduplication
# --------------------------------------------------------------------------- #


def test_duplicate_claims_collapse_keeping_the_longest_excerpt():
    items = extract_from_text(
        "Acme opened a new store in Indore.\n"
        "Acme opened a new store in Indore, its third in the region this year.",
        company_name="Acme",
    )
    deduped = deduplicate(items)
    assert len(deduped) == 1
    assert "third in the region" in deduped[0].excerpt


def test_fingerprints_are_stable_and_claim_sensitive():
    a = evidence_fingerprint(1, "new_store", "Acme opened a store.")
    b = evidence_fingerprint(1, "new_store", "acme  opened   a store!")
    c = evidence_fingerprint(1, "new_store", "Acme closed a store.")
    d = evidence_fingerprint(2, "new_store", "Acme opened a store.")
    assert a == b, "cosmetic differences must not create a new fingerprint"
    assert a != c and a != d


def test_content_hash_detects_change():
    assert content_hash("hello world") == content_hash("Hello   World!")
    assert content_hash("hello") != content_hash("goodbye")
    assert content_hash(None) is None


def test_normalize_text_handles_none():
    assert normalize_text(None) == ""


# --------------------------------------------------------------------------- #
# signals
# --------------------------------------------------------------------------- #


async def test_signals_group_related_evidence(session):
    company = await make_company(session)
    source = await make_source(session, company.id)
    items = [
        await make_evidence(session, company.id, source.id, evidence_type="new_store", claim="c1"),
        await make_evidence(
            session, company.id, source.id, evidence_type="geographic_expansion", claim="c2"
        ),
        await make_evidence(session, company.id, source.id, evidence_type="campaign", claim="c3"),
    ]
    signals = signal_engine.derive_signals(items, company_name=company.name)
    by_type = {signal.signal_type: signal for signal in signals}

    assert by_type["geographic_expansion"].evidence_count == 2
    assert by_type["marketing_activity"].evidence_count == 1
    # Every evidence id is retained so the reasoning can be walked back.
    assert set(by_type["geographic_expansion"].evidence_ids) == {items[0].id, items[1].id}


async def test_signal_strength_rises_with_more_sources(session):
    company = await make_company(session)
    one = await make_source(session, company.id, url="https://a.test/1")
    two = await make_source(session, company.id, url="https://b.test/2")

    single = [await make_evidence(session, company.id, one.id, claim="x1")]
    multi = [
        await make_evidence(session, company.id, one.id, claim="y1"),
        await make_evidence(session, company.id, two.id, claim="y2"),
    ]
    weak = signal_engine.derive_signals(single, company_name=company.name)[0]
    strong = signal_engine.derive_signals(multi, company_name=company.name)[0]
    assert strong.strength > weak.strength
    assert strong.distinct_sources == 2


async def test_identity_evidence_does_not_become_a_signal(session):
    company = await make_company(session)
    source = await make_source(session, company.id)
    item = await make_evidence(
        session, company.id, source.id, evidence_type="company_identity", claim="founded"
    )
    assert signal_engine.derive_signals([item], company_name=company.name) == []


def test_signal_fingerprint_is_one_per_company_and_type():
    assert signal_fingerprint(1, "event_activity") == signal_fingerprint(1, "event_activity")
    assert signal_fingerprint(1, "event_activity") != signal_fingerprint(2, "event_activity")


# --------------------------------------------------------------------------- #
# contradictions
# --------------------------------------------------------------------------- #


async def test_conflicting_headcounts_are_detected_not_resolved_silently(session):
    company = await make_company(session)
    website = await make_source(session, company.id, url="https://acme-retail.test/about")
    article = await make_source(
        session,
        company.id,
        url="https://news.test/acme",
        source_reliability=SourceReliability.PRESS,
    )
    a = await make_evidence(
        session, company.id, website.id,
        evidence_type="company_identity", claim="500 staff",
        normalized_value={"attribute": "employee_count", "value": 500},
    )
    b = await make_evidence(
        session, company.id, article.id,
        evidence_type="company_identity", claim="200 staff",
        normalized_value={"attribute": "employee_count", "value": 200},
    )

    found = contradictions.detect([a, b])
    assert len(found) == 1
    conflict = found[0]
    assert conflict.subject == "employee_count"
    assert {conflict.evidence_a_id, conflict.evidence_b_id} == {a.id, b.id}
    # Both sides survive; the explanation names the conflict.
    assert "Conflicting public information" in conflict.explanation


async def test_newer_evidence_is_preferred_but_both_are_kept(session):
    company = await make_company(session)
    old_source = await make_source(session, company.id, url="https://a.test/old")
    new_source = await make_source(session, company.id, url="https://b.test/new")
    old = await make_evidence(
        session, company.id, old_source.id, claim="old",
        evidence_type="company_identity",
        normalized_value={"attribute": "employee_count", "value": 200},
        published_at=datetime.now(UTC) - timedelta(days=400),
    )
    new = await make_evidence(
        session, company.id, new_source.id, claim="new",
        evidence_type="company_identity",
        normalized_value={"attribute": "employee_count", "value": 500},
        published_at=datetime.now(UTC) - timedelta(days=5),
    )
    conflict = contradictions.detect([old, new])[0]
    assert conflict.status == ContradictionStatus.RESOLVED_BY_RECENCY
    assert conflict.preferred_evidence_id == new.id


async def test_unresolvable_conflicts_stay_unresolved(session):
    """Equal dates and equal reliability must not be decided arbitrarily."""
    company = await make_company(session)
    a_source = await make_source(session, company.id, url="https://a.test/x")
    b_source = await make_source(session, company.id, url="https://b.test/y")
    a = await make_evidence(
        session, company.id, a_source.id, claim="a",
        evidence_type="company_identity",
        normalized_value={"attribute": "employee_count", "value": 100},
    )
    b = await make_evidence(
        session, company.id, b_source.id, claim="b",
        evidence_type="company_identity",
        normalized_value={"attribute": "employee_count", "value": 900},
    )
    conflict = contradictions.detect([a, b])[0]
    assert conflict.status == ContradictionStatus.UNRESOLVED
    assert conflict.preferred_evidence_id is None


async def test_small_headcount_differences_are_not_a_contradiction(session):
    company = await make_company(session)
    a_source = await make_source(session, company.id, url="https://a.test/x")
    b_source = await make_source(session, company.id, url="https://b.test/y")
    a = await make_evidence(
        session, company.id, a_source.id, claim="a",
        evidence_type="company_identity",
        normalized_value={"attribute": "employee_count", "value": 500},
    )
    b = await make_evidence(
        session, company.id, b_source.id, claim="b",
        evidence_type="company_identity",
        normalized_value={"attribute": "employee_count", "value": 480},
    )
    assert contradictions.detect([a, b]) == []


async def test_same_source_repeating_a_figure_is_not_a_contradiction(session):
    company = await make_company(session)
    source = await make_source(session, company.id)
    a = await make_evidence(
        session, company.id, source.id, claim="a",
        evidence_type="company_identity",
        normalized_value={"attribute": "employee_count", "value": 100},
    )
    b = await make_evidence(
        session, company.id, source.id, claim="b",
        evidence_type="company_identity",
        normalized_value={"attribute": "employee_count", "value": 900},
    )
    assert contradictions.detect([a, b]) == []


# --------------------------------------------------------------------------- #
# capability matching
# --------------------------------------------------------------------------- #


def _capability(**overrides) -> UbmCapability:
    capability = UbmCapability(
        **{
            "id": overrides.pop("id", 1),
            "slug": "on-ground",
            "name": "On-Ground Activations",
            "description": "Localised customer-facing activations.",
            "signal_types": ["geographic_expansion"],
            "keywords": [],
            "weight": 1.0,
            "active": True,
            **overrides,
        }
    )
    return capability


def _signal(signal_type: str, **overrides) -> signal_engine.DerivedSignal:
    return signal_engine.DerivedSignal(
        signal_type=signal_type,
        title=signal_type.replace("_", " ").title(),
        description="d",
        evidence_ids=overrides.pop("evidence_ids", [1, 2]),
        strength=overrides.pop("strength", 0.8),
        freshness=overrides.pop("freshness", "recent"),
        confidence=overrides.pop("confidence", 0.8),
        confidence_level=overrides.pop("confidence_level", ConfidenceLevel.HIGH),
        confidence_components=overrides.pop("confidence_components", {"components": {}}),
        latest_evidence_at=None,
        evidence_count=2,
        distinct_sources=overrides.pop("distinct_sources", 1),
    )


def test_capability_matches_only_its_declared_signals():
    matches = capability_matching.match(
        [_signal("geographic_expansion")], [_capability()], company_name="Acme"
    )
    assert len(matches) == 1
    assert matches[0].capability_name == "On-Ground Activations"


def test_capability_does_not_match_unrelated_signals():
    matches = capability_matching.match(
        [_signal("hiring_activity")], [_capability()], company_name="Acme"
    )
    assert matches == []


def test_inactive_capabilities_are_skipped():
    matches = capability_matching.match(
        [_signal("geographic_expansion")], [_capability(active=False)], company_name="Acme"
    )
    assert matches == []


def test_matching_is_industry_agnostic():
    """Identical signals must yield identical matches regardless of company."""
    signals = [_signal("geographic_expansion")]
    a = capability_matching.match(signals, [_capability()], company_name="Acme Jewellers")
    b = capability_matching.match(signals, [_capability()], company_name="Zenith Hospitals")
    assert [item.capability_id for item in a] == [item.capability_id for item in b]
    assert a[0].confidence == b[0].confidence


def test_opportunity_carries_its_evidence_ids():
    matches = capability_matching.match(
        [_signal("geographic_expansion", evidence_ids=[7, 8, 9])],
        [_capability()],
        company_name="Acme",
    )
    assert matches[0].evidence_ids == [7, 8, 9]
    assert matches[0].evidence_count == 3


def test_single_source_support_cannot_be_marked_supported():
    """One page producing many signals must not promote a hypothesis."""
    matches = capability_matching.match(
        [
            _signal("geographic_expansion", distinct_sources=1),
            _signal("event_activity", distinct_sources=1),
        ],
        [_capability(signal_types=["geographic_expansion", "event_activity"])],
        company_name="Acme",
    )
    assert matches[0].status != OpportunityStatus.SUPPORTED


def test_multi_source_corroboration_can_reach_supported():
    matches = capability_matching.match(
        [
            _signal("geographic_expansion", distinct_sources=3),
            _signal("event_activity", distinct_sources=2),
        ],
        [_capability(signal_types=["geographic_expansion", "event_activity"])],
        company_name="Acme",
    )
    assert matches[0].status == OpportunityStatus.SUPPORTED


def test_rationale_uses_provisional_language():
    matches = capability_matching.match(
        [_signal("geographic_expansion")],
        [_capability(rationale_template="{company} shows {signal_summary}. This may be relevant.")],
        company_name="Acme",
    )
    text = matches[0].why_relevant.lower()
    assert "may" in text or "could" in text
    assert "definitely" not in text and "needs" not in text


async def test_many_differing_values_yield_one_contradiction_not_n_squared(session):
    """Six differing years must not produce fifteen near-identical rows."""
    company = await make_company(session)
    items = []
    for index, year in enumerate([1968, 1980, 1982, 2011, 2014, 2017]):
        source = await make_source(session, company.id, url=f"https://s{index}.test/about")
        items.append(
            await make_evidence(
                session, company.id, source.id,
                claim=f"founded {year}",
                evidence_type="company_identity",
                normalized_value={"attribute": "founded_year", "value": year},
            )
        )

    found = contradictions.detect(items)
    assert len(found) == 1
    # The single row names every distinct value so nothing is hidden.
    explanation = found[0].explanation
    assert "6 sources" in explanation
    for year in (1968, 2017):
        assert str(year) in explanation


def test_founding_year_needs_an_explicit_verb():
    """'since 2014' appears in copyright lines and unrelated prose."""
    from app.services.evidence_extraction import extract_identity

    assert extract_identity("Trusted by customers since 2014.", company_name="X") == []
    assert extract_identity("The company was founded in 2014.", company_name="X")
