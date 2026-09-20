"""SearXNG search provider (self-hosted, free).

Talks to the instance's JSON API: GET {base}/search?q=...&format=json
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.core.config import settings
from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.providers.search.base import ProviderStatus, SearchProvider, SearchResultItem

logger = get_logger(__name__)


class SearxngSearchProvider(SearchProvider):
    name = "searxng"

    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.searxng_url).rstrip("/")
        self.timeout = timeout or settings.search_timeout_seconds

    async def search(self, query: str, *, limit: int = 20) -> list[SearchResultItem]:
        params = {
            "q": query,
            "format": "json",
            "safesearch": "0",
            "language": "en",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/search",
                    params=params,
                    headers={"Accept": "application/json", "User-Agent": settings.crawl_user_agent},
                )
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Could not reach SearXNG at {self.base_url}: {exc}",
                details={"provider": self.name},
            ) from exc

        if response.status_code == 403:
            raise ProviderError(
                "SearXNG rejected the request (403). Enable the JSON format in "
                "its settings.yml under `search.formats`.",
                details={"provider": self.name},
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"SearXNG returned HTTP {response.status_code}.",
                details={"provider": self.name},
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError(
                "SearXNG returned a non-JSON response. Is `json` listed in "
                "`search.formats` of settings.yml?",
                details={"provider": self.name},
            ) from exc

        return self._normalize(payload, limit=limit)

    def _normalize(self, payload: dict, *, limit: int) -> list[SearchResultItem]:
        now = datetime.now(UTC)
        items: list[SearchResultItem] = []
        for position, entry in enumerate(payload.get("results") or [], start=1):
            url = (entry.get("url") or "").strip()
            if not url:
                continue
            engine = entry.get("engine") or (entry.get("engines") or [None])[0]
            items.append(
                SearchResultItem(
                    title=(entry.get("title") or "").strip() or None,
                    url=url,
                    snippet=(entry.get("content") or "").strip() or None,
                    source_engine=engine,
                    position=position,
                    discovered_at=now,
                    raw=entry,
                )
            )
            if len(items) >= limit:
                break
        return items

    async def status(self) -> ProviderStatus:
        try:
            # Generous: a freshly started instance is slow on its first query.
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.base_url}/search",
                    params={"q": "ping", "format": "json"},
                    headers={"Accept": "application/json"},
                )
            if response.status_code == 200:
                return ProviderStatus(self.name, True, f"Connected to {self.base_url}")
            if response.status_code == 403:
                return ProviderStatus(
                    self.name, False, "Reachable, but the JSON API is disabled (HTTP 403)."
                )
            return ProviderStatus(self.name, False, f"HTTP {response.status_code} from {self.base_url}")
        except httpx.HTTPError as exc:
            # Timeouts stringify to "", so name the exception type instead.
            reason = str(exc) or type(exc).__name__
            return ProviderStatus(self.name, False, f"Not reachable at {self.base_url}: {reason}")
