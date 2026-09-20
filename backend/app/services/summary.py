"""Deterministic company profile summary.

Everything here is extracted verbatim from crawled pages or counted from the
database. No language model is involved, and nothing is inferred — Phase 2
owns interpretation.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from app.models import Company, CompanyPage
from app.models.enums import CrawlStatus, PageType

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Loose international/Indian phone shapes; validated only by length.
_PHONE = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,5}\)?[\s-]?)?\d{3,5}[\s-]?\d{4,6}")
_IMAGE_EXT = re.compile(r"\.(png|jpe?g|gif|svg|webp)$", re.IGNORECASE)


@dataclass
class CompanySummary:
    pages_found: list[str] = field(default_factory=list)
    page_count: int = 0
    successful_pages: int = 0
    failed_pages: int = 0
    homepage_title: str | None = None
    total_content_chars: int = 0
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)

    def dict(self) -> dict:
        return asdict(self)


def _clean_phone(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if not 8 <= len(digits) <= 15:
        return None
    return re.sub(r"\s+", " ", value).strip()


def build_summary(company: Company, pages: list[CompanyPage]) -> CompanySummary:
    summary = CompanySummary()
    if not pages:
        return summary

    summary.page_count = len(pages)
    successful = [page for page in pages if page.status == CrawlStatus.SUCCESS]
    summary.successful_pages = len(successful)
    summary.failed_pages = len(pages) - len(successful)
    summary.pages_found = sorted({page.page_type for page in successful})
    summary.total_content_chars = sum(page.content_length or 0 for page in successful)

    home = next((page for page in successful if page.page_type == PageType.HOME), None)
    if home:
        summary.homepage_title = home.title

    emails: list[str] = []
    phones: list[str] = []
    for page in successful:
        content = page.content or ""
        for match in _EMAIL.findall(content):
            candidate = match.strip(".,;:").lower()
            if _IMAGE_EXT.search(candidate) or candidate in emails:
                continue
            emails.append(candidate)
        # Phone numbers are only trusted on the contact page, where a bare
        # number is unambiguous rather than a price or a product code.
        if page.page_type == PageType.CONTACT:
            for match in _PHONE.findall(content):
                cleaned = _clean_phone(match)
                if cleaned and cleaned not in phones:
                    phones.append(cleaned)

    summary.emails = emails[:10]
    summary.phones = phones[:10]

    # Plain, checkable statements — each one is a count or a copied value.
    facts: list[str] = []
    if summary.successful_pages:
        facts.append(
            f"{summary.successful_pages} page(s) retrieved from {company.canonical_domain}."
        )
    if summary.pages_found:
        facts.append("Page types found: " + ", ".join(summary.pages_found) + ".")
    if summary.homepage_title:
        facts.append(f'Homepage title: "{summary.homepage_title}".')
    if summary.emails:
        facts.append(f"{len(summary.emails)} contact email(s) listed on the website.")
    if summary.phones:
        facts.append(f"{len(summary.phones)} phone number(s) listed on the contact page.")
    if summary.failed_pages:
        facts.append(f"{summary.failed_pages} page(s) could not be retrieved.")
    summary.facts = facts

    return summary
