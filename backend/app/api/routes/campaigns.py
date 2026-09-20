"""Campaigns and outreach analytics.

A campaign groups outreach for organisation and reporting. It never sends
anything and has no scheduling behaviour.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, status

from app.api.deps import SessionDep
from app.core.errors import NotFoundError
from app.models import Opportunity, Target
from app.models.enums import AuditAction, OutcomeStatus, OutreachStatus
from app.repositories.outreach import (
    CampaignRepository,
    OutreachRepository,
    OutreachVersionRepository,
)
from app.repositories.research import OpportunityRepository
from app.schemas.outreach import (
    CampaignCreate,
    CampaignRead,
    CampaignUpdate,
    OutreachAnalytics,
    PrepareOutreachRequest,
    PrepareOutreachResponse,
)
from app.services import audit
from app.services.outreach_serialization import outreach_to_schema
from app.services.outreach_service import OutreachService

router = APIRouter(prefix="/api", tags=["campaigns"])

#: Below this many sent messages a percentage is noise, so none is shown.
MIN_SAMPLE_FOR_RATE = 10


def _campaign_to_schema(campaign, stats: dict[str, int]) -> CampaignRead:
    payload = CampaignRead.model_validate(campaign, from_attributes=True)
    target = getattr(campaign, "target", None)
    payload.target_name = target.name if target else None
    payload.outreach_counts = stats
    payload.outreach_total = sum(stats.values())
    return payload


@router.get("/campaigns", response_model=list[CampaignRead])
async def list_campaigns(session: SessionDep):
    repo = CampaignRepository(session)
    campaigns = await repo.list()
    stats = await repo.stats([campaign.id for campaign in campaigns])
    return [_campaign_to_schema(campaign, stats.get(campaign.id, {})) for campaign in campaigns]


@router.post("/campaigns", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(payload: CampaignCreate, session: SessionDep):
    if payload.target_id is not None and await session.get(Target, payload.target_id) is None:
        raise NotFoundError(f"Target {payload.target_id} not found")

    service = OutreachService(session)
    sender = await service.ensure_sender_profile()

    campaign = await CampaignRepository(session).create(
        **payload.model_dump(), sender_profile_id=sender.id, owner=sender.name
    )
    await audit.record(
        session,
        action=AuditAction.CAMPAIGN_CREATED,
        object_type="campaign",
        object_id=campaign.id,
        actor=sender.name,
        detail={"name": campaign.name},
    )
    await session.commit()
    return _campaign_to_schema(await CampaignRepository(session).get(campaign.id), {})


@router.get("/campaigns/{campaign_id}", response_model=CampaignRead)
async def get_campaign(campaign_id: int, session: SessionDep):
    repo = CampaignRepository(session)
    campaign = await repo.get(campaign_id)
    if campaign is None:
        raise NotFoundError(f"Campaign {campaign_id} not found")
    stats = await repo.stats([campaign_id])
    return _campaign_to_schema(campaign, stats.get(campaign_id, {}))


@router.patch("/campaigns/{campaign_id}", response_model=CampaignRead)
async def update_campaign(campaign_id: int, payload: CampaignUpdate, session: SessionDep):
    repo = CampaignRepository(session)
    campaign = await repo.get(campaign_id)
    if campaign is None:
        raise NotFoundError(f"Campaign {campaign_id} not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(campaign, key, value)
    await session.commit()
    stats = await repo.stats([campaign_id])
    return _campaign_to_schema(await repo.get(campaign_id), stats.get(campaign_id, {}))


@router.post(
    "/campaigns/{campaign_id}/prepare",
    response_model=PrepareOutreachResponse,
    status_code=status.HTTP_201_CREATED,
)
async def prepare_campaign_outreach(
    campaign_id: int, payload: PrepareOutreachRequest, session: SessionDep
):
    """Create review-stage drafts for the selected opportunities.

    Nothing is approved and nothing is sent — every draft still needs a human.
    """
    campaign = await CampaignRepository(session).get(campaign_id)
    if campaign is None:
        raise NotFoundError(f"Campaign {campaign_id} not found")

    service = OutreachService(session)
    repo = OutreachRepository(session)

    created = []
    skipped: list[dict] = []

    for opportunity_id in payload.opportunity_ids:
        opportunity = await session.get(Opportunity, opportunity_id)
        if opportunity is None:
            skipped.append({"opportunity_id": opportunity_id, "reason": "Opportunity not found"})
            continue
        if opportunity.status == "dismissed":
            skipped.append(
                {
                    "opportunity_id": opportunity_id,
                    "reason": "This opportunity was dismissed by a reviewer",
                }
            )
            continue

        existing = await repo.existing_for(
            opportunity_id=opportunity_id, decision_maker_id=None
        )
        outreach = await service.create_from_opportunity(
            opportunity_id=opportunity_id,
            campaign_id=campaign_id,
            tone=campaign.tone,
            message_length=campaign.message_length,
        )
        if existing is not None and existing.id == outreach.id:
            skipped.append(
                {
                    "opportunity_id": opportunity_id,
                    "reason": "An outreach already exists for this opportunity",
                    "outreach_id": outreach.id,
                }
            )
            continue

        # Attach to this campaign even when it was created outside one.
        if outreach.campaign_id != campaign_id:
            outreach.campaign_id = campaign_id
            await session.commit()
        created.append(outreach_to_schema(await repo.get(outreach.id)))

    return PrepareOutreachResponse(created=created, skipped=skipped)


@router.get("/outreach-analytics", response_model=OutreachAnalytics)
async def outreach_analytics(session: SessionDep):
    """Real counts from the database. Rates are withheld below a usable sample."""
    outreach_repo = OutreachRepository(session)
    by_status = await outreach_repo.count_by_status()
    by_outcome = await outreach_repo.count_by_outcome()
    now = datetime.now(UTC)

    total = await outreach_repo.count_all()
    approved = (
        by_status.get(OutreachStatus.APPROVED, 0)
        + by_status.get(OutreachStatus.GMAIL_DRAFT_CREATED, 0)
        + by_status.get(OutreachStatus.SENT, 0)
        + by_status.get(OutreachStatus.FOLLOW_UP_DUE, 0)
        + by_status.get(OutreachStatus.COMPLETED, 0)
    )
    marked_sent = (
        by_status.get(OutreachStatus.SENT, 0)
        + by_status.get(OutreachStatus.FOLLOW_UP_DUE, 0)
        + by_status.get(OutreachStatus.COMPLETED, 0)
    )
    replies = (
        by_outcome.get(OutcomeStatus.REPLIED, 0)
        + by_outcome.get(OutcomeStatus.INTERESTED, 0)
        + by_outcome.get(OutcomeStatus.NOT_INTERESTED, 0)
        + by_outcome.get(OutcomeStatus.MEETING_SCHEDULED, 0)
    )

    reviewed = approved + by_status.get(OutreachStatus.REJECTED, 0)
    approval_rate = round(approved / reviewed, 3) if reviewed >= MIN_SAMPLE_FOR_RATE else None
    reply_rate = (
        round(replies / marked_sent, 3) if marked_sent >= MIN_SAMPLE_FOR_RATE else None
    )

    notes = []
    if approval_rate is None and reviewed:
        notes.append(f"Approval rate is hidden below {MIN_SAMPLE_FOR_RATE} reviewed messages.")
    if reply_rate is None and marked_sent:
        notes.append(f"Reply rate is hidden below {MIN_SAMPLE_FOR_RATE} sent messages.")

    return OutreachAnalytics(
        opportunities_total=await OpportunityRepository(session).count_all(),
        outreach_total=total,
        by_status=by_status,
        by_outcome=by_outcome,
        drafts=by_status.get(OutreachStatus.DRAFT, 0),
        awaiting_review=by_status.get(OutreachStatus.REVIEW, 0),
        approved=approved,
        gmail_drafts=by_status.get(OutreachStatus.GMAIL_DRAFT_CREATED, 0),
        marked_sent=marked_sent,
        follow_ups_due=await outreach_repo.count_follow_ups_due(now),
        replies=replies,
        meetings=by_outcome.get(OutcomeStatus.MEETING_SCHEDULED, 0),
        won=by_outcome.get(OutcomeStatus.OPPORTUNITY_WON, 0),
        lost=by_outcome.get(OutcomeStatus.OPPORTUNITY_LOST, 0),
        edited_before_approval=await outreach_repo.count_edited(),
        versions_total=await OutreachVersionRepository(session).count_all(),
        approval_rate=approval_rate,
        reply_rate=reply_rate,
        rate_note=" ".join(notes) or None,
        recent=[outreach_to_schema(item, now=now) for item in await outreach_repo.recent()],
    )
