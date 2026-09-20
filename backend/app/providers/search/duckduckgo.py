"""DuckDuckGo HTML search provider.

Free, no API key, no container and no account — this is the zero-setup
default so the application is runnable immediately. It queries the same
public HTML endpoint a browser uses and parses the result list.

Trade-off versus SearXNG: a single upstream engine rather than an aggregate,
and it is rate-limited more aggressively, so keep SEARCH_DELAY_SECONDS at 1s
or above. Switch to `SEARCH_PROVIDER=searxng` for broader coverage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, unquote, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.providers.search.base import ProviderStatus, SearchProvider, SearchResultItem

logger = get_logger(__name__)

ENDPOINT = "https://html.duckduckgo.com/html/"

# A browser-like UA is required: the endpoint returns an empty page otherwise.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


class DuckDuckGoSearchProvider(SearchProvider):
    name = "duckduckgo"

    def __init__(self, timeout: float | None = None):
        self.timeout = timeout or settings.search_timeout_seconds

    async def search(self, query: str, *, limit: int = 20) -> list[SearchResultItem]:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True, headers=_HEADERS
            ) as client:
                response = await client.post(ENDPOINT, data={"q": query, "kl": "wt-wt"})
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Could not reach DuckDuckGo: {exc}", details={"provider": self.name}
            ) from exc

        if response.status_code == 429:
            raise ProviderError(
                "DuckDuckGo is rate limiting this client. Increase "
                "SEARCH_DELAY_SECONDS, or switch to a self-hosted SearXNG "
                "instance (SEARCH_PROVIDER=searxng).",
                details={"provider": self.name},
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"DuckDuckGo returned HTTP {response.status_code}.",
                details={"provider": self.name},
            )

        body = response.text
        if _is_bot_challenge(body):
            # A challenge page arrives as HTTP 200/202 with no results. Treat it
            # as the failure it is rather than reporting "0 results found".
            raise ProviderError(
                "DuckDuckGo served a bot-detection page instead of results. "
                "This endpoint throttles repeated automated queries; run a "
                "self-hosted SearXNG instance (SEARCH_PROVIDER=searxng) for "
                "reliable discovery.",
                details={"provider": self.name},
            )

        return self._parse(body, limit=limit)

    def _parse(self, html: str, *, limit: int) -> list[SearchResultItem]:
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(UTC)
        items: list[SearchResultItem] = []

        for position, block in enumerate(soup.select("div.result, div.web-result"), start=1):
            anchor = block.select_one("a.result__a")
            if not anchor or not anchor.get("href"):
                continue
            url = _unwrap(anchor["href"])
            if not url:
                continue
            snippet_node = block.select_one(".result__snippet")
            items.append(
                SearchResultItem(
                    title=anchor.get_text(" ", strip=True) or None,
                    url=url,
                    snippet=snippet_node.get_text(" ", strip=True) if snippet_node else None,
                    source_engine=self.name,
                    position=position,
                    discovered_at=now,
                    raw={
                        "url": url,
                        "title": anchor.get_text(" ", strip=True),
                        "href": anchor["href"],
                    },
                )
            )
            if len(items) >= limit:
                break

        return items

    async def status(self) -> ProviderStatus:
        try:
            results = await self.search("test", limit=1)
        except ProviderError as exc:
            return ProviderStatus(self.name, False, str(exc))
        if not results:
            return ProviderStatus(
                self.name, False, "Reachable, but returned no results (possibly throttled)."
            )
        return ProviderStatus(self.name, True, "Connected (public endpoint, no API key)")


def _is_bot_challenge(body: str) -> bool:
    lowered = body[:20000].lower()
    return ("anomaly" in lowered and "challenge" in lowered) or "detected unusual" in lowered


def _unwrap(href: str) -> str | None:
    """DuckDuckGo wraps results as /l/?uddg=<encoded target>."""
    if href.startswith("//"):
        href = "https:" + href
    parts = urlsplit(href)
    if parts.path.startswith("/l/"):
        target = parse_qs(parts.query).get("uddg", [None])[0]
        return unquote(target) if target else None
    return href if parts.scheme in ("http", "https") else None
