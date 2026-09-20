from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, CompanySource, DiscoveryRun, Target


class TargetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **fields) -> Target:
        target = Target(**fields)
        self.session.add(target)
        await self.session.flush()
        return target

    async def get(self, target_id: int) -> Target | None:
        return await self.session.get(Target, target_id)

    async def list(self) -> list[Target]:
        result = await self.session.scalars(select(Target).order_by(Target.id.desc()))
        return list(result)

    async def count(self) -> int:
        return int(await self.session.scalar(select(func.count(Target.id))) or 0)

    async def delete(self, target: Target) -> None:
        await self.session.delete(target)

    async def stats(self, target_ids: list[int]) -> dict[int, dict]:
        """Company counts and latest-run info for a set of targets, in two queries."""
        if not target_ids:
            return {}

        company_rows = await self.session.execute(
            select(
                CompanySource.target_id,
                func.count(func.distinct(CompanySource.company_id)),
            )
            .where(CompanySource.target_id.in_(target_ids))
            .group_by(CompanySource.target_id)
        )
        companies = {row[0]: row[1] for row in company_rows}

        latest_run_id = (
            select(func.max(DiscoveryRun.id))
            .where(DiscoveryRun.target_id.in_(target_ids))
            .group_by(DiscoveryRun.target_id)
            .scalar_subquery()
        )
        runs = await self.session.scalars(
            select(DiscoveryRun).where(DiscoveryRun.id.in_(latest_run_id))
        )

        stats: dict[int, dict] = {
            target_id: {
                "companies_count": companies.get(target_id, 0),
                "last_run": None,
            }
            for target_id in target_ids
        }
        for run in runs:
            stats[run.target_id]["last_run"] = run
        return stats
