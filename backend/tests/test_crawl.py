from datetime import UTC, datetime

import pytest

from app.models import Company, CompanyPage
from app.models.enums import CompanyStatus, CrawlStatus, PageType
from app.providers.crawler.base import CrawlerProvider, CrawlerStatus, FetchedPage
from app.services.crawl import CrawlService
from app.services.page_classifier import classify_page
from app.services.summary import build_summary


class FakeCrawler(CrawlerProvider):
    name = "fake"

    def __init__(self, pages: dict[str, FetchedPage]):
        self.pages = pages
        self.fetched: list[str] = []

    async def fetch(self, url: str) -> FetchedPage:
        self.fetched.append(url)
        return self.pages.get(url, FetchedPage(url=url, ok=False, error="not found", http_status=404))

    async def status(self):
        return CrawlerStatus(self.name, True)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com", PageType.HOME),
        ("https://example.com/", PageType.HOME),
        ("https://example.com/about", PageType.ABOUT),
        ("https://example.com/about-us", PageType.ABOUT),
        ("https://example.com/our-story", PageType.ABOUT),
        ("https://example.com/products", PageType.PRODUCTS),
        ("https://example.com/collections/gold", PageType.PRODUCTS),
        ("https://example.com/services", PageType.SERVICES),
        ("https://example.com/contact-us", PageType.CONTACT),
        ("https://example.com/store-locator", PageType.CONTACT),
        ("https://example.com/news", PageType.NEWS),
        ("https://example.com/blog/post-1", PageType.BLOG),
        ("https://example.com/careers", PageType.CAREERS),
        ("https://example.com/xyz-123", PageType.OTHER),
    ],
)
def test_page_classification_is_url_based_and_generic(url, expected):
    assert classify_page(url) == expected


def test_classification_falls_back_to_the_title():
    assert classify_page("https://example.com/p/17", "About Us") == PageType.ABOUT


def test_unrecognised_pages_are_other_not_guessed():
    assert classify_page("https://example.com/q/8", "Untitled") == PageType.OTHER


async def _company(session) -> Company:
    company = Company(
        name="Example",
        canonical_domain="example.com",
        website_url="https://example.com",
        status=CompanyStatus.DISCOVERED,
    )
    session.add(company)
    await session.commit()
    return company


def _page(url: str, title: str, text: str, links: list[str] | None = None) -> FetchedPage:
    return FetchedPage(url=url, ok=True, http_status=200, title=title, text=text, links=links or [])


async def test_crawl_stores_pages_and_classifies_them(session, monkeypatch):
    monkeypatch.setattr("app.services.robots.RobotsPolicy.can_fetch", lambda self, url: _true())
    company = await _company(session)
    crawler = FakeCrawler({
        "https://example.com": _page(
            "https://example.com", "Example | Home", "Welcome to Example.",
            links=[
                "https://example.com/about",
                "https://example.com/contact",
                "https://other.com/about",
                "https://example.com/brochure.pdf",
            ],
        ),
        "https://example.com/about": _page("https://example.com/about", "About Us", "Founded in 1990."),
        "https://example.com/contact": _page(
            "https://example.com/contact", "Contact", "Email info@example.com call +91 98765 43210"
        ),
    })

    await CrawlService(session, provider=crawler).crawl_company(company.id)

    pages = {page.page_type: page for page in await _pages(session, company.id)}
    assert set(pages) == {PageType.HOME, PageType.ABOUT, PageType.CONTACT}
    assert all(page.status == CrawlStatus.SUCCESS for page in pages.values())
    # Off-domain links are never followed.
    assert not any("other.com" in url for url in crawler.fetched)


async def test_crawl_marks_company_researched(session, monkeypatch):
    monkeypatch.setattr("app.services.robots.RobotsPolicy.can_fetch", lambda self, url: _true())
    company = await _company(session)
    crawler = FakeCrawler({"https://example.com": _page("https://example.com", "Example", "x" * 200)})

    await CrawlService(session, provider=crawler).crawl_company(company.id)

    await session.refresh(company)
    assert company.status == CompanyStatus.RESEARCHED
    assert company.last_researched_at is not None
    assert company.crawl_error is None


