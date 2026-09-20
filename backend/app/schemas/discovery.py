from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SearchQueryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query: str
    template: str | None
    provider: str | None
    status: str
    results_count: int
    error_message: str | None
    executed_at: datetime | None


class SearchResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    url: str
    snippet: str | None
    source_engine: str | None
    position: int | None
    extracted_domain: str | None
    accepted: bool
    rejection_reason: str | None
    discovered_at: datetime | None


class DiscoveryRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_id: int
    status: str
    stage: str
    progress: int
    search_provider: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    queries_count: int
    results_count: int
    unique_domains_count: int
    new_companies_count: int
    duplicate_companies_count: int
    rejected_results_count: int
    failed_queries_count: int

    error_message: str | None
    errors: list[dict] = []

    target_name: str | None = None
    target_industry: str | None = None
    target_location: str | None = None


class DiscoveryRunDetail(DiscoveryRunRead):
    queries: list[SearchQueryRead] = []
    results: list[SearchResultRead] = []
