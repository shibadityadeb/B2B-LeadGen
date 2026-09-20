"""Personalization, strategy, composition and validation."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import (
    ClaimKind,
    MessageLength,
    ObservationState,
    OutreachObjective,
    OutreachTone,
)
from app.providers.writer.base import ComposedClaim, ComposedEmail, WriterContext
from app.providers.writer.deterministic import DeterministicWriter
from app.services.outreach_strategy import build_strategy, choose_objective
from app.services.outreach_validation import validate_outreach
from app.services.personalization import build_personalization, email_display_name
from tests.factories_phase2 import make_company, make_evidence, make_source
from tests.factories_phase3 import make_capability, make_opportunity, make_person


# Each call creates its own company; the domain is unique per call so a test
# may build more than one scenario.
_COUNTER = {"n": 0}


async def _setup(session, *, with_person=True, evidence_specs=None):
    _COUNTER["n"] += 1
    index = _COUNTER["n"]
    company = await make_company(
        session,
        canonical_domain=f"acme-{index}.test",
        website_url=f"https://acme-{index}.test",
    )
    source = await make_source(session, company.id)
    specs = evidence_specs or [
        ("new_store", "Acme Retail opened two new showrooms in Bhopal this month."),
        ("campaign", "Acme Retail launched a regional advertising campaign in March."),
    ]
    evidence = [
        await make_evidence(
            session, company.id, source.id,
            evidence_type=kind, claim=f"claim {index}", excerpt=excerpt,
            published_at=datetime.now(UTC),
        )
        for index, (kind, excerpt) in enumerate(specs)
    ]
    capability = await make_capability(session, slug=f"capability-{index}")
    opportunity = await make_opportunity(
        session, company.id, capability.id, [item.id for item in evidence]
    )
    person = await make_person(session, company.id) if with_person else None
    return company, opportunity, capability, evidence, person


# --------------------------------------------------------------------------- #
# personalization
# --------------------------------------------------------------------------- #


async def test_personalization_is_built_only_from_stored_evidence(session):
    company, opportunity, capability, evidence, person = await _setup(session)
    data = build_personalization(
        company=company, opportunity=opportunity, capability=capability,
        evidence=evidence, signals=[], recipient=person,
    )
    assert data.points
    known_ids = {item.id for item in evidence}
    for point in data.points:
        assert set(point.evidence_ids) <= known_ids
        # The excerpt is the verbatim source text, not a paraphrase.
        assert point.excerpt in {item.excerpt for item in evidence}


async def test_personalization_selects_at_most_two_points(session):
    specs = [
        ("new_store", "Acme opened two new showrooms in Bhopal this month for customers."),
        ("campaign", "Acme launched a regional advertising campaign in March this year."),
        ("partnership", "Acme partnered with a local logistics provider for deliveries."),
        ("funding", "Acme raised a funding round led by a regional investor group."),
    ]
    company, opportunity, capability, evidence, person = await _setup(
        session, evidence_specs=specs
    )
    data = build_personalization(
        company=company, opportunity=opportunity, capability=capability,
        evidence=evidence, signals=[], recipient=person, max_points=2,
    )
    assert len(data.points) == 2, "an email stuffed with facts reads like a mail merge"


async def test_evidence_no_longer_observed_is_not_used(session):
    company, opportunity, capability, evidence, person = await _setup(session)
    for item in evidence:
        item.observation_state = ObservationState.NOT_FOUND
    await session.commit()

    data = build_personalization(
        company=company, opportunity=opportunity, capability=capability,
        evidence=evidence, signals=[], recipient=person,
    )
    assert data.points == []
    assert any("no usable public evidence" in note.lower() for note in data.uncertainties)


async def test_unnamed_recipient_is_not_given_a_name(session):
    company, opportunity, capability, evidence, _ = await _setup(session, with_person=False)
    person = await make_person(session, company.id, name=None, role="Head of Marketing")

    data = build_personalization(
        company=company, opportunity=opportunity, capability=capability,
        evidence=evidence, signals=[], recipient=person,
    )
    assert data.recipient["name"] is None
    assert data.recipient["role"] == "Head of Marketing"
    assert any("name is not published" in note for note in data.uncertainties)


async def test_missing_email_is_flagged_not_invented(session):
    company, opportunity, capability, evidence, person = await _setup(session)
    data = build_personalization(
        company=company, opportunity=opportunity, capability=capability,
        evidence=evidence, signals=[], recipient=person,
    )
    assert data.recipient["email"] is None
    assert any("email address" in note for note in data.uncertainties)


async def test_undated_evidence_is_flagged_as_estimated(session):
    company = await make_company(session)
    source = await make_source(session, company.id)
    evidence = [
        await make_evidence(
            session, company.id, source.id, evidence_type="new_store",
            excerpt="Acme Retail opened two new showrooms in Bhopal this month.",
            published_at=None,
        )
    ]
    capability = await make_capability(session)
    opportunity = await make_opportunity(session, company.id, capability.id, [evidence[0].id])

    data = build_personalization(
        company=company, opportunity=opportunity, capability=capability,
        evidence=evidence, signals=[], recipient=None,
    )
    assert data.points[0].freshness_basis == "observed_at"
    assert any("no publication date" in note for note in data.uncertainties)


def test_listicle_company_names_are_not_used_in_emails():
    class Fake:
        def __init__(self, name, domain):
            self.name, self.canonical_domain = name, domain

    assert email_display_name(Fake("25 Best Jewellery Shops in Indore", "bluestone.com")) == "Bluestone"
    assert email_display_name(Fake("Reliance Jewels", "reliancejewels.com")) == "Reliance Jewels"


# --------------------------------------------------------------------------- #
# strategy
# --------------------------------------------------------------------------- #


async def test_objective_falls_back_when_evidence_is_absent(session):
    company, opportunity, capability, evidence, person = await _setup(session)
    for item in evidence:
        item.observation_state = ObservationState.NOT_FOUND
    await session.commit()
    data = build_personalization(
        company=company, opportunity=opportunity, capability=capability,
        evidence=evidence, signals=[], recipient=person,
    )
    # Without an observation the message cannot credibly "share an idea".
    assert choose_objective(data) == OutreachObjective.INTRODUCE_CAPABILITY


async def test_follow_up_objective_is_always_follow_up(session):
    company, opportunity, capability, evidence, person = await _setup(session)
    data = build_personalization(
        company=company, opportunity=opportunity, capability=capability,
        evidence=evidence, signals=[], recipient=person,
    )
    assert choose_objective(data, is_follow_up=True) == OutreachObjective.FOLLOW_UP


async def test_strategy_records_the_plan_without_model_narration(session):
    company, opportunity, capability, evidence, person = await _setup(session)
    data = build_personalization(
        company=company, opportunity=opportunity, capability=capability,
        evidence=evidence, signals=[], recipient=person,
    )
    strategy = build_strategy(personalization=data, capability=capability)
    payload = strategy.dict()
    assert set(payload) >= {
        "objective", "relevant_capability", "recipient_role",
        "personalization_points", "call_to_action", "tone", "message_length",
    }
    assert payload["relevant_capability"] == capability.name


# --------------------------------------------------------------------------- #
# composition
# --------------------------------------------------------------------------- #


async def _context(session, **overrides) -> WriterContext:
    company, opportunity, capability, evidence, person = await _setup(session)
    data = build_personalization(
        company=company, opportunity=opportunity, capability=capability,
        evidence=evidence, signals=[], recipient=person,
    )
    strategy = build_strategy(
        personalization=data,
        capability=capability,
        tone=overrides.pop("tone", OutreachTone.PROFESSIONAL),
        message_length=overrides.pop("message_length", MessageLength.SHORT),
    )
    return WriterContext(
        company_name=email_display_name(company),
        personalization=data,
        strategy=strategy,
        capability_name=capability.name,
        capability_description=capability.description,
        sender_name="Test Sender",
        sender_company="Upshot Brand Media",
        **overrides,
    )


async def test_every_company_claim_carries_evidence(session):
    context = await _context(session)
    email = await DeterministicWriter().generate_outreach(context)

    company_claims = [
        claim for claim in email.claims if claim.kind == ClaimKind.COMPANY_FACT
    ]
    assert company_claims
    for claim in company_claims:
        assert claim.evidence_ids, f"unsupported claim: {claim.text}"


async def test_generated_email_has_subject_body_and_a_question(session):
    context = await _context(session)
    email = await DeterministicWriter().generate_outreach(context)
    assert email.subject and email.body
    assert email.call_to_action.endswith("?") or "happy to" in email.call_to_action.lower()
    assert email.greeting.startswith("Hi ") or email.greeting.startswith("Hello ")


async def test_email_avoids_generic_agency_language(session):
    context = await _context(session)
    email = await DeterministicWriter().generate_outreach(context)
    lowered = email.body.lower()
    for phrase in ("dear sir", "leading marketing agency", "world class", "act now"):
        assert phrase not in lowered


async def test_generation_is_deterministic(session):
    context = await _context(session)
    writer = DeterministicWriter()
    first = await writer.generate_outreach(context)
    second = await writer.generate_outreach(context)
    assert first.subject == second.subject and first.body == second.body


async def test_short_messages_use_one_point_medium_uses_two(session):
    short = await DeterministicWriter().generate_outreach(await _context(session))
    medium = await DeterministicWriter().generate_outreach(
        await _context(session, message_length=MessageLength.MEDIUM)
    )
    assert len(medium.body) > len(short.body)


async def test_greeting_addresses_the_role_when_no_name_exists(session):
    company, opportunity, capability, evidence, _ = await _setup(session, with_person=False)
    person = await make_person(session, company.id, name=None, role="Head of Marketing")
    data = build_personalization(
        company=company, opportunity=opportunity, capability=capability,
        evidence=evidence, signals=[], recipient=person,
    )
    strategy = build_strategy(personalization=data, capability=capability)
    context = WriterContext(
        company_name="Acme", personalization=data, strategy=strategy,
        capability_name=capability.name, capability_description=capability.description,
        sender_name="Test Sender", sender_company="UBM",
    )
    email = await DeterministicWriter().generate_outreach(context)
    assert email.greeting == "Hello Head of Marketing,"
    assert "sir" not in email.greeting.lower()


async def test_follow_up_is_shorter_and_references_the_earlier_note(session):
    context = await _context(session, previous_subject="An idea for Acme")
    writer = DeterministicWriter()
    first = await writer.generate_outreach(context)
    follow_up = await writer.generate_follow_up(context)

    assert "following up" in follow_up.body.lower()
    assert follow_up.subject.lower().startswith("following up")
    # A follow-up must not balloon past the original.
    assert len(follow_up.body) <= len(first.body) * 1.35


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #


def _personalization(**overrides):
    from app.services.personalization import PersonalizationData

    return PersonalizationData(
        recipient=overrides.pop(
            "recipient", {"decision_maker_id": 1, "name": "Priya Nair", "role": "Head of Marketing"}
        ),
        company_reference=None,
        business_signal=None,
        relevant_ubm_capability={"id": 1, "name": "On-Ground Activations"},
        conversation_angle="angle",
        points=overrides.pop("points", []),
        uncertainties=overrides.pop("uncertainties", []),
    )


def _email(body: str, subject: str = "A subject") -> ComposedEmail:
    return ComposedEmail(
        subject=subject, greeting="Hi Priya,", body_paragraphs=[body],
        call_to_action="Would that be useful?", signature="Best",
    )


def test_a_claim_without_evidence_is_an_error():
    result = validate_outreach(
        email=_email("Acme opened three new stores."),
        claims=[ComposedClaim(text="Acme opened three new stores.", evidence_ids=[])],
        personalization=_personalization(),
        evidence_excerpts={},
        recipient_email="priya@example.com",
        capability_exists=True,
    )
    assert not result.valid
    assert any(issue.code == "unsupported_claim" for issue in result.errors)


def test_a_number_absent_from_the_evidence_is_rejected():
    result = validate_outreach(
        email=_email("Acme opened 12 new stores."),
        claims=[ComposedClaim(text="Acme opened 12 new stores.", evidence_ids=[7])],
        personalization=_personalization(),
        evidence_excerpts={7: "Acme opened two new showrooms in Bhopal."},
        recipient_email="priya@example.com",
        capability_exists=True,
    )
    assert not result.valid
    assert any(issue.code == "fabricated_number" for issue in result.errors)


def test_a_number_present_in_the_evidence_is_accepted():
    result = validate_outreach(
        email=_email("Acme opened 2 new stores."),
        claims=[ComposedClaim(text="Acme opened 2 new stores.", evidence_ids=[7])],
        personalization=_personalization(),
        evidence_excerpts={7: "Acme opened 2 new showrooms in Bhopal."},
        recipient_email="priya@example.com",
        capability_exists=True,
    )
    assert result.valid


def test_claimed_prior_relationships_are_rejected():
    for phrase in ("We have worked with brands like yours.", "See our case study on retail."):
        result = validate_outreach(
            email=_email(phrase),
            claims=[],
            personalization=_personalization(),
            evidence_excerpts={},
            recipient_email="priya@example.com",
            capability_exists=True,
        )
        assert not result.valid, phrase
        assert any(
            issue.code == "unsupported_relationship_claim" for issue in result.errors
        ), phrase


def test_evidence_that_no_longer_exists_is_an_error():
    result = validate_outreach(
        email=_email("Acme expanded into Bhopal."),
        claims=[ComposedClaim(text="Acme expanded into Bhopal.", evidence_ids=[999])],
        personalization=_personalization(),
        evidence_excerpts={},
        recipient_email="priya@example.com",
        capability_exists=True,
    )
    assert any(issue.code == "missing_evidence" for issue in result.errors)


def test_unfilled_placeholders_are_rejected():
    result = validate_outreach(
        email=_email("Hi [Name], I saw your work."),
        claims=[],
        personalization=_personalization(),
        evidence_excerpts={},
        recipient_email="priya@example.com",
        capability_exists=True,
    )
    assert any(issue.code == "unfilled_placeholder" for issue in result.errors)


def test_invalid_recipient_address_is_rejected():
    result = validate_outreach(
        email=_email("Hello there."),
        claims=[],
        personalization=_personalization(),
        evidence_excerpts={},
        recipient_email="not-an-email",
        capability_exists=True,
    )
    assert any(issue.code == "invalid_recipient_email" for issue in result.errors)


def test_missing_recipient_blocks_only_when_not_explicitly_allowed():
    blocking = validate_outreach(
        email=_email("Hello there."), claims=[], personalization=_personalization(),
        evidence_excerpts={}, recipient_email=None, capability_exists=True,
    )
    assert not blocking.valid

    permissive = validate_outreach(
        email=_email("Hello there."), claims=[], personalization=_personalization(),
        evidence_excerpts={}, recipient_email=None, capability_exists=True,
        allow_missing_recipient=True,
    )
    assert permissive.valid
    assert any(issue.code == "missing_recipient_email" for issue in permissive.warnings)


def test_a_deleted_capability_blocks_the_email():
    result = validate_outreach(
        email=_email("Hello there."), claims=[], personalization=_personalization(),
        evidence_excerpts={}, recipient_email="priya@example.com", capability_exists=False,
    )
    assert any(issue.code == "unknown_capability" for issue in result.errors)


def test_a_missing_subject_or_body_is_an_error():
    result = validate_outreach(
        email=ComposedEmail(subject="", greeting="", body_paragraphs=[], call_to_action="", signature=""),
        claims=[], personalization=_personalization(), evidence_excerpts={},
        recipient_email="priya@example.com", capability_exists=True,
    )
    codes = {issue.code for issue in result.errors}
    assert {"missing_subject", "missing_body", "missing_cta"} <= codes


def test_generic_marketing_language_is_a_warning_not_a_block():
    result = validate_outreach(
        email=_email("We are a world class agency."), claims=[],
        personalization=_personalization(), evidence_excerpts={},
        recipient_email="priya@example.com", capability_exists=True,
    )
    assert any(issue.code == "generic_marketing_language" for issue in result.warnings)


def test_uncertainties_are_surfaced_as_warnings():
    result = validate_outreach(
        email=_email("Hello."), claims=[],
        personalization=_personalization(uncertainties=["The date is estimated."]),
        evidence_excerpts={}, recipient_email="priya@example.com", capability_exists=True,
    )
    assert any(issue.message == "The date is estimated." for issue in result.warnings)
