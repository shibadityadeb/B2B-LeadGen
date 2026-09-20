"""Initial company-website crawl.

Deliberately shallow: fetch the homepage, pick a handful of standard
corporate pages from its navigation, store what was actually returned.
No inference, no content generation.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.models import Company
from app.models.enums import CompanyStatus, CrawlStatus, PageType, SourceType
from app.providers.crawler.base import CrawlerProvider
from app.providers.crawler.registry import get_crawler_provider
from app.repositories.companies import (
    CompanyPageRepository,
    CompanyRepository,
    CompanySourceRepository,
)
from app.services.normalization import extract_domain, normalize_url, root_url
from app.services.page_classifier import CRAWL_PRIORITY, classify_page
from app.services.robots import RobotsPolicy

logger = get_logger(__name__)


class CrawlService:
    def __init__(self, session: AsyncSession, provider: CrawlerProvider | None = None):
        self.session = session
        self.companies = CompanyRepository(session)
        self.pages = CompanyPageRepository(session)
        self.sources = CompanySourceRepository(session)
        self._provider = provider

    @property
    def provider(self) -> CrawlerProvider:
        if self._provider is None:
            self._provider = get_crawler_provider()
        return self._provider

    async def request_crawl(self, company: Company) -> Company:
        """Mark a company as queued for research; the job queue does the work."""
        company.status = CompanyStatus.RESEARCHING
        company.crawl_error = None
        await self.session.commit()
        # `updated_at` is recomputed by the database on UPDATE, so reload the
        # row before it is serialized into the response.
        await self.session.refresh(company)
        return company

    async def crawl_company(self, company_id: int) -> Company:
        company = await self.companies.get(company_id)
        if company is None:
            raise NotFoundError(f"Company {company_id} not found")

        start_url = root_url(company.website_url) or company.website_url
        domain = company.canonical_domain
        robots = RobotsPolicy()

        company.status = CompanyStatus.RESEARCHING
        company.crawl_error = None
        await self.session.commit()

        try:
            pages_retrieved, failures = await self._crawl(company, start_url, domain, robots)
        except Exception as exc:
            logger.exception("crawl crashed company=%s", company_id)
            company.status = CompanyStatus.RESEARCH_FAILED
            company.crawl_error = f"{type(exc).__name__}: {exc}"
            company.last_researched_at = datetime.now(UTC)
            await self.session.commit()
            raise

        company.last_researched_at = datetime.now(UTC)
        if pages_retrieved == 0:
            company.status = CompanyStatus.RESEARCH_FAILED
            company.crawl_error = failures[0] if failures else "No pages could be retrieved."
        else:
            company.status = CompanyStatus.RESEARCHED
            company.crawl_error = None
            await self._backfill_description(company)
        await self.session.commit()

        logger.info(
            "crawl finished company=%s retrieved=%s failures=%s",
            company_id, pages_retrieved, len(failures),
        )
        return company

    # ------------------------------------------------------------------ #

    async def _crawl(
        self, company: Company, start_url: str, domain: str, robots: RobotsPolicy
    ) -> tuple[int, list[str]]:
        """Returns (pages successfully retrieved, failure messages).

        Attempts are what the page budget is spent on; successes are what
        decides whether the company counts as researched.
        """
        delay = max(settings.crawl_delay_seconds, await robots.crawl_delay(start_url) or 0.0)
        max_pages = max(1, settings.crawl_max_pages)

        attempted = 0
        retrieved = 0
        failures: list[str] = []
        visited: set[str] = set()

        queue: list[tuple[str, PageType]] = [(start_url, PageType.HOME)]
        discovered_links: list[str] = []

        while queue and attempted < max_pages:
            url, page_type = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            if not await robots.can_fetch(url):
                await self._record_skip(company.id, url, page_type, "Disallowed by robots.txt")
                continue

            page = await self.provider.fetch(url)
            attempted += 1

            if not page.ok:
                failures.append(page.error or "Unknown crawl error")
                await self.pages.upsert(
                    company_id=company.id,
                    url=url,
                    page_type=page_type,
                    title=None,
                    content=None,
                    content_length=0,
                    status=CrawlStatus.FAILED,
                    http_status=page.http_status,
                    error_message=page.error,
                    crawled_at=datetime.now(UTC),
                )
            else:
                retrieved += 1
                text = page.text or ""
                await self.pages.upsert(
                    company_id=company.id,
                    url=url,
                    page_type=page_type,
                    title=page.title,
                    content=text or None,
                    content_length=len(text),
                    status=CrawlStatus.SUCCESS,
                    http_status=page.http_status,
                    error_message=None,
                    crawled_at=datetime.now(UTC),
                )
                await self._record_source(company, page.url, page.title, page_type)
                if page_type == PageType.HOME:
                    discovered_links = page.links
                    queue.extend(
                        self._select_pages(discovered_links, domain, max_pages - attempted)
                    )

            await self.session.commit()
            if delay > 0 and queue and attempted < max_pages:
                await asyncio.sleep(delay)

        return retrieved, failures

    def _select_pages(
        self, links: list[str], domain: str, budget: int
    ) -> list[tuple[str, PageType]]:
        """Pick at most one on-domain page per interesting page type."""
        if budget <= 0:
            return []

        best: dict[PageType, str] = {}
        for link in links:
            normalized = normalize_url(link)
            if not normalized or extract_domain(normalized) != domain:
                continue
            page_type = classify_page(normalized)
            if page_type in (PageType.HOME, PageType.OTHER):
                continue
            # Shallower URLs are more likely to be the canonical section page.
            current = best.get(page_type)
            if current is None or normalized.count("/") < current.count("/"):
                best[page_type] = normalized

        ordered = [
            (best[page_type], page_type)
            for page_type in CRAWL_PRIORITY
            if page_type in best
        ]
        return ordered[:budget]

    async def _record_skip(self, company_id: int, url: str, page_type: PageType, reason: str):
        await self.pages.upsert(
            company_id=company_id,
            url=url,
            page_type=page_type,
            title=None,
            content=None,
            content_length=0,
            status=CrawlStatus.SKIPPED,
            http_status=None,
            error_message=reason,
            crawled_at=datetime.now(UTC),
        )
        await self.session.commit()

    async def _record_source(self, company: Company, url: str, title: str | None, page_type: PageType):
        normalized = normalize_url(url) or url
        if await self.sources.existing_urls(company.id, [normalized]):
            return
        self.sources.add(
            company_id=company.id,
            url=normalized,
            title=title,
            snippet=None,
            source_type=(
                SourceType.ABOUT_PAGE if page_type == PageType.ABOUT else SourceType.COMPANY_WEBSITE
            ),
            discovered_at=datetime.now(UTC),
        )
        await self.session.flush()

    async def _backfill_description(self, company: Company) -> None:
        """Use the homepage's own meta description text if we have none.

        Only verbatim website content is stored — nothing is synthesised.
        """
        if company.description:
            return
        pages = await self.pages.list_for_company(company.id)
        home = next(
            (page for page in pages if page.page_type == PageType.HOME and page.content), None
        )
        if not home or not home.content:
            return
        first_paragraph = next(
            (
                line.strip()
                for line in home.content.splitlines()
                if len(line.strip()) >= 80
            ),
            None,
        )
        if first_paragraph:
            company.description = first_paragraph[:500]
