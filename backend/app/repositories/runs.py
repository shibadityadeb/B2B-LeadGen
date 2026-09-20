from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import DiscoveryRun, SearchQuery, SearchResult
from app.models.enums import RunStatus


class DiscoveryRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, *, target_id: int, search_provider: str) -> DiscoveryRun:
        run = DiscoveryRun(
            target_id=target_id,
            status=RunStatus.QUEUED,
            search_provider=search_provider,
            errors=[],
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get(self, run_id: int) -> DiscoveryRun | None:
        return await self.session.get(DiscoveryRun, run_id)

    async def get_with_target(self, run_id: int) -> DiscoveryRun | None:
        return await self.session.scalar(
            select(DiscoveryRun)
            .where(DiscoveryRun.id == run_id)
            .options(selectinload(DiscoveryRun.target))
        )

    async def list(self, *, limit: int = 50, offset: int = 0, target_id: int | None = None):
        stmt = (
            select(DiscoveryRun)
            .options(selectinload(DiscoveryRun.target))
            .order_by(DiscoveryRun.id.desc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = select(func.count(DiscoveryRun.id))
        if target_id is not None:
            stmt = stmt.where(DiscoveryRun.target_id == target_id)
            count_stmt = count_stmt.where(DiscoveryRun.target_id == target_id)

        runs = list(await self.session.scalars(stmt))
        total = int(await self.session.scalar(count_stmt) or 0)
        return runs, total

    async def queries_for_run(self, run_id: int) -> list[SearchQuery]:
        result = await self.session.scalars(
            select(SearchQuery).where(SearchQuery.discovery_run_id == run_id).order_by(SearchQuery.id)
        )
        return list(result)

    async def results_for_run(self, run_id: int, *, limit: int = 200) -> list[SearchResult]:
        result = await self.session.scalars(
            select(SearchResult)
            .where(SearchResult.discovery_run_id == run_id)
            .order_by(SearchResult.id)
            .limit(limit)
        )
        return list(result)

    async def count_by_status(self) -> dict[str, int]:
        rows = await self.session.execute(
            select(DiscoveryRun.status, func.count(DiscoveryRun.id)).group_by(DiscoveryRun.status)
        )
        return {row[0]: row[1] for row in rows}
