"""Dependency-light crawler backend: plain HTTP + HTML parsing.

Always available. Sufficient for server-rendered marketing sites, which is
the large majority of company websites.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.crawler.base import CrawlerProvider, CrawlerStatus, FetchedPage
from app.providers.crawler.html_utils import parse_html

logger = get_logger(__name__)


class HttpxCrawlerProvider(CrawlerProvider):
    name = "httpx"

    async def fetch(self, url: str) -> FetchedPage:
        try:
            async with httpx.AsyncClient(
                timeout=settings.crawl_timeout_seconds,
                follow_redirects=True,
                headers={
                    "User-Agent": settings.crawl_user_agent,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en",
                },
            ) as client:
                response = await client.get(url)
        except httpx.HTTPError as exc:
            logger.warning("crawl failed url=%s error=%s", url, exc)
            return FetchedPage(url=url, ok=False, error=str(exc))

        final_url = str(response.url)
        if response.status_code >= 400:
            return FetchedPage(
                url=final_url,
                ok=False,
                http_status=response.status_code,
                error=f"HTTP {response.status_code}",
            )

        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return FetchedPage(
                url=final_url,
                ok=False,
                http_status=response.status_code,
                error=f"Unsupported content type: {content_type or 'unknown'}",
            )

        title, text, links = parse_html(response.text, final_url)
        return FetchedPage(
            url=final_url,
            ok=True,
            http_status=response.status_code,
            title=title,
            text=text,
            links=links,
        )

    async def status(self) -> CrawlerStatus:
        return CrawlerStatus(self.name, True, "Built-in HTTP crawler (no browser rendering)")
