from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ComponentStatus(BaseModel):
    name: str
    provider: str
    connected: bool
    detail: str | None = None
    optional: bool = False


class SystemStatus(BaseModel):
    healthy: bool
    environment: str
    components: list[ComponentStatus]
    configuration: dict


class RecentRunSummary(BaseModel):
    id: int
    target_id: int
    target_name: str
    industry: str
    location: str | None
    status: str
    progress: int
    companies_found: int
    created_at: datetime
    completed_at: datetime | None


class RecentCompanySummary(BaseModel):
    id: int
    name: str
    canonical_domain: str
    industry: str | None
    location: str | None
    status: str
    created_at: datetime


class DashboardStats(BaseModel):
    targets_count: int
    companies_count: int
    researched_count: int
    sources_count: int
    pages_count: int
    runs_count: int
    runs_by_status: dict[str, int]
    recent_runs: list[RecentRunSummary]
    recent_companies: list[RecentCompanySummary]
