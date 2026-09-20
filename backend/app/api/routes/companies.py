from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query, status

from app.api.deps import QueueDep, SessionDep
from app.core.errors import NotFoundError
from app.models import Company
from app.repositories.companies import (
    CompanyPageRepository,
    CompanyRepository,
    CompanySourceRepository,
)
from app.schemas.common import Page
from app.schemas.company import (
    CompanyDetail,
    CompanyFilterOptions,
    CompanyListItem,
    CompanyPageDetail,
    CompanyPageRead,
    CompanyRead,
    CompanySourceRead,
    CompanySummaryRead,
)
from app.services.crawl import CrawlService
from app.services.summary import build_summary
from app.workers.jobs import CRAWL_JOB

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("", response_model=Page[CompanyListItem])
async def list_companies(
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    industry: str | None = None,
    location: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    target_id: int | None = None,
    discovered_after: datetime | None = None,
    discovered_before: datetime | None = None,
):
    rows, total = await CompanyRepository(session).list_paginated(
        page=page,
        page_size=page_size,
        search=search,
        industry=industry,
        location=location,
        status=status_filter,
        target_id=target_id,
        discovered_after=discovered_after,
        discovered_before=discovered_before,
    )
    items = [
        CompanyListItem(
            **CompanyRead.model_validate(company).model_dump(), sources_count=count
        )
        for company, count in rows
    ]
    return Page[CompanyListItem](items=items, total=total, page=page, page_size=page_size)


@router.get("/filters", response_model=CompanyFilterOptions)
async def company_filters(session: SessionDep):
    repo = CompanyRepository(session)
    return CompanyFilterOptions(
        industries=await repo.distinct_values(Company.industry),
        locations=await repo.distinct_values(Company.location),
        statuses=await repo.distinct_values(Company.status),
    )


@router.get("/{company_id}", response_model=CompanyDetail)
async def get_company(company_id: int, session: SessionDep):
    company = await CompanyRepository(session).get_with_relations(company_id)
    if company is None:
        raise NotFoundError(f"Company {company_id} not found")

    summary = build_summary(company, list(company.pages))
    return CompanyDetail(
        **CompanyRead.model_validate(company).model_dump(),
        sources=[CompanySourceRead.model_validate(source) for source in company.sources],
        pages=[CompanyPageRead.model_validate(page) for page in company.pages],
        summary=CompanySummaryRead(**summary.dict()),
    )


@router.get("/{company_id}/sources", response_model=list[CompanySourceRead])
async def get_company_sources(company_id: int, session: SessionDep):
    company = await CompanyRepository(session).get(company_id)
    if company is None:
        raise NotFoundError(f"Company {company_id} not found")
    return await CompanySourceRepository(session).list_for_company(company_id)


@router.get("/{company_id}/pages", response_model=list[CompanyPageRead])
async def get_company_pages(company_id: int, session: SessionDep):
    company = await CompanyRepository(session).get(company_id)
    if company is None:
        raise NotFoundError(f"Company {company_id} not found")
    return await CompanyPageRepository(session).list_for_company(company_id)


@router.get("/{company_id}/pages/{page_id}", response_model=CompanyPageDetail)
async def get_company_page(company_id: int, page_id: int, session: SessionDep):
    pages = await CompanyPageRepository(session).list_for_company(company_id)
    page = next((item for item in pages if item.id == page_id), None)
    if page is None:
        raise NotFoundError(f"Page {page_id} not found for company {company_id}")
    return page


@router.post(
    "/{company_id}/crawl", response_model=CompanyRead, status_code=status.HTTP_202_ACCEPTED
)
async def crawl_company(company_id: int, session: SessionDep, queue: QueueDep):
    company = await CompanyRepository(session).get(company_id)
    if company is None:
        raise NotFoundError(f"Company {company_id} not found")

    await CrawlService(session).request_crawl(company)
    await queue.enqueue(CRAWL_JOB, company_id=company.id)
    return company
