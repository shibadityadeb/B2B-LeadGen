"""Persistence for Phase 2 objects.

The upsert helpers all key on a fingerprint so that repeated research updates
rows in place instead of accumulating near-duplicates — while still recording
that the observation was seen again, which is what change detection reads.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Contradiction,
    DecisionMaker,
    Evidence,
    Opportunity,
    OpportunityEvidence,
    OpportunitySignal,
    ResearchBrief,
    ResearchRun,
    ResearchSource,
    Signal,
    SignalEvidence,
    UbmCapability,
)
from app.models.enums import ObservationState, ResearchStatus


class ResearchRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, *, company_id: int, **fields) -> ResearchRun:
        run = ResearchRun(company_id=company_id, status=ResearchStatus.QUEUED, errors=[], **fields)
        self.session.add(run)
        await self.session.flush()
        return run

    async def get(self, run_id: int) -> ResearchRun | None:
        return await self.session.get(ResearchRun, run_id)

    async def get_with_company(self, run_id: int) -> ResearchRun | None:
        return await self.session.scalar(
            select(ResearchRun)
            .where(ResearchRun.id == run_id)
            .options(selectinload(ResearchRun.company))
        )

    async def latest_for_company(self, company_id: int) -> ResearchRun | None:
        return await self.session.scalar(
            select(ResearchRun)
            .where(ResearchRun.company_id == company_id)
            .order_by(ResearchRun.id.desc())
            .limit(1)
        )

    async def previous_completed(self, company_id: int, before_run_id: int) -> ResearchRun | None:
        return await self.session.scalar(
            select(ResearchRun)
            .where(
                ResearchRun.company_id == company_id,
                ResearchRun.id < before_run_id,
                ResearchRun.status == ResearchStatus.COMPLETED,
            )
            .order_by(ResearchRun.id.desc())
            .limit(1)
        )

    async def list_for_company(self, company_id: int, *, limit: int = 20) -> list[ResearchRun]:
        rows = await self.session.scalars(
            select(ResearchRun)
            .where(ResearchRun.company_id == company_id)
            .order_by(ResearchRun.id.desc())
            .limit(limit)
        )
        return list(rows)

    async def list_all(self, *, limit: int, offset: int) -> tuple[list[ResearchRun], int]:
        rows = list(
            await self.session.scalars(
                select(ResearchRun)
                .options(selectinload(ResearchRun.company))
                .order_by(ResearchRun.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        total = int(await self.session.scalar(select(func.count(ResearchRun.id))) or 0)
        return rows, total

    async def count_by_status(self) -> dict[str, int]:
        rows = await self.session.execute(
            select(ResearchRun.status, func.count(ResearchRun.id)).group_by(ResearchRun.status)
        )
        return {row[0]: row[1] for row in rows}


class ResearchSourceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_url(self, company_id: int, url: str) -> ResearchSource | None:
        return await self.session.scalar(
            select(ResearchSource).where(
                ResearchSource.company_id == company_id, ResearchSource.url == url
            )
        )

    async def upsert(self, *, company_id: int, url: str, **fields) -> tuple[ResearchSource, bool]:
        """Returns (source, created). One row per (company, url), updated in place."""
        existing = await self.get_by_url(company_id, url)
        if existing is None:
            source = ResearchSource(company_id=company_id, url=url, **fields)
            self.session.add(source)
            await self.session.flush()
            return source, True

        for key, value in fields.items():
            # Never overwrite retrieved content with nothing.
            if value is None and key in ("content", "content_hash", "title", "published_at"):
                continue
            setattr(existing, key, value)
        await self.session.flush()
        return existing, False

    async def list_for_company(self, company_id: int, *, limit: int = 200) -> list[ResearchSource]:
        rows = await self.session.scalars(
            select(ResearchSource)
            .where(ResearchSource.company_id == company_id)
            .order_by(ResearchSource.id.desc())
            .limit(limit)
        )
        return list(rows)

    async def count_for_company(self, company_id: int) -> int:
        return int(
            await self.session.scalar(
                select(func.count(ResearchSource.id)).where(
                    ResearchSource.company_id == company_id
                )
            )
            or 0
        )


class EvidenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_fingerprints(self, company_id: int, fingerprints: list[str]) -> dict[str, Evidence]:
        if not fingerprints:
            return {}
        rows = await self.session.scalars(
            select(Evidence).where(
                Evidence.company_id == company_id, Evidence.fingerprint.in_(fingerprints)
            )
        )
        return {item.fingerprint: item for item in rows}

    async def list_for_company(
        self, company_id: int, *, evidence_type: str | None = None, limit: int = 500
    ) -> list[Evidence]:
        stmt = (
            select(Evidence)
            .where(Evidence.company_id == company_id)
            .options(selectinload(Evidence.source))
            .order_by(Evidence.id)
            .limit(limit)
        )
        if evidence_type:
            stmt = stmt.where(Evidence.evidence_type == evidence_type)
        return list(await self.session.scalars(stmt))

    async def list_for_run(self, run_id: int) -> list[Evidence]:
        return list(
            await self.session.scalars(
                select(Evidence)
                .where(Evidence.research_run_id == run_id)
                .options(selectinload(Evidence.source))
                .order_by(Evidence.id)
            )
        )

    async def count_all(self) -> int:
        return int(await self.session.scalar(select(func.count(Evidence.id))) or 0)

    async def count_fresh(self, since: datetime) -> int:
        """Evidence whose *publication* date is recent — not merely re-observed."""
        return int(
            await self.session.scalar(
                select(func.count(Evidence.id)).where(Evidence.published_at >= since)
            )
            or 0
        )

    async def mark_not_found(self, company_id: int, seen_ids: set[int]) -> int:
        """Evidence that a fresh run no longer observed.

        The row is kept — only its state changes, so history is never lost.
        """
        rows = list(
            await self.session.scalars(
                select(Evidence).where(
                    Evidence.company_id == company_id,
                    Evidence.observation_state != ObservationState.NOT_FOUND,
                )
            )
        )
        changed = 0
        for row in rows:
            if row.id not in seen_ids:
                row.observation_state = ObservationState.NOT_FOUND
                changed += 1
        return changed


class SignalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_fingerprint(self, company_id: int, fingerprint: str) -> Signal | None:
        return await self.session.scalar(
            select(Signal).where(
                Signal.company_id == company_id, Signal.fingerprint == fingerprint
            )
        )

    async def list_for_company(self, company_id: int) -> list[Signal]:
        return list(
            await self.session.scalars(
                select(Signal)
                .where(Signal.company_id == company_id)
                .options(selectinload(Signal.evidence_links))
                .order_by(Signal.strength.desc(), Signal.id)
            )
        )

    async def replace_evidence_links(self, signal: Signal, evidence_ids: list[int]) -> None:
        existing = {link.evidence_id for link in signal.evidence_links}
        for evidence_id in evidence_ids:
            if evidence_id not in existing:
                self.session.add(
                    SignalEvidence(signal_id=signal.id, evidence_id=evidence_id)
                )
        await self.session.flush()

    async def count_all(self) -> int:
        return int(await self.session.scalar(select(func.count(Signal.id))) or 0)


class CapabilityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self, *, active_only: bool = False) -> list[UbmCapability]:
        stmt = select(UbmCapability).order_by(UbmCapability.name)
        if active_only:
            stmt = stmt.where(UbmCapability.active.is_(True))
        return list(await self.session.scalars(stmt))

    async def get(self, capability_id: int) -> UbmCapability | None:
        return await self.session.get(UbmCapability, capability_id)

    async def get_by_slug(self, slug: str) -> UbmCapability | None:
        return await self.session.scalar(
            select(UbmCapability).where(UbmCapability.slug == slug)
        )

    async def create(self, **fields) -> UbmCapability:
        capability = UbmCapability(**fields)
        self.session.add(capability)
        await self.session.flush()
        return capability

    async def count(self) -> int:
        return int(await self.session.scalar(select(func.count(UbmCapability.id))) or 0)


class OpportunityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_fingerprint(self, company_id: int, fingerprint: str) -> Opportunity | None:
        return await self.session.scalar(
            select(Opportunity).where(
                Opportunity.company_id == company_id, Opportunity.fingerprint == fingerprint
            )
        )

    async def list_for_company(self, company_id: int) -> list[Opportunity]:
        return list(
            await self.session.scalars(
                select(Opportunity)
                .where(Opportunity.company_id == company_id)
                .options(
                    selectinload(Opportunity.capability),
                    selectinload(Opportunity.evidence_links),
                    selectinload(Opportunity.signal_links),
                )
                .order_by(Opportunity.confidence.desc(), Opportunity.id)
            )
        )

    async def link(
        self, opportunity: Opportunity, *, evidence_ids: list[int], signal_ids: list[int]
    ) -> None:
        existing_evidence = {link.evidence_id for link in opportunity.evidence_links}
        for evidence_id in evidence_ids:
            if evidence_id not in existing_evidence:
                self.session.add(
                    OpportunityEvidence(opportunity_id=opportunity.id, evidence_id=evidence_id)
                )
        existing_signals = {link.signal_id for link in opportunity.signal_links}
        for signal_id in signal_ids:
            if signal_id not in existing_signals:
                self.session.add(
                    OpportunitySignal(opportunity_id=opportunity.id, signal_id=signal_id)
                )
        await self.session.flush()

    async def count_all(self) -> int:
        return int(await self.session.scalar(select(func.count(Opportunity.id))) or 0)


class DecisionMakerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_fingerprint(self, company_id: int, fingerprint: str) -> DecisionMaker | None:
        return await self.session.scalar(
            select(DecisionMaker).where(
                DecisionMaker.company_id == company_id,
                DecisionMaker.fingerprint == fingerprint,
            )
        )

    async def list_for_company(self, company_id: int) -> list[DecisionMaker]:
        return list(
            await self.session.scalars(
                select(DecisionMaker)
                .where(DecisionMaker.company_id == company_id)
                .options(selectinload(DecisionMaker.source))
                .order_by(DecisionMaker.confidence.desc(), DecisionMaker.id)
            )
        )

    async def count_all(self) -> int:
        return int(await self.session.scalar(select(func.count(DecisionMaker.id))) or 0)


class ContradictionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def exists(self, company_id: int, a_id: int, b_id: int) -> bool:
        found = await self.session.scalar(
            select(Contradiction.id).where(
                Contradiction.company_id == company_id,
                Contradiction.evidence_a_id == a_id,
                Contradiction.evidence_b_id == b_id,
            )
        )
        return found is not None

    async def list_for_company(self, company_id: int) -> list[Contradiction]:
        return list(
            await self.session.scalars(
                select(Contradiction)
                .where(Contradiction.company_id == company_id)
                .order_by(Contradiction.id)
            )
        )


class BriefRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def for_run(self, run_id: int) -> ResearchBrief | None:
        return await self.session.scalar(
            select(ResearchBrief).where(ResearchBrief.research_run_id == run_id)
        )

    async def latest_for_company(self, company_id: int) -> ResearchBrief | None:
        return await self.session.scalar(
            select(ResearchBrief)
            .where(ResearchBrief.company_id == company_id)
            .order_by(ResearchBrief.id.desc())
            .limit(1)
        )

    async def upsert(self, *, company_id: int, research_run_id: int, **fields) -> ResearchBrief:
        existing = await self.for_run(research_run_id)
        if existing is None:
            brief = ResearchBrief(
                company_id=company_id, research_run_id=research_run_id, **fields
            )
            self.session.add(brief)
            await self.session.flush()
            return brief
        for key, value in fields.items():
            setattr(existing, key, value)
        await self.session.flush()
        return existing


def utcnow() -> datetime:
    return datetime.now(UTC)
