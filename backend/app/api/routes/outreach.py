"""Phase 3 API: outreach, versions, approval, Gmail drafts, follow-ups.

There is no send endpoint. Sending is something the user does in their own
mail client.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Query, status

from app.api.deps import SessionDep
from app.core.errors import NotFoundError
from app.models import Opportunity
from app.models.enums import OutreachStatus
from app.repositories.outreach import (
    OutreachRepository,
    OutreachVersionRepository,
    SenderProfileRepository,
)
from app.schemas.common import Page
from app.schemas.outreach import (
    ActivateVersionRequest,
    GmailDraftRequest,
    MarkSentRequest,
    OutcomeUpdate,
    OutreachCreate,
    OutreachDetail,
    OutreachOutcomeRead,
    OutreachRead,
    OutreachUpdate,
    RegenerateRequest,
    RejectRequest,
    SenderProfileRead,
    SenderProfileUpdate,
)
from app.services import audit
from app.services.outreach_serialization import outreach_to_schema, version_to_schema
from app.services.outreach_service import OutreachService

router = APIRouter(prefix="/api", tags=["outreach"])


async def _require(session, outreach_id: int):
    outreach = await OutreachRepository(session).get(outreach_id)
    if outreach is None:
        raise NotFoundError(f"Outreach {outreach_id} not found")
    return outreach


# --------------------------------------------------------------------------- #
# creating outreach
# --------------------------------------------------------------------------- #


@router.post(
    "/opportunities/{opportunity_id}/outreach",
    response_model=OutreachRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_outreach(
    opportunity_id: int, payload: OutreachCreate, session: SessionDep
):
    """Prepare an outreach for review. Nothing is sent and no Gmail draft is
    created here."""
    opportunity = await session.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise NotFoundError(f"Opportunity {opportunity_id} not found")

    service = OutreachService(session)
    outreach = await service.create_from_opportunity(
        opportunity_id=opportunity_id,
        decision_maker_id=payload.decision_maker_id,
        campaign_id=payload.campaign_id,
        tone=payload.tone,
        message_length=payload.message_length,
        objective=payload.objective,
    )
    refreshed = await OutreachRepository(session).get(outreach.id)
    return outreach_to_schema(refreshed)


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #


@router.get("/outreach", response_model=Page[OutreachRead])
async def list_outreach(
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    company_id: int | None = None,
    campaign_id: int | None = None,
    opportunity_id: int | None = None,
    owner: str | None = None,
    search: str | None = None,
    follow_up_due: bool | None = None,
    created_after: datetime | None = None,
):
    now = datetime.now(UTC)
    rows, total = await OutreachRepository(session).list_paginated(
        page=page,
        page_size=page_size,
        status=status_filter,
        company_id=company_id,
        campaign_id=campaign_id,
        opportunity_id=opportunity_id,
        owner=owner,
        search=search,
        follow_up_due=follow_up_due,
        created_after=created_after,
        now=now,
    )
    return Page[OutreachRead](
        items=[outreach_to_schema(row, now=now) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/outreach/{outreach_id}", response_model=OutreachDetail)
async def get_outreach(outreach_id: int, session: SessionDep):
    repo = OutreachRepository(session)
    outreach = await repo.get_full(outreach_id)
    if outreach is None:
        raise NotFoundError(f"Outreach {outreach_id} not found")

    versions = await OutreachVersionRepository(session).list_for(outreach_id)
    follow_ups = await repo.follow_ups_of(outreach_id)
    events = await audit.for_object(session, object_type="outreach", object_id=outreach_id)

    detail = OutreachDetail(**outreach_to_schema(outreach).model_dump())
    detail.versions = [await version_to_schema(session, version) for version in versions]
    detail.outcomes = [
        OutreachOutcomeRead.model_validate(outcome, from_attributes=True)
        for outcome in outreach.outcomes
    ]
    detail.follow_ups = [outreach_to_schema(item) for item in follow_ups]
    detail.audit = [
        {
            "id": event.id,
            "action": event.action,
            "actor": event.actor,
            "detail": event.detail,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]
    return detail


# --------------------------------------------------------------------------- #
# editing and versions
# --------------------------------------------------------------------------- #


@router.patch("/outreach/{outreach_id}", response_model=OutreachRead)
async def update_outreach(outreach_id: int, payload: OutreachUpdate, session: SessionDep):
    await _require(session, outreach_id)
    service = OutreachService(session)
    outreach = await service.apply_edit(
        outreach_id,
        subject=payload.subject,
        body=payload.body,
        to_email=payload.to_email,
        to_name=payload.to_name,
        cc=payload.cc,
        bcc=payload.bcc,
    )
    return outreach_to_schema(await OutreachRepository(session).get(outreach.id))


@router.post("/outreach/{outreach_id}/regenerate", response_model=OutreachRead)
async def regenerate_outreach(
    outreach_id: int, payload: RegenerateRequest, session: SessionDep
):
    await _require(session, outreach_id)
    service = OutreachService(session)
    outreach = await service.regenerate(
        outreach_id,
        tone=payload.tone,
        message_length=payload.message_length,
        objective=payload.objective,
    )
    return outreach_to_schema(await OutreachRepository(session).get(outreach.id))


@router.post("/outreach/{outreach_id}/reset", response_model=OutreachRead)
async def reset_to_generated(outreach_id: int, session: SessionDep):
    """Discard hand edits and restore the generated text."""
    outreach = await _require(session, outreach_id)
    service = OutreachService(session)
    updated = await service.apply_edit(
        outreach_id,
        subject=outreach.ai_generated_subject,
        body=outreach.ai_generated_body,
    )
    updated.user_edited = False
    await session.commit()
    return outreach_to_schema(await OutreachRepository(session).get(updated.id))


@router.post("/outreach/{outreach_id}/versions/activate", response_model=OutreachRead)
async def activate_version(
    outreach_id: int, payload: ActivateVersionRequest, session: SessionDep
):
    service = OutreachService(session)
    outreach = await service.activate_version(outreach_id, payload.version_id)
    return outreach_to_schema(await OutreachRepository(session).get(outreach.id))


# --------------------------------------------------------------------------- #
# approval
# --------------------------------------------------------------------------- #


@router.post("/outreach/{outreach_id}/approve", response_model=OutreachRead)
async def approve_outreach(outreach_id: int, session: SessionDep):
    service = OutreachService(session)
    outreach = await service.approve(outreach_id)
    return outreach_to_schema(await OutreachRepository(session).get(outreach.id))


@router.post("/outreach/{outreach_id}/reject", response_model=OutreachRead)
async def reject_outreach(outreach_id: int, payload: RejectRequest, session: SessionDep):
    service = OutreachService(session)
    outreach = await service.reject(outreach_id, reason=payload.reason)
    return outreach_to_schema(await OutreachRepository(session).get(outreach.id))


@router.post("/outreach/{outreach_id}/cancel", response_model=OutreachRead)
async def cancel_outreach(outreach_id: int, session: SessionDep):
    service = OutreachService(session)
    outreach = await service.cancel(outreach_id)
    return outreach_to_schema(await OutreachRepository(session).get(outreach.id))


# --------------------------------------------------------------------------- #
# gmail draft and manual send tracking
# --------------------------------------------------------------------------- #


@router.post("/outreach/{outreach_id}/gmail-draft", response_model=OutreachRead)
async def create_gmail_draft(
    outreach_id: int, payload: GmailDraftRequest, session: SessionDep
):
    """Create a draft in the connected mailbox. This never sends anything."""
    service = OutreachService(session)
    outreach = await service.create_gmail_draft(outreach_id, force_new=payload.force_new)
    return outreach_to_schema(await OutreachRepository(session).get(outreach.id))


@router.post("/outreach/{outreach_id}/mark-sent", response_model=OutreachRead)
async def mark_sent(outreach_id: int, payload: MarkSentRequest, session: SessionDep):
    """Record that the user sent the message themselves."""
    service = OutreachService(session)
    outreach = await service.mark_sent(outreach_id, sent_at=payload.sent_at)
    return outreach_to_schema(await OutreachRepository(session).get(outreach.id))


# --------------------------------------------------------------------------- #
# follow-ups and outcomes
# --------------------------------------------------------------------------- #


@router.post(
    "/outreach/{outreach_id}/follow-up-draft",
    response_model=OutreachRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_follow_up_draft(outreach_id: int, session: SessionDep):
    service = OutreachService(session)
    follow_up = await service.create_follow_up(outreach_id)
    return outreach_to_schema(await OutreachRepository(session).get(follow_up.id))


@router.patch("/outreach/{outreach_id}/outcome", response_model=OutreachRead)
async def update_outcome(outreach_id: int, payload: OutcomeUpdate, session: SessionDep):
    service = OutreachService(session)
    outreach = await service.record_outcome(
        outreach_id, status=payload.status, reason=payload.reason, notes=payload.notes
    )
    return outreach_to_schema(await OutreachRepository(session).get(outreach.id))


# --------------------------------------------------------------------------- #
# sender profile
# --------------------------------------------------------------------------- #


@router.get("/sender-profile", response_model=SenderProfileRead)
async def get_sender_profile(session: SessionDep):
    return await OutreachService(session).ensure_sender_profile()


@router.patch("/sender-profile", response_model=SenderProfileRead)
async def update_sender_profile(payload: SenderProfileUpdate, session: SessionDep):
    service = OutreachService(session)
    profile = await service.ensure_sender_profile()
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    await session.commit()
    await session.refresh(profile)
    return profile