async def test_a_completely_failed_crawl_is_reported_not_swallowed(session, monkeypatch):
    monkeypatch.setattr("app.services.robots.RobotsPolicy.can_fetch", lambda self, url: _true())
    company = await _company(session)
    crawler = FakeCrawler({})  # every fetch fails

    await CrawlService(session, provider=crawler).crawl_company(company.id)

    await session.refresh(company)
    assert company.status == CompanyStatus.RESEARCH_FAILED
    assert company.crawl_error
    pages = await _pages(session, company.id)
    assert pages and pages[0].status == CrawlStatus.FAILED


async def test_robots_disallowed_pages_are_skipped_not_fetched(session, monkeypatch):
    monkeypatch.setattr("app.services.robots.RobotsPolicy.can_fetch", lambda self, url: _false())
    company = await _company(session)
    crawler = FakeCrawler({"https://example.com": _page("https://example.com", "Example", "hi")})

    await CrawlService(session, provider=crawler).crawl_company(company.id)

    assert crawler.fetched == []
    pages = await _pages(session, company.id)
    assert pages[0].status == CrawlStatus.SKIPPED
    assert "robots" in pages[0].error_message.lower()


async def test_recrawling_updates_rather_than_duplicates(session, monkeypatch):
    monkeypatch.setattr("app.services.robots.RobotsPolicy.can_fetch", lambda self, url: _true())
    company = await _company(session)
    crawler = FakeCrawler({"https://example.com": _page("https://example.com", "Example", "first")})
    service = CrawlService(session, provider=crawler)

    await service.crawl_company(company.id)
    crawler.pages["https://example.com"] = _page("https://example.com", "Example", "second")
    await service.crawl_company(company.id)

    pages = await _pages(session, company.id)
    assert len(pages) == 1
    assert pages[0].content == "second"


async def _pages(session, company_id: int) -> list[CompanyPage]:
    from sqlalchemy import select

    return list(
        await session.scalars(select(CompanyPage).where(CompanyPage.company_id == company_id))
    )


async def _true():
    return True


async def _false():
    return False


def test_summary_only_reports_what_was_actually_found():
    company = Company(name="Example", canonical_domain="example.com", website_url="https://example.com")
    pages = [
        CompanyPage(
            company_id=1, url="https://example.com", page_type=PageType.HOME, title="Example | Home",
            content="Welcome", content_length=7, status=CrawlStatus.SUCCESS, crawled_at=datetime.now(UTC),
        ),
        CompanyPage(
            company_id=1, url="https://example.com/contact", page_type=PageType.CONTACT, title="Contact",
            content="Reach us at info@example.com or +91 98765 43210", content_length=47,
            status=CrawlStatus.SUCCESS, crawled_at=datetime.now(UTC),
        ),
        CompanyPage(
            company_id=1, url="https://example.com/news", page_type=PageType.NEWS, title=None,
            content=None, content_length=0, status=CrawlStatus.FAILED, crawled_at=datetime.now(UTC),
        ),
    ]

    summary = build_summary(company, pages)

    assert summary.successful_pages == 2
    assert summary.failed_pages == 1
    assert summary.pages_found == ["contact", "home"]
    assert summary.homepage_title == "Example | Home"
    assert summary.emails == ["info@example.com"]
    assert summary.phones == ["+91 98765 43210"]
    # Every fact is a count or a copied value — nothing interpretive.
    assert all(isinstance(fact, str) and fact for fact in summary.facts)


def test_summary_of_a_company_with_no_pages_is_empty():
    company = Company(name="Example", canonical_domain="example.com", website_url="https://example.com")
    summary = build_summary(company, [])
    assert summary.page_count == 0 and summary.facts == [] and summary.emails == []
