"""Generic page-type classification from URL path and page title.

Purely structural: it recognises the shape of a corporate website, never an
industry. Unrecognised pages are ``other`` rather than guessed.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from app.models.enums import PageType

# Ordered: the first matching type wins, so more specific types come first.
_RULES: tuple[tuple[PageType, tuple[str, ...]], ...] = (
    (PageType.CAREERS, ("career", "careers", "jobs", "job", "vacancy", "vacancies", "hiring", "work-with-us", "join-us")),
    (PageType.CONTACT, ("contact", "contact-us", "contactus", "reach-us", "enquiry", "enquire", "get-in-touch", "locations", "stores", "store-locator", "branches")),
    (PageType.ABOUT, ("about", "about-us", "aboutus", "who-we-are", "our-story", "company", "overview", "profile", "history", "team", "leadership")),
    (PageType.PRODUCTS, ("product", "products", "collection", "collections", "catalogue", "catalog", "shop", "range", "portfolio")),
    (PageType.SERVICES, ("service", "services", "solutions", "capabilities", "what-we-do", "offerings", "expertise")),
    (PageType.NEWS, ("news", "press", "press-release", "press-releases", "media", "newsroom", "updates", "announcements", "events")),
    (PageType.BLOG, ("blog", "blogs", "articles", "insights", "resources", "stories", "journal")),
)

_SPLIT = re.compile(r"[^a-z0-9]+")


def _tokens(value: str) -> set[str]:
    return {token for token in _SPLIT.split(value.lower()) if token}


def classify_page(url: str, title: str | None = None, *, is_root: bool = False) -> PageType:
    path = urlsplit(url).path.strip("/")
    if is_root or not path:
        return PageType.HOME

    segments = [segment.lower() for segment in path.split("/") if segment]
    path_tokens = _tokens(path)
    title_tokens = _tokens(title or "")

    for page_type, keywords in _RULES:
        keyword_set = set(keywords)
        # A whole path segment matching outranks a loose token match.
        if any(segment in keyword_set for segment in segments):
            return page_type
        if path_tokens & keyword_set:
            return page_type

    for page_type, keywords in _RULES:
        if title_tokens & set(keywords):
            return page_type

    return PageType.OTHER


# Page types worth fetching during the shallow Phase 1 crawl, in priority order.
CRAWL_PRIORITY: tuple[PageType, ...] = (
    PageType.HOME,
    PageType.ABOUT,
    PageType.PRODUCTS,
    PageType.SERVICES,
    PageType.CONTACT,
    PageType.NEWS,
    PageType.BLOG,
    PageType.CAREERS,
)
