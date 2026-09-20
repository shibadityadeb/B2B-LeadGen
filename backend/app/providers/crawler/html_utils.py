"""Shared HTML -> (title, text, links) extraction used by crawler providers."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.core.config import settings

_WHITESPACE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_STRIP_TAGS = ("script", "style", "noscript", "template", "svg", "iframe")


def parse_html(html: str, base_url: str) -> tuple[str | None, str, list[str]]:
    soup = BeautifulSoup(html, "lxml")

    title = None
    if soup.title and soup.title.string:
        title = _WHITESPACE.sub(" ", soup.title.string).strip() or None
    if not title:
        meta = soup.find("meta", attrs={"property": "og:site_name"}) or soup.find(
            "meta", attrs={"property": "og:title"}
        )
        if meta and meta.get("content"):
            title = meta["content"].strip() or None

    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        links.append(urljoin(base_url, href))

    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    text = soup.get_text(separator="\n")
    text = _WHITESPACE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = _BLANK_LINES.sub("\n\n", text).strip()

    return title, text[: settings.crawl_max_content_chars], links
