"""Finds public documents about a company using the configured search provider.

Queries are generated from the company's own attributes — no industry
branching — and target the kinds of pages that carry business events: news,
press releases, launches, expansion, events, hiring.
"""

from __future__ import annotations

import asyncio

from app.core.config import settings
from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.models.enums import ResearchSourceType
from app.providers.research.base import (
    ResearchCandidate,
    ResearchProviderStatus,
    ResearchSourceProvider,
)
from app.providers.search.base import SearchProvider
from app.providers.search.registry import get_search_provider
from app.services.normalization import extract_domain, is_excluded_domain, normalize_url

logger = get_logger(__name__)

# Each template targets a class of business event. `{name}` is the company,
# `{place}` its location. Industry never appears.
QUERY_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("news", '"{name}" news'),
    ("expansion", '"{name}" new store OR outlet OR branch OR expansion'),
    ("launch", '"{name}" launch OR launches OR unveils'),
    ("event", '"{name}" event OR sponsor OR exhibition'),
    ("partnership", '"{name}" partnership OR collaboration OR tie-up'),
    ("press", '"{name}" press release OR announcement'),
)

# Hosts that publish *about* companies. Results from these are second-hand
# but legitimate; results from the company's own domain are first-party.
_NEWS_HINTS = (
    "news", "times", "express", "herald", "tribune", "post", "journal",
    "media", "magazine", "daily", "wire", "report", "business", "economic",
)


class WebResearchProvider(ResearchSourceProvider):
    name = "web_search"

    def __init__(self, search_provider: SearchProvider | None = None):
        self._search = search_provider

    @property
    def search(self) -> SearchProvider:
        if self._search is None:
            self._search = get_search_provider()
        return self._search

    def _classify(self, url: str, company_domain: str, template: str) -> str:
        domain = extract_domain(url) or ""
        if domain == company_domain:
            # The company's own site: let the page classifier refine it later.
            return ResearchSourceType.COMPANY_NEWS if template in ("news", "press") else (
                ResearchSourceType.COMPANY_WEBSITE
            )
        if template == "press":
            return ResearchSourceType.PRESS_RELEASE
        if template == "event":
            return ResearchSourceType.EVENT
        if any(hint in domain for hint in _NEWS_HINTS):
            return ResearchSourceType.NEWS
        return ResearchSourceType.SEARCH_RESULT

    async def find_sources(
        self,
        *,
        company_name: str,
        domain: str,
        location: str | None = None,
        industry: str | None = None,
        limit: int = 25,
    ) -> list[ResearchCandidate]:
        place = (location or "").strip()
        templates = QUERY_TEMPLATES[: settings.research_max_search_queries]

        candidates: list[ResearchCandidate] = []
        seen_urls: set[str] = set()

        for index, (template_name, template) in enumerate(templates):
            query = template.format(name=company_name)
            # Location disambiguates common company names.
            if place and template_name in ("news", "expansion", "event"):
                query = f"{query} {place}"

            try:
                results = await self.search.search(
                    query, limit=settings.research_results_per_query
                )
            except ProviderError as exc:
                # One failing query must not abandon the whole run.
                logger.warning("research query failed name=%s query=%r: %s", company_name, query, exc)
                continue

            for item in results:
                url = normalize_url(item.url)
                if not url or url in seen_urls:
                    continue
                result_domain = extract_domain(url)
                if not result_domain:
                    continue
                # Directories and social aggregators are filtered by the same
                # rules discovery uses, unless it is the company's own site.
                if result_domain != domain and is_excluded_domain(result_domain):
                    continue

                seen_urls.add(url)
                candidates.append(
                    ResearchCandidate(
                        url=url,
                        title=item.title,
                        snippet=item.snippet,
                        source_type=self._classify(url, domain, template_name),
                        source_engine=item.source_engine,
                        query=query,
                        raw=item.raw or {},
                    )
                )
                if len(candidates) >= limit:
                    return candidates

            if settings.search_delay_seconds > 0 and index < len(templates) - 1:
                await asyncio.sleep(settings.search_delay_seconds)

        return candidates

    async def status(self) -> ResearchProviderStatus:
        try:
            search_status = await self.search.status()
        except Exception as exc:
            return ResearchProviderStatus(self.name, False, str(exc))
        return ResearchProviderStatus(
            self.name,
            search_status.available,
            f"Uses the '{search_status.name}' search provider. {search_status.detail or ''}".strip(),
        )
