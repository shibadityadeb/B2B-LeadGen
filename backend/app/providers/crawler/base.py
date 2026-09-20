"""Crawler provider contract.

Providers only *fetch and parse a single URL*. Deciding which URLs are worth
fetching, robots.txt compliance and rate limiting live in
``app.services.crawl`` so that swapping the fetch backend never changes
crawling behaviour or politeness.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FetchedPage:
    url: str
    ok: bool
    http_status: int | None = None
    title: str | None = None
    text: str | None = None
    links: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class CrawlerStatus:
    name: str
    available: bool
    detail: str | None = None


class CrawlerProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    async def fetch(self, url: str) -> FetchedPage:
        """Fetch one URL. Must not raise for ordinary network/HTTP failures —
        return ``FetchedPage(ok=False, error=...)`` instead."""

    @abc.abstractmethod
    async def status(self) -> CrawlerStatus: ...

    async def close(self) -> None:  # pragma: no cover - optional hook
        return None
