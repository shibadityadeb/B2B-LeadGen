"""State transitions, Gmail drafts, follow-ups, outcomes and versioning.

The delivery provider is always a fake: no email is drafted or sent anywhere.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.errors import ConflictError, ValidationError
from app.models import AuditEvent, Outreach, OutreachClaim, OutreachVersion
from app.models.enums import (
    AuditAction,
    GenerationMethod,
    OutcomeStatus,
    OutreachStatus,
)
from app.services import outreach_state
from app.services.outreach_service import OutreachService
from tests.factories_phase3 import FakeDeliveryProvider, seeded_opportunity


async def _service(session, **overrides) -> OutreachService:
    return OutreachService(
        session, delivery=overrides.pop("delivery", FakeDeliveryProvider()), **overrides
    )


async def _approved(session, delivery=None, email="priya@example.com"):
    company, opportunity, evidence, person = await seeded_opportunity(session, email=email)
    service = OutreachService(session, delivery=delivery or FakeDeliveryProvider())
    outreach = await service.create_from_opportunity(opportunity_id=opportunity.id)
    await service.approve(outreach.id)
    return service, outreach


# --------------------------------------------------------------------------- #
# creation
# --------------------------------------------------------------------------- #


async def test_creating_outreach_puts_it_in_review_not_approved(session):
    company, opportunity, evidence, person = await seeded_opportunity(session)
    service = await _service(session)
    outreach = await service.create_from_opportunity(opportunity_id=opportunity.id)

    assert outreach.status == OutreachStatus.REVIEW
    assert outreach.approved_at is None
    assert outreach.gmail_draft_id is None
    assert outreach.sent_at is None


async def test_creation_records_claims_with_evidence(session):
    company, opportunity, evidence, person = await seeded_opportunity(session)
    service = await _service(session)
    outreach = await service.create_from_opportunity(opportunity_id=opportunity.id)

    version = await session.get(OutreachVersion, outreach.active_version_id)
    await session.refresh(version, ["claims"])
    bound = [claim for claim in version.claims if claim.requires_evidence]
    assert bound
    for claim in bound:
        await session.refresh(claim, ["evidence_links"])
        assert claim.evidence_links, f"unsupported claim persisted: {claim.text}"


async def test_recipient_email_is_taken_from_the_person_never_derived(session):
    company, opportunity, evidence, person = await seeded_opportunity(session, email=None)
    service = await _service(session)
    outreach = await service.create_from_opportunity(opportunity_id=opportunity.id)
    # The person has a name but no published address; none is invented.
    assert outreach.to_name == person.name
    assert outreach.to_email is None


async def test_requesting_the_same_outreach_twice_reuses_it(session):
    company, opportunity, evidence, person = await seeded_opportunity(session)
    service = await _service(session)
    first = await service.create_from_opportunity(
        opportunity_id=opportunity.id, decision_maker_id=person.id
    )
    second = await service.create_from_opportunity(
        opportunity_id=opportunity.id, decision_maker_id=person.id
    )
    assert first.id == second.id
    assert await session.scalar(select(func.count(Outreach.id))) == 1


# --------------------------------------------------------------------------- #
# state machine
# --------------------------------------------------------------------------- #


def test_a_draft_can_never_jump_straight_to_sent():
    assert not outreach_state.can_transition(OutreachStatus.DRAFT, OutreachStatus.SENT)
    assert not outreach_state.can_transition(OutreachStatus.REVIEW, OutreachStatus.SENT)


def test_gmail_drafts_require_approval():
    with pytest.raises(ConflictError):
        outreach_state.ensure_can_create_gmail_draft(OutreachStatus.REVIEW)
    outreach_state.ensure_can_create_gmail_draft(OutreachStatus.APPROVED)


async def test_approval_is_blocked_while_validation_fails(session):
    company, opportunity, evidence, person = await seeded_opportunity(session)
    service = await _service(session)
    outreach = await service.create_from_opportunity(opportunity_id=opportunity.id)

    # A hand edit that claims a relationship the system cannot support.
    await service.apply_edit(outreach.id, body="We have worked with brands like yours.")
    with pytest.raises(ValidationError):
        await service.approve(outreach.id)


async def test_editing_an_approved_outreach_returns_it_to_review(session):
    service, outreach = await _approved(session)
    assert outreach.status == OutreachStatus.APPROVED

    await service.apply_edit(outreach.id, body="A revised message body goes here.")
    refreshed = await service.outreach.get(outreach.id)
    assert refreshed.status == OutreachStatus.REVIEW
    assert refreshed.approved_at is None
    assert refreshed.user_edited is True


# --------------------------------------------------------------------------- #
# versioning
# --------------------------------------------------------------------------- #


async def test_regeneration_adds_a_version_and_keeps_the_old_one(session):
    company, opportunity, evidence, person = await seeded_opportunity(session)
    service = await _service(session)
    outreach = await service.create_from_opportunity(opportunity_id=opportunity.id)
    first_version_id = outreach.active_version_id

    await service.regenerate(outreach.id, tone="direct")
    versions = await service.versions.list_for(outreach.id)

    assert len(versions) == 2
    assert {version.version_number for version in versions} == {1, 2}
    # The original is preserved, just no longer active.
    original = next(v for v in versions if v.id == first_version_id)
    assert original.is_active is False
    assert original.body


async def test_user_edits_are_snapshotted_as_their_own_version(session):
    company, opportunity, evidence, person = await seeded_opportunity(session)
    service = await _service(session)
    outreach = await service.create_from_opportunity(opportunity_id=opportunity.id)

    await service.apply_edit(outreach.id, body="My own wording for this message.")
    versions = await service.versions.list_for(outreach.id)
    latest = versions[-1]
    assert latest.generation_method == GenerationMethod.USER_EDIT
    assert latest.body == "My own wording for this message."


async def test_a_previous_version_can_be_restored(session):
    company, opportunity, evidence, person = await seeded_opportunity(session)
    service = await _service(session)
    outreach = await service.create_from_opportunity(opportunity_id=opportunity.id)
    original_body = outreach.body

    await service.regenerate(outreach.id, tone="direct")
    versions = await service.versions.list_for(outreach.id)
    first = next(version for version in versions if version.version_number == 1)

    restored = await service.activate_version(outreach.id, first.id)
    assert restored.body == original_body
    assert restored.active_version_id == first.id


async def test_regeneration_does_not_create_a_second_outreach(session):
    company, opportunity, evidence, person = await seeded_opportunity(session)
    service = await _service(session)
    outreach = await service.create_from_opportunity(opportunity_id=opportunity.id)
    await service.regenerate(outreach.id)
    assert await session.scalar(select(func.count(Outreach.id))) == 1


async def test_reset_restores_the_generated_text(session):
    company, opportunity, evidence, person = await seeded_opportunity(session)
    service = await _service(session)
    outreach = await service.create_from_opportunity(opportunity_id=opportunity.id)
    generated = outreach.ai_generated_body

    await service.apply_edit(outreach.id, body="Hand written.")
    await service.apply_edit(outreach.id, body=generated)
    refreshed = await service.outreach.get(outreach.id)
    assert refreshed.body == generated


# --------------------------------------------------------------------------- #
# gmail drafts
# --------------------------------------------------------------------------- #


async def test_creating_a_gmail_draft_does_not_mark_it_sent(session):
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery)

    updated = await service.create_gmail_draft(outreach.id)
    assert updated.status == OutreachStatus.GMAIL_DRAFT_CREATED
    assert updated.gmail_draft_id
    # The crucial assertion: a draft is not a send.
    assert updated.sent_at is None
    assert len(delivery.created) == 1


async def test_clicking_twice_does_not_create_two_drafts(session):
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery)

    await service.create_gmail_draft(outreach.id)
    await service.create_gmail_draft(outreach.id)
    assert len(delivery.created) == 1, "the existing draft must be reused"


async def test_a_second_draft_can_be_requested_explicitly(session):
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery)

    await service.create_gmail_draft(outreach.id)
    await service.create_gmail_draft(outreach.id, force_new=True)
    assert len(delivery.created) == 2


async def test_a_draft_deleted_in_gmail_is_recreated(session):
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery)

    first = await service.create_gmail_draft(outreach.id)
    delivery.drafts.clear()  # the user deleted it in Gmail
    await service.create_gmail_draft(outreach.id)
    assert len(delivery.created) == 2


async def test_no_recipient_address_blocks_the_gmail_draft(session):
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery, email=None)

    with pytest.raises(ValidationError) as exc:
        await service.create_gmail_draft(outreach.id)
    assert "recipient email" in str(exc.value).lower()
    assert delivery.created == []


async def test_a_disconnected_mailbox_reports_rather_than_failing_silently(session):
    delivery = FakeDeliveryProvider(connected=False)
    service, outreach = await _approved(session, delivery)

    from app.core.errors import ProviderError

    with pytest.raises(ProviderError):
        await service.create_gmail_draft(outreach.id)


async def test_an_unapproved_outreach_cannot_reach_gmail(session):
    company, opportunity, evidence, person = await seeded_opportunity(
        session, email="priya@example.com"
    )
    delivery = FakeDeliveryProvider()
    service = OutreachService(session, delivery=delivery)
    outreach = await service.create_from_opportunity(opportunity_id=opportunity.id)

    with pytest.raises(ConflictError):
        await service.create_gmail_draft(outreach.id)
    assert delivery.created == []


# --------------------------------------------------------------------------- #
# sending is manual
# --------------------------------------------------------------------------- #


async def test_marking_sent_sets_the_next_follow_up_date(session):
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery)
    await service.create_gmail_draft(outreach.id)

    sent = await service.mark_sent(outreach.id)
    assert sent.status == OutreachStatus.SENT
    assert sent.sent_at is not None
    assert sent.next_follow_up_at is not None
    delta = sent.next_follow_up_at - sent.sent_at
    assert timedelta(days=2) < delta < timedelta(days=4), "default first interval is 3 days"


async def test_an_unapproved_outreach_cannot_be_marked_sent(session):
    company, opportunity, evidence, person = await seeded_opportunity(session)
    service = await _service(session)
    outreach = await service.create_from_opportunity(opportunity_id=opportunity.id)

    with pytest.raises(ConflictError):
        await service.mark_sent(outreach.id)


# --------------------------------------------------------------------------- #
# follow-ups
# --------------------------------------------------------------------------- #


async def test_a_follow_up_is_its_own_outreach_linked_to_the_original(session):
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery)
    await service.create_gmail_draft(outreach.id)
    await service.mark_sent(outreach.id)

    follow_up = await service.create_follow_up(outreach.id)
    assert follow_up.id != outreach.id
    assert follow_up.parent_outreach_id == outreach.id
    assert follow_up.follow_up_number == 1
    assert follow_up.status == OutreachStatus.REVIEW, "a follow-up still needs approval"
    assert follow_up.to_email == outreach.to_email


async def test_a_follow_up_requires_the_original_to_be_sent(session):
    service, outreach = await _approved(session)
    with pytest.raises(ConflictError):
        await service.create_follow_up(outreach.id)


async def test_follow_up_intervals_advance(session):
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery)
    await service.create_gmail_draft(outreach.id)
    await service.mark_sent(outreach.id)
    first_due = outreach.next_follow_up_at

    await service.create_follow_up(outreach.id)
    parent = await service.outreach.get(outreach.id)
    # The second interval is further out than the first.
    assert parent.next_follow_up_at > first_due


# --------------------------------------------------------------------------- #
# outcomes
# --------------------------------------------------------------------------- #


async def test_recording_an_outcome_appends_history(session):
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery)
    await service.create_gmail_draft(outreach.id)
    await service.mark_sent(outreach.id)

    await service.record_outcome(outreach.id, status=OutcomeStatus.REPLIED)
    await service.record_outcome(
        outreach.id, status=OutcomeStatus.MEETING_SCHEDULED, notes="Call on Friday"
    )

    refreshed = await service.outreach.get_full(outreach.id)
    assert refreshed.outcome_status == OutcomeStatus.MEETING_SCHEDULED
    assert len(refreshed.outcomes) == 2, "earlier outcomes are kept"


async def test_a_terminal_outcome_stops_follow_up_chasing(session):
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery)
    await service.create_gmail_draft(outreach.id)
    await service.mark_sent(outreach.id)

    await service.record_outcome(
        outreach.id, status=OutcomeStatus.NOT_INTERESTED, reason="no_budget"
    )
    refreshed = await service.outreach.get(outreach.id)
    assert refreshed.status == OutreachStatus.COMPLETED
    assert refreshed.next_follow_up_at is None
    assert refreshed.outcome_reason == "no_budget"


# --------------------------------------------------------------------------- #
# audit trail
# --------------------------------------------------------------------------- #


async def test_the_important_actions_are_audited(session):
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery)
    await service.create_gmail_draft(outreach.id)
    await service.mark_sent(outreach.id)
    await service.record_outcome(outreach.id, status=OutcomeStatus.REPLIED)

    events = list(
        await session.scalars(
            select(AuditEvent).where(AuditEvent.object_id == outreach.id)
        )
    )
    actions = {event.action for event in events}
    assert {
        AuditAction.OUTREACH_CREATED,
        AuditAction.EMAIL_GENERATED,
        AuditAction.EMAIL_APPROVED,
        AuditAction.GMAIL_DRAFT_CREATED,
        AuditAction.MARKED_SENT,
        AuditAction.OUTCOME_UPDATED,
    } <= actions


async def test_an_approved_outreach_can_still_be_rejected(session):
    """A reviewer must be able to change their mind before anything goes out."""
    service, outreach = await _approved(session)
    rejected = await service.reject(outreach.id, reason="Wrong angle")
    assert rejected.status == OutreachStatus.REJECTED


async def test_a_sent_outreach_cannot_be_rejected(session):
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery)
    await service.create_gmail_draft(outreach.id)
    await service.mark_sent(outreach.id)

    with pytest.raises(ConflictError):
        await service.reject(outreach.id)


async def test_the_original_message_is_never_labelled_a_follow_up(session):
    """The parent keeps follow_up_number 0 so the UI does not mislabel it."""
    delivery = FakeDeliveryProvider()
    service, outreach = await _approved(session, delivery)
    await service.create_gmail_draft(outreach.id)
    await service.mark_sent(outreach.id)
    await service.create_follow_up(outreach.id)

    parent = await service.outreach.get(outreach.id)
    assert parent.follow_up_number == 0
    assert parent.next_follow_up_at is not None
