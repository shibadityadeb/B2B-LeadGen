"""Mock providers and row builders for Phase 2 tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models import Company, Evidence, ResearchSource
from app.models.enums import (
    EpistemicStatus,
    ResearchSourceType,
    RetrievalStatus,
    SourceReliability,
)
from app.providers.crawler.base import CrawlerProvider, CrawlerStatus, FetchedPage
from app.providers.llm.base import LLMProvider, LLMStatus
from app.providers.people.base import (
    DecisionMakerProvider,
    DiscoveredPerson,
    PeopleProviderStatus,
)
from app.providers.research.base import (
    ResearchCandidate,
    ResearchProviderStatus,
    ResearchSourceProvider,
)


class FakeResearchProvider(ResearchSourceProvider):
    name = "fake_research"

    def __init__(self, candidates: list[ResearchCandidate] | None = None, failing: bool = False):
        self.candidates = candidates or []
        self.failing = failing
        self.calls: list[str] = []

    async def find_sources(self, *, company_name, domain, location=None, industry=None, limit=25):
        self.calls.append(company_name)
        if self.failing:
            from app.core.errors import ProviderError

            raise ProviderError("search backend unavailable")
        return self.candidates[:limit]

    async def status(self):
        return ResearchProviderStatus(self.name, True)


class FakeCrawler(CrawlerProvider):
    name = "fake_crawler"

    def __init__(self, pages: dict[str, str] | None = None):
        self.pages = pages or {}
        self.fetched: list[str] = []

    async def fetch(self, url: str) -> FetchedPage:
        self.fetched.append(url)
        text = self.pages.get(url)
        if text is None:
            return FetchedPage(url=url, ok=False, http_status=404, error="HTTP 404")
        return FetchedPage(url=url, ok=True, http_status=200, title="Page", text=text, links=[])

    async def status(self):
        return CrawlerStatus(self.name, True)


class FakePeopleProvider(DecisionMakerProvider):
    name = "fake_people"

    def __init__(self, people: list[DiscoveredPerson] | None = None):
        self.people = people or []

    async def find_people(self, *, company_name, documents):
        return self.people

    async def status(self):
        return PeopleProviderStatus(self.name, True)


class FakeLLM(LLMProvider):
    name = "fake_llm"

    def __init__(self, payload: dict | None = None, enabled: bool = True, failing: bool = False):
        self.payload = payload or {"claims": [], "uncertainties": []}
        self._enabled = enabled
        self.failing = failing
        self.prompts: list[str] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def complete_json(self, *, system, prompt, schema=None):
        self.prompts.append(prompt)
        if self.failing:
            from app.core.errors import ProviderError

            raise ProviderError("model unavailable")
        return self.payload

    async def status(self):
        return LLMStatus(self.name, self._enabled)


def candidate(url: str, source_type: str = ResearchSourceType.NEWS, **kwargs) -> ResearchCandidate:
    return ResearchCandidate(
        url=url,
        title=kwargs.pop("title", "A public page"),
        snippet=kwargs.pop("snippet", None),
        source_type=source_type,
        **kwargs,
    )


async def make_company(session, **overrides) -> Company:
    company = Company(
        **{
            "name": "Acme Retail",
            "canonical_domain": "acme-retail.test",
            "website_url": "https://acme-retail.test",
            "industry": "Retail",
            "location": "Indore",
            **overrides,
        }
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return company


async def make_source(session, company_id: int, **overrides) -> ResearchSource:
    source = ResearchSource(
        **{
            "company_id": company_id,
            "url": "https://acme-retail.test/about",
            "domain": "acme-retail.test",
            "title": "About",
            "source_type": ResearchSourceType.COMPANY_ABOUT,
            "source_reliability": SourceReliability.FIRST_PARTY,
            "retrieval_status": RetrievalStatus.RETRIEVED,
            "content": "Some content",
            "retrieved_at": datetime.now(UTC),
            **overrides,
        }
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def make_evidence(session, company_id: int, source_id: int, **overrides) -> Evidence:
    from app.services.fingerprints import evidence_fingerprint

    evidence_type = overrides.pop("evidence_type", "new_store")
    claim = overrides.pop("claim", "Acme opened a store.")
    item = Evidence(
        **{
            "company_id": company_id,
            "source_id": source_id,
            "claim": claim,
            "excerpt": "Acme opened a new store in Bhopal.",
            "evidence_type": evidence_type,
            "epistemic_status": EpistemicStatus.KNOWN,
            "normalized_value": {},
            "observed_at": datetime.now(UTC),
            "confidence": 0.8,
            "confidence_level": "high",
            "fingerprint": evidence_fingerprint(company_id, evidence_type, claim),
            **overrides,
        }
    )
    session.add(item)
    await session.commit()
    await session.refresh(item, ["source"])
    return item
