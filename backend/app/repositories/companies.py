from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Company, CompanyPage, CompanySource
from app.models.enums import CompanyStatus


class CompanyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, company_id: int) -> Company | None:
        return await self.session.get(Company, company_id)

    async def get_with_relations(self, company_id: int) -> Company | None:
        return await self.session.scalar(
            select(Company)
            .where(Company.id == company_id)
            .options(selectinload(Company.sources), selectinload(Company.pages))
        )

    async def get_by_domain(self, domain: str) -> Company | None:
        return await self.session.scalar(
            select(Company).where(Company.canonical_domain == domain)
        )

    async def get_by_domains(self, domains: list[str]) -> dict[str, Company]:
        if not domains:
            return {}
        rows = await self.session.scalars(
            select(Company).where(Company.canonical_domain.in_(domains))
        )
        return {company.canonical_domain: company for company in rows}

    async def create(self, **fields) -> Company:
        company = Company(**fields)
        self.session.add(company)
        await self.session.flush()
        return company

    async def count(self, *, status: str | None = None) -> int:
        stmt = select(func.count(Company.id))
        if status:
            stmt = stmt.where(Company.status == status)
        return int(await self.session.scalar(stmt) or 0)

    async def count_researched(self) -> int:
        return int(
            await self.session.scalar(
                select(func.count(Company.id)).where(Company.last_researched_at.is_not(None))
            )
            or 0
        )

    def _apply_filters(
        self,
        stmt: Select,
        *,
        search: str | None,
        industry: str | None,
        location: str | None,
        status: str | None,
        target_id: int | None,
        discovered_after: datetime | None,
        discovered_before: datetime | None,
    ) -> Select:
        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Company.name).like(pattern),
                    func.lower(Company.canonical_domain).like(pattern),
                )
            )
        if industry:
            stmt = stmt.where(func.lower(Company.industry) == industry.strip().lower())
        if location:
            stmt = stmt.where(func.lower(Company.location) == location.strip().lower())
        if status:
            stmt = stmt.where(Company.status == status)
        if target_id is not None:
            stmt = stmt.where(
                select(CompanySource.id)
                .where(
                    CompanySource.company_id == Company.id,
                    CompanySource.target_id == target_id,
                )
                .exists()
            )
        if discovered_after:
            stmt = stmt.where(Company.created_at >= discovered_after)
        if discovered_before:
            stmt = stmt.where(Company.created_at <= discovered_before)
        return stmt

    async def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        industry: str | None = None,
        location: str | None = None,
        status: str | None = None,
        target_id: int | None = None,
        discovered_after: datetime | None = None,
        discovered_before: datetime | None = None,
    ) -> tuple[list[tuple[Company, int]], int]:
        """Return (company, source_count) rows for one page, plus the total count."""
        filters = {
            "search": search,
            "industry": industry,
            "location": location,
            "status": status,
            "target_id": target_id,
            "discovered_after": discovered_after,
            "discovered_before": discovered_before,
        }

        source_count = (
            select(func.count(CompanySource.id))
            .where(CompanySource.company_id == Company.id)
            .correlate(Company)
            .scalar_subquery()
        )

        stmt = self._apply_filters(select(Company, source_count), **filters)
        stmt = stmt.order_by(Company.id.desc()).limit(page_size).offset((page - 1) * page_size)

        rows = (await self.session.execute(stmt)).all()
        total = int(
            await self.session.scalar(
                self._apply_filters(select(func.count(Company.id)), **filters)
            )
            or 0
        )
        return [(row[0], row[1]) for row in rows], total

    async def recent(self, limit: int = 5) -> list[Company]:
        rows = await self.session.scalars(
            select(Company).order_by(Company.id.desc()).limit(limit)
        )
        return list(rows)

    async def distinct_values(self, column) -> list[str]:
        rows = await self.session.scalars(
            select(column).where(column.is_not(None)).distinct().order_by(column)
        )
        return [value for value in rows if value]

    async def set_status(self, company: Company, status: CompanyStatus, error: str | None = None):
        company.status = status
        company.crawl_error = error
        await self.session.flush()


class CompanySourceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def existing_urls(self, company_id: int, urls: list[str]) -> set[str]:
        if not urls:
            return set()
        rows = await self.session.scalars(
            select(CompanySource.url).where(
                CompanySource.company_id == company_id, CompanySource.url.in_(urls)
            )
        )
        return set(rows)

    async def list_for_company(self, company_id: int) -> list[CompanySource]:
        rows = await self.session.scalars(
            select(CompanySource)
            .where(CompanySource.company_id == company_id)
            .order_by(CompanySource.id)
        )
        return list(rows)

    async def count_all(self) -> int:
        return int(await self.session.scalar(select(func.count(CompanySource.id))) or 0)

    def add(self, **fields) -> CompanySource:
        source = CompanySource(**fields)
        self.session.add(source)
        return source


class CompanyPageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_company(self, company_id: int) -> list[CompanyPage]:
        rows = await self.session.scalars(
            select(CompanyPage).where(CompanyPage.company_id == company_id).order_by(CompanyPage.id)
        )
        return list(rows)

    async def get_by_url(self, company_id: int, url: str) -> CompanyPage | None:
        return await self.session.scalar(
            select(CompanyPage).where(
                CompanyPage.company_id == company_id, CompanyPage.url == url
            )
        )

    async def upsert(self, *, company_id: int, url: str, **fields) -> CompanyPage:
        """Idempotent: re-crawling a URL updates the existing row."""
        page = await self.get_by_url(company_id, url)
        if page is None:
            page = CompanyPage(company_id=company_id, url=url, **fields)
            self.session.add(page)
        else:
            for key, value in fields.items():
                setattr(page, key, value)
        await self.session.flush()
        return page

    async def count_all(self) -> int:
        return int(await self.session.scalar(select(func.count(CompanyPage.id))) or 0)
