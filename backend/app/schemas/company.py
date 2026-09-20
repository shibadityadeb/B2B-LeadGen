from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanySourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str | None
    snippet: str | None
    source_type: str
    source_engine: str | None
    discovery_run_id: int | None
    target_id: int | None
    discovered_at: datetime | None


class CompanyPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    page_type: str
    title: str | None
    content_length: int
    status: str
    http_status: int | None
    error_message: str | None
    crawled_at: datetime | None


class CompanyPageDetail(CompanyPageRead):
    content: str | None = None


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    canonical_domain: str
    website_url: str
    description: str | None
    industry: str | None
    location: str | None
    country: str | None
    company_size: str | None
    status: str
    crawl_error: str | None
    first_discovery_run_id: int | None
    last_researched_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CompanyListItem(CompanyRead):
    sources_count: int = 0


class CompanySummaryRead(BaseModel):
    pages_found: list[str] = []
    page_count: int = 0
    successful_pages: int = 0
    failed_pages: int = 0
    homepage_title: str | None = None
    total_content_chars: int = 0
    emails: list[str] = []
    phones: list[str] = []
    facts: list[str] = []


class CompanyDetail(CompanyRead):
    sources: list[CompanySourceRead] = []
    pages: list[CompanyPageRead] = []
    summary: CompanySummaryRead = CompanySummaryRead()


class CompanyFilterOptions(BaseModel):
    industries: list[str] = []
    locations: list[str] = []
    statuses: list[str] = []
