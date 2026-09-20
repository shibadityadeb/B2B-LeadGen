"""Crawl4AI crawler backend (optional).

Enabled when the `crawl4ai` package is installed. It renders pages with a
headless browser, which matters for JavaScript-only sites. Falls back to the
httpx provider automatically when the package is missing — see
``app.providers.crawler.registry``.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.crawler.base import CrawlerProvider, CrawlerStatus, FetchedPage
from app.providers.crawler.html_utils import parse_html

logger = get_logger(__name__)


def crawl4ai_available() -> bool:
    try:
        import crawl4ai  # noqa: F401
    except Exception:
        return False
    return True


class Crawl4AICrawlerProvider(CrawlerProvider):
    name = "crawl4ai"

    async def fetch(self, url: str) -> FetchedPage:
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
        except Exception as exc:  # pragma: no cover - import guard
            return FetchedPage(url=url, ok=False, error=f"crawl4ai is not installed: {exc}")

        browser_config = BrowserConfig(
            headless=True,
            user_agent=settings.crawl_user_agent,
            verbose=False,
        )
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=int(settings.crawl_timeout_seconds * 1000),
            word_count_threshold=5,
        )

        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
        except Exception as exc:
            logger.warning("crawl4ai fetch failed url=%s error=%s", url, exc)
            return FetchedPage(url=url, ok=False, error=str(exc))

        if not getattr(result, "success", False):
            return FetchedPage(
                url=url,
                ok=False,
                http_status=getattr(result, "status_code", None),
                error=getattr(result, "error_message", None) or "crawl4ai reported failure",
            )

        final_url = getattr(result, "url", url) or url
        html = getattr(result, "cleaned_html", None) or getattr(result, "html", "") or ""
        title, text, links = parse_html(html, final_url) if html else (None, "", [])

        # Prefer crawl4ai's markdown extraction when it produced more content.
        markdown = getattr(result, "markdown", None)
        markdown_text = getattr(markdown, "raw_markdown", None) or (
            markdown if isinstance(markdown, str) else None
        )
        if markdown_text and len(markdown_text) > len(text):
            text = markdown_text[: settings.crawl_max_content_chars]

        if not title:
            title = (getattr(result, "metadata", None) or {}).get("title")

        # crawl4ai exposes links as {"internal": [{"href": ...}], "external": [...]}.
        crawl_links = getattr(result, "links", None) or {}
        if isinstance(crawl_links, dict):
            for group in crawl_links.values():
                for item in group or []:
                    href = item.get("href") if isinstance(item, dict) else item
                    if href:
                        links.append(href)

        return FetchedPage(
            url=final_url,
            ok=True,
            http_status=getattr(result, "status_code", 200),
            title=title,
            text=text,
            links=links,
        )

    async def status(self) -> CrawlerStatus:
        if crawl4ai_available():
            return CrawlerStatus(self.name, True, "Crawl4AI installed (browser rendering enabled)")
        return CrawlerStatus(
            self.name,
            False,
            "Crawl4AI is not installed; the built-in httpx crawler is used instead.",
        )
