"""DuckDuckGo HTML search provider.

Free, no API key, no container and no account — this is the zero-setup
default so the application is runnable immediately. It queries the same
public HTML endpoint a browser uses and parses the result list.

Trade-off versus SearXNG: a single upstream engine rather than an aggregate,
and it is rate-limited more aggressively, so keep SEARCH_DELAY_SECONDS at 1s
or above. Switch to `SEARCH_PROVIDER=searxng` for broader coverage.
"""

from __future__ import annotations

import asyncio
import random
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

    #: The endpoint throttles bursts, so a refused query is retried a couple
    #: of times with growing, jittered gaps before giving up.
    MAX_ATTEMPTS = 3
    BASE_BACKOFF_SECONDS = 4.0

    def __init__(self, timeout: float | None = None):
        self.timeout = timeout or settings.search_timeout_seconds

    async def search(self, query: str, *, limit: int = 20) -> list[SearchResultItem]:
        last_error: ProviderError | None = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                body = await self._fetch(query)
            except ProviderError as exc:
                last_error = exc
                # Only a throttle is worth waiting out; a hard error is not.
                if not exc.details.get("retryable") or attempt == self.MAX_ATTEMPTS:
                    raise
                # Jitter so parallel runs do not retry in lockstep.
                delay = self.BASE_BACKOFF_SECONDS * attempt + random.uniform(0, 2)
                logger.info(
                    "duckduckgo throttled (attempt %s/%s); waiting %.1fs",
                    attempt, self.MAX_ATTEMPTS, delay,
                )
                await asyncio.sleep(delay)
                continue

            return self._parse(body, limit=limit)

        raise last_error or ProviderError(
            "DuckDuckGo did not return results.", details={"provider": self.name}
        )

    async def _fetch(self, query: str) -> str:
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
                "DuckDuckGo is rate limiting this server.",
                details={"provider": self.name, "retryable": True},
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"DuckDuckGo returned HTTP {response.status_code}.",
                details={"provider": self.name},
            )

        body = response.text
        if _is_bot_challenge(body):
            # A challenge page arrives as HTTP 200/202 with no results. Treat
            # it as the failure it is rather than reporting "0 results found".
            raise ProviderError(
                "DuckDuckGo is serving a bot-check page instead of results. It "
                "limits automated searching from shared server addresses. For "
                "dependable results, run a SearXNG instance and set "
                "SEARCH_PROVIDER=searxng with SEARXNG_URL.",
                details={"provider": self.name, "retryable": True, "needs_searxng": True},
            )

        return body

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
