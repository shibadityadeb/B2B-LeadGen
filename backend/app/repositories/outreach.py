"""Persistence for Phase 3 objects."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Company,
    Opportunity,
    GmailConnection,
    Outreach,
    OutreachCampaign,
    OutreachClaim,
    OutreachOutcome,
    OutreachVersion,
    SenderProfile,
)
from app.models.enums import OutreachStatus


class SenderProfileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_default(self) -> SenderProfile | None:
        return await self.session.scalar(
            select(SenderProfile)
            .where(SenderProfile.is_default.is_(True))
            .order_by(SenderProfile.id)
            .limit(1)
        )

    async def get(self, profile_id: int) -> SenderProfile | None:
        return await self.session.get(SenderProfile, profile_id)

    async def list(self) -> list[SenderProfile]:
        return list(await self.session.scalars(select(SenderProfile).order_by(SenderProfile.id)))

    async def create(self, **fields) -> SenderProfile:
        profile = SenderProfile(**fields)
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def count(self) -> int:
        return int(await self.session.scalar(select(func.count(SenderProfile.id))) or 0)


class CampaignRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, campaign_id: int) -> OutreachCampaign | None:
        return await self.session.scalar(
            select(OutreachCampaign)
            .where(OutreachCampaign.id == campaign_id)
            .options(
                selectinload(OutreachCampaign.target),
                selectinload(OutreachCampaign.sender_profile),
            )
        )

    async def list(self) -> list[OutreachCampaign]:
        return list(
            await self.session.scalars(
                select(OutreachCampaign)
                .options(selectinload(OutreachCampaign.target))
                .order_by(OutreachCampaign.id.desc())
            )
        )

    async def create(self, **fields) -> OutreachCampaign:
        campaign = OutreachCampaign(**fields)
        self.session.add(campaign)
        await self.session.flush()
        return campaign

    async def stats(self, campaign_ids: list[int]) -> dict[int, dict[str, int]]:
        """Outreach counts per campaign, by status, in one query."""
        if not campaign_ids:
            return {}
        rows = await self.session.execute(
            select(Outreach.campaign_id, Outreach.status, func.count(Outreach.id))
            .where(Outreach.campaign_id.in_(campaign_ids))
            .group_by(Outreach.campaign_id, Outreach.status)
        )
        stats: dict[int, dict[str, int]] = {campaign_id: {} for campaign_id in campaign_ids}
        for campaign_id, status, count in rows:
            stats.setdefault(campaign_id, {})[status] = count
        return stats


class OutreachRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # The capability is nested behind the opportunity and is read during
    # serialization, so it must be eager-loaded too.
    _RELATIONS = (
        selectinload(Outreach.company),
        selectinload(Outreach.opportunity).selectinload(Opportunity.capability),
        selectinload(Outreach.decision_maker),
        selectinload(Outreach.campaign),
        selectinload(Outreach.sender_profile),
    )

    async def get(self, outreach_id: int) -> Outreach | None:
        return await self.session.scalar(
            select(Outreach).where(Outreach.id == outreach_id).options(*self._RELATIONS)
        )

    async def get_full(self, outreach_id: int) -> Outreach | None:
        return await self.session.scalar(
            select(Outreach)
            .where(Outreach.id == outreach_id)
            .options(
                *self._RELATIONS,
                selectinload(Outreach.versions).selectinload(OutreachVersion.claims),
                selectinload(Outreach.outcomes),
            )
        )

    async def create(self, **fields) -> Outreach:
        outreach = Outreach(**fields)
        self.session.add(outreach)
        await self.session.flush()
        return outreach

    async def existing_for(
        self, *, opportunity_id: int, decision_maker_id: int | None
    ) -> Outreach | None:
        """Used to avoid silently creating a second outreach for the same
        opportunity and person."""
        stmt = select(Outreach).where(
            Outreach.opportunity_id == opportunity_id,
            Outreach.follow_up_number == 0,
            Outreach.status != OutreachStatus.CANCELLED,
        )
        stmt = stmt.where(
            Outreach.decision_maker_id == decision_maker_id
            if decision_maker_id is not None
            else Outreach.decision_maker_id.is_(None)
        )
        return await self.session.scalar(stmt.order_by(Outreach.id.desc()).limit(1))

    def _filtered(
        self,
        stmt: Select,
        *,
        status: str | None,
        company_id: int | None,
        campaign_id: int | None,
        opportunity_id: int | None,
        owner: str | None,
        search: str | None,
        follow_up_due: bool | None,
        created_after: datetime | None,
        now: datetime | None,
    ) -> Select:
        if status:
            stmt = stmt.where(Outreach.status == status)
        if company_id is not None:
            stmt = stmt.where(Outreach.company_id == company_id)
        if campaign_id is not None:
            stmt = stmt.where(Outreach.campaign_id == campaign_id)
        if opportunity_id is not None:
            stmt = stmt.where(Outreach.opportunity_id == opportunity_id)
        if owner:
            stmt = stmt.where(Outreach.owner == owner)
        if created_after:
            stmt = stmt.where(Outreach.created_at >= created_after)
        if follow_up_due and now is not None:
            stmt = stmt.where(
                Outreach.next_follow_up_at.is_not(None),
                Outreach.next_follow_up_at <= now,
                Outreach.status.in_([OutreachStatus.SENT, OutreachStatus.FOLLOW_UP_DUE]),
            )
        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.join(Company, Company.id == Outreach.company_id).where(
                or_(
                    func.lower(Company.name).like(pattern),
                    func.lower(Company.canonical_domain).like(pattern),
                    func.lower(func.coalesce(Outreach.to_email, "")).like(pattern),
                    func.lower(func.coalesce(Outreach.to_name, "")).like(pattern),
                )
            )
        return stmt

    async def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        company_id: int | None = None,
        campaign_id: int | None = None,
        opportunity_id: int | None = None,
        owner: str | None = None,
        search: str | None = None,
        follow_up_due: bool | None = None,
        created_after: datetime | None = None,
        now: datetime | None = None,
    ) -> tuple[list[Outreach], int]:
        filters = {
            "status": status,
            "company_id": company_id,
            "campaign_id": campaign_id,
            "opportunity_id": opportunity_id,
            "owner": owner,
            "search": search,
            "follow_up_due": follow_up_due,
            "created_after": created_after,
            "now": now,
        }
        stmt = self._filtered(select(Outreach).options(*self._RELATIONS), **filters)
        stmt = stmt.order_by(Outreach.id.desc()).limit(page_size).offset((page - 1) * page_size)
        rows = list(await self.session.scalars(stmt))

        total = int(
            await self.session.scalar(
                self._filtered(select(func.count(Outreach.id)), **filters)
            )
            or 0
        )
        return rows, total

    async def count_by_status(self) -> dict[str, int]:
        rows = await self.session.execute(
            select(Outreach.status, func.count(Outreach.id)).group_by(Outreach.status)
        )
        return {row[0]: row[1] for row in rows}

    async def count_by_outcome(self) -> dict[str, int]:
        rows = await self.session.execute(
            select(Outreach.outcome_status, func.count(Outreach.id))
            .where(Outreach.outcome_status.is_not(None))
            .group_by(Outreach.outcome_status)
        )
        return {row[0]: row[1] for row in rows}

    async def count_follow_ups_due(self, now: datetime) -> int:
        return int(
            await self.session.scalar(
                select(func.count(Outreach.id)).where(
                    Outreach.next_follow_up_at.is_not(None),
                    Outreach.next_follow_up_at <= now,
                    Outreach.status.in_([OutreachStatus.SENT, OutreachStatus.FOLLOW_UP_DUE]),
                )
            )
            or 0
        )

    async def count_all(self) -> int:
        return int(await self.session.scalar(select(func.count(Outreach.id))) or 0)

    async def count_edited(self) -> int:
        return int(
            await self.session.scalar(
                select(func.count(Outreach.id)).where(Outreach.user_edited.is_(True))
            )
            or 0
        )

    async def recent(self, limit: int = 8) -> list[Outreach]:
        return list(
            await self.session.scalars(
                select(Outreach).options(*self._RELATIONS).order_by(Outreach.id.desc()).limit(limit)
            )
        )

    async def follow_ups_of(self, outreach_id: int) -> list[Outreach]:
        return list(
            await self.session.scalars(
                select(Outreach)
                .where(Outreach.parent_outreach_id == outreach_id)
                .order_by(Outreach.follow_up_number)
            )
        )


class OutreachVersionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for(self, outreach_id: int) -> list[OutreachVersion]:
        return list(
            await self.session.scalars(
                select(OutreachVersion)
                .where(OutreachVersion.outreach_id == outreach_id)
                .options(selectinload(OutreachVersion.claims).selectinload(OutreachClaim.evidence_links))
                .order_by(OutreachVersion.version_number)
            )
        )

    async def get(self, version_id: int) -> OutreachVersion | None:
        return await self.session.scalar(
            select(OutreachVersion)
            .where(OutreachVersion.id == version_id)
            .options(selectinload(OutreachVersion.claims).selectinload(OutreachClaim.evidence_links))
        )

    async def next_number(self, outreach_id: int) -> int:
        current = await self.session.scalar(
            select(func.max(OutreachVersion.version_number)).where(
                OutreachVersion.outreach_id == outreach_id
            )
        )
        return int(current or 0) + 1

    async def deactivate_all(self, outreach_id: int) -> None:
        for version in await self.list_for(outreach_id):
            version.is_active = False
        await self.session.flush()

    async def count_all(self) -> int:
        return int(await self.session.scalar(select(func.count(OutreachVersion.id))) or 0)


class OutcomeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for(self, outreach_id: int) -> list[OutreachOutcome]:
        return list(
            await self.session.scalars(
                select(OutreachOutcome)
                .where(OutreachOutcome.outreach_id == outreach_id)
                .order_by(OutreachOutcome.id)
            )
        )


class GmailConnectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def active(self) -> GmailConnection | None:
        return await self.session.scalar(
            select(GmailConnection)
            .where(GmailConnection.is_active.is_(True))
            .order_by(GmailConnection.id.desc())
            .limit(1)
        )

    async def by_email(self, email: str) -> GmailConnection | None:
        return await self.session.scalar(
            select(GmailConnection).where(GmailConnection.account_email == email)
        )

    async def deactivate_all(self) -> None:
        rows = await self.session.scalars(
            select(GmailConnection).where(GmailConnection.is_active.is_(True))
        )
        for row in rows:
            row.is_active = False
        await self.session.flush()
