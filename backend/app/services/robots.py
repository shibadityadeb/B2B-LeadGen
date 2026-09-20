"""robots.txt fetching and evaluation.

Crawling is opt-out-respecting by default: a disallowed URL is never fetched,
and an unreachable robots.txt is treated as "allowed" only because that is the
documented convention — a robots.txt that explicitly denies us is always obeyed.
"""

from __future__ import annotations

from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RobotsPolicy:
    """Per-crawl cache of robots.txt decisions, one entry per origin."""

    def __init__(self, user_agent: str | None = None, *, enabled: bool | None = None):
        self.user_agent = user_agent or settings.crawl_user_agent
        self.enabled = settings.crawl_respect_robots if enabled is None else enabled
        self._parsers: dict[str, RobotFileParser | None] = {}

    async def _parser(self, origin: str) -> RobotFileParser | None:
        if origin in self._parsers:
            return self._parsers[origin]

        parser: RobotFileParser | None = None
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as client:
                response = await client.get(f"{origin}/robots.txt")
            if response.status_code == 200 and response.text:
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())
        except httpx.HTTPError as exc:
            logger.info("robots.txt unavailable for %s (%s); proceeding", origin, exc)

        self._parsers[origin] = parser
        return parser

    async def can_fetch(self, url: str) -> bool:
        if not self.enabled:
            return True
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            return False
        parser = await self._parser(f"{parts.scheme}://{parts.netloc}")
        if parser is None:
            return True
        return parser.can_fetch(self.user_agent, url)

    async def crawl_delay(self, url: str) -> float | None:
        if not self.enabled:
            return None
        parts = urlsplit(url)
        parser = await self._parser(f"{parts.scheme}://{parts.netloc}")
        if parser is None:
            return None
        try:
            delay = parser.crawl_delay(self.user_agent)
        except Exception:
            return None
        return float(delay) if delay else None
