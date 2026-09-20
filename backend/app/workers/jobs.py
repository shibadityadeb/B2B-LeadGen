"""Job handlers. Thin wrappers that delegate to services."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.crawl import CrawlService
from app.services.discovery import DiscoveryService
from app.services.research_orchestrator import ResearchOrchestrator
from app.workers.queue import register_job

DISCOVERY_JOB = "discovery.run"
CRAWL_JOB = "company.crawl"
RESEARCH_JOB = "company.research"


@register_job(DISCOVERY_JOB)
async def run_discovery_job(session: AsyncSession, payload: dict) -> None:
    await DiscoveryService(session).execute_run(int(payload["run_id"]))


@register_job(CRAWL_JOB)
async def run_crawl_job(session: AsyncSession, payload: dict) -> None:
    await CrawlService(session).crawl_company(int(payload["company_id"]))


@register_job(RESEARCH_JOB)
async def run_research_job(session: AsyncSession, payload: dict) -> None:
    await ResearchOrchestrator(session).execute(int(payload["run_id"]))
