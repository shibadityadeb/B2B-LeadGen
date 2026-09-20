"""Chooses the active crawler provider from configuration.

`CRAWLER_PROVIDER=auto` prefers Crawl4AI when it is installed and otherwise
uses the always-available httpx backend, so Phase 1 never hard-fails on an
optional dependency.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.providers.crawler.base import CrawlerProvider
from app.providers.crawler.crawl4ai_crawler import Crawl4AICrawlerProvider, crawl4ai_available
from app.providers.crawler.httpx_crawler import HttpxCrawlerProvider

logger = get_logger(__name__)

_BUILDERS: dict[str, type[CrawlerProvider]] = {
    "httpx": HttpxCrawlerProvider,
    "crawl4ai": Crawl4AICrawlerProvider,
}


def available_providers() -> list[str]:
    return ["auto", *sorted(_BUILDERS)]


def get_crawler_provider(name: str | None = None) -> CrawlerProvider:
    key = (name or settings.crawler_provider).lower().strip()
    if key == "auto":
        if crawl4ai_available():
            return Crawl4AICrawlerProvider()
        logger.info("crawl4ai not installed; using built-in httpx crawler")
        return HttpxCrawlerProvider()

    builder = _BUILDERS.get(key)
    if builder is None:
        raise AppError(
            f"Unknown crawler provider '{key}'. Available: {', '.join(available_providers())}."
        )
    return builder()
