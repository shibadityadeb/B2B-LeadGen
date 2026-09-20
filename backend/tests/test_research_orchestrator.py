"""End-to-end orchestrator behaviour against mock providers."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.models import (
    CompanyPage,
    DecisionMaker,
    Evidence,
    Opportunity,
    ResearchBrief,
    ResearchSource,
    Signal,
    UbmCapability,
)
from app.models.enums import (
    CompanyStatus,
    CrawlStatus,
    ObservationState,
    PageType,
    ResearchStatus,
    RetrievalStatus,
    SourceReliability,
    VerificationStatus,
)
from app.providers.people.base import DiscoveredPerson
from app.services.research_orchestrator import ResearchOrchestrator
from tests.factories_phase2 import (
    FakeCrawler,
    FakeLLM,
    FakePeopleProvider,
    FakeResearchProvider,
    candidate,
    make_company,
)

NEWS_TEXT = (
    "Acme Retail opened two new showrooms in Bhopal this month. "
    "The company is expanding into Madhya Pradesh with a regional campaign. "
    "Acme Retail also partnered with a local logistics provider for deliveries."
)
ABOUT_TEXT = (
    "Founded in 1998, Acme Retail today employs around 450 employees across India. "
    "We are hiring a Brand Marketing Manager to lead our regional campaigns."
)


async def _page(session, company_id: int, url: str, text: str, page_type=PageType.ABOUT):
    page = CompanyPage(
        company_id=company_id,
        url=url,
        page_type=page_type,
        title="About Acme",
        content=text,
        content_length=len(text),
        status=CrawlStatus.SUCCESS,
        crawled_at=datetime.now(UTC),
    )
    session.add(page)
    await session.commit()
    return page


def _orchestrator(session, **overrides) -> ResearchOrchestrator:
    return ResearchOrchestrator(
        session,
        research_provider=overrides.pop("research_provider", FakeResearchProvider()),
        crawler=overrides.pop("crawler", FakeCrawler()),
        people_provider=overrides.pop("people_provider", FakePeopleProvider()),
        llm=overrides.pop("llm", FakeLLM(enabled=False)),
    )


@pytest.fixture
async def company(session):
    return await make_company(session)


async def test_run_completes_and_records_real_counters(session, company):
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    orchestrator = _orchestrator(
        session,
        research_provider=FakeResearchProvider([candidate("https://news.test/acme")]),
        crawler=FakeCrawler({"https://news.test/acme": NEWS_TEXT}),
    )
    run = await orchestrator.create_run(company)
    result = await orchestrator.execute(run.id)

    assert result.status == ResearchStatus.COMPLETED
    assert result.progress == 100
    assert result.started_at and result.completed_at
    assert result.evidence_count > 0
    assert result.signals_count > 0
    assert result.opportunities_count > 0


async def test_phase_1_pages_are_ingested_as_first_party_sources(session, company):
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    orchestrator = _orchestrator(session)
    run = await orchestrator.create_run(company)
    await orchestrator.execute(run.id)

    source = await session.scalar(
        select(ResearchSource).where(ResearchSource.url == "https://acme-retail.test/about")
    )
    assert source is not None
    assert source.source_reliability == SourceReliability.FIRST_PARTY
    assert source.retrieval_status == RetrievalStatus.RETRIEVED
    assert source.content_hash, "content must be hashed for change detection"


async def test_every_evidence_item_links_to_a_real_source(session, company):
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    orchestrator = _orchestrator(session)
    run = await orchestrator.create_run(company)
    await orchestrator.execute(run.id)

    items = await session.scalars(
        select(Evidence).where(Evidence.company_id == company.id)
    )
    items = list(items)
    assert items
    for item in items:
        source = await session.get(ResearchSource, item.source_id)
        assert source is not None and source.url
        # The excerpt must actually appear in the retrieved content.
        assert item.excerpt and item.excerpt.rstrip("…")[:60] in (source.content or "")


async def test_capabilities_are_seeded_on_first_run(session, company):
    assert await session.scalar(select(func.count(UbmCapability.id))) == 0
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    orchestrator = _orchestrator(session)
    run = await orchestrator.create_run(company)
    await orchestrator.execute(run.id)
    assert await session.scalar(select(func.count(UbmCapability.id))) > 0


async def test_opportunities_link_back_to_evidence_and_signals(session, company):
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    orchestrator = _orchestrator(
        session,
        research_provider=FakeResearchProvider([candidate("https://news.test/acme")]),
        crawler=FakeCrawler({"https://news.test/acme": NEWS_TEXT}),
    )
    run = await orchestrator.create_run(company)
    await orchestrator.execute(run.id)

    opportunities = await orchestrator.opportunities.list_for_company(company.id)
    assert opportunities
    for opportunity in opportunities:
        assert opportunity.evidence_links, "a hypothesis with no evidence is not allowed"
        assert opportunity.why_relevant
        for link in opportunity.evidence_links:
            assert await session.get(Evidence, link.evidence_id) is not None


async def test_rerunning_is_idempotent(session, company):
    """A second run must not duplicate sources, evidence, signals or hypotheses."""
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    provider = FakeResearchProvider([candidate("https://news.test/acme")])
    crawler = FakeCrawler({"https://news.test/acme": NEWS_TEXT})

    first = _orchestrator(session, research_provider=provider, crawler=crawler)
    run_one = await first.create_run(company)
    await first.execute(run_one.id)

    counts_before = {
        "sources": await session.scalar(select(func.count(ResearchSource.id))),
        "evidence": await session.scalar(select(func.count(Evidence.id))),
        "signals": await session.scalar(select(func.count(Signal.id))),
        "opportunities": await session.scalar(select(func.count(Opportunity.id))),
    }

    second = _orchestrator(session, research_provider=provider, crawler=crawler)
    run_two = await second.create_run(company)
    await second.execute(run_two.id)

    counts_after = {
        "sources": await session.scalar(select(func.count(ResearchSource.id))),
        "evidence": await session.scalar(select(func.count(Evidence.id))),
        "signals": await session.scalar(select(func.count(Signal.id))),
        "opportunities": await session.scalar(select(func.count(Opportunity.id))),
    }
    assert counts_before == counts_after


async def test_rerun_records_reobservation_for_change_detection(session, company):
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    first = _orchestrator(session)
    run_one = await first.create_run(company)
    await first.execute(run_one.id)

    second = _orchestrator(session)
    run_two = await second.create_run(company)
    await second.execute(run_two.id)

    items = list(await session.scalars(select(Evidence).where(Evidence.company_id == company.id)))
    assert items
    assert all(item.times_observed >= 2 for item in items)
    assert all(item.first_seen_run_id == run_one.id for item in items)
    assert all(item.last_seen_run_id == run_two.id for item in items)
    assert all(
        item.observation_state in (ObservationState.STILL_PRESENT, ObservationState.UPDATED)
        for item in items
    )


async def test_evidence_that_disappears_is_marked_not_deleted(session, company):
    page = await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    first = _orchestrator(session)
    run_one = await first.create_run(company)
    await first.execute(run_one.id)
    before = await session.scalar(select(func.count(Evidence.id)))

    # The page no longer says any of it.
    page.content = "Welcome to our website. Browse our catalogue."
    await session.commit()

    second = _orchestrator(session)
    run_two = await second.create_run(company)
    await second.execute(run_two.id)

    after = await session.scalar(select(func.count(Evidence.id)))
    assert after == before, "history must never be deleted"
    stale = list(
        await session.scalars(
            select(Evidence).where(Evidence.observation_state == ObservationState.NOT_FOUND)
        )
    )
    assert stale, "evidence no longer observed must be flagged"


async def test_run_survives_a_failing_search_provider(session, company):
    """First-party pages still yield evidence when search is unavailable."""
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    orchestrator = _orchestrator(session, research_provider=FakeResearchProvider(failing=True))
    run = await orchestrator.create_run(company)
    result = await orchestrator.execute(run.id)

    assert result.status == ResearchStatus.COMPLETED
    assert result.evidence_count > 0
    assert any(error.get("stage") == "discover_sources" for error in result.errors)


async def test_robots_disallowed_sources_are_skipped(session, company, monkeypatch):
    async def deny(self, url):
        return False

    monkeypatch.setattr("app.services.robots.RobotsPolicy.can_fetch", deny)
    crawler = FakeCrawler({"https://news.test/acme": NEWS_TEXT})
    orchestrator = _orchestrator(
        session,
        research_provider=FakeResearchProvider([candidate("https://news.test/acme")]),
        crawler=crawler,
    )
    run = await orchestrator.create_run(company)
    await orchestrator.execute(run.id)

    assert crawler.fetched == [], "a disallowed URL must never be fetched"
    source = await session.scalar(
        select(ResearchSource).where(ResearchSource.url == "https://news.test/acme")
    )
    assert source.retrieval_status == RetrievalStatus.SKIPPED
    assert "robots" in (source.error_message or "").lower()


async def test_a_brief_is_generated_and_stored(session, company):
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    orchestrator = _orchestrator(session)
    run = await orchestrator.create_run(company)
    await orchestrator.execute(run.id)

    brief = await session.scalar(
        select(ResearchBrief).where(ResearchBrief.research_run_id == run.id)
    )
    assert brief is not None
    assert brief.generated_by == "deterministic"
    assert "## Potential UBM opportunities" in brief.markdown
    assert "## Sources" in brief.markdown
    assert brief.profile["company"]["name"] == company.name


async def test_decision_makers_are_persisted_with_provenance(session, company):
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    people = FakePeopleProvider(
        [
            DiscoveredPerson(
                name="Priya Nair",
                role="Head of Marketing",
                role_category="marketing",
                source_url="https://acme-retail.test/about",
                excerpt="Priya Nair - Head of Marketing",
                verification_status=VerificationStatus.PUBLIC_COMPANY_SOURCE,
            ),
            DiscoveredPerson(
                role="Chief Marketing Officer",
                role_category="marketing",
                verification_status=VerificationStatus.ROLE_ONLY,
            ),
        ]
    )
    orchestrator = _orchestrator(session, people_provider=people)
    run = await orchestrator.create_run(company)
    await orchestrator.execute(run.id)

    rows = list(await session.scalars(select(DecisionMaker)))
    assert len(rows) == 2
    named = next(row for row in rows if row.name)
    unnamed = next(row for row in rows if not row.name)

    assert named.source_id is not None, "a named person must cite its source"
    assert named.verification_status == VerificationStatus.PUBLIC_COMPANY_SOURCE
    # A role with no published name stays unnamed rather than being invented.
    assert unnamed.name is None
    assert unnamed.verification_status == VerificationStatus.ROLE_ONLY
    assert all(row.email is None for row in rows), "emails are never derived"


async def test_a_failing_llm_does_not_fail_the_run(session, company):
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    orchestrator = _orchestrator(session, llm=FakeLLM(enabled=True, failing=True))
    run = await orchestrator.create_run(company)
    result = await orchestrator.execute(run.id)

    assert result.status == ResearchStatus.COMPLETED
    assert result.evidence_count > 0
    assert any(error.get("stage") == "llm" for error in result.errors)


async def test_llm_claims_are_only_kept_when_verifiable(session, company):
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    llm = FakeLLM(
        enabled=True,
        payload={
            "claims": [
                {
                    "claim": "Acme was founded in 1998.",
                    "excerpt": "Founded in 1998, Acme Retail today employs around 450 employees",
                    "evidence_type": "company_identity",
                    "certain": True,
                },
                {
                    "claim": "Acme raised 100 crore in funding.",
                    "excerpt": "Acme raised 100 crore from investors last quarter",
                    "evidence_type": "funding",
                    "certain": True,
                },
            ],
            "uncertainties": ["Revenue is not published."],
        },
    )
    orchestrator = _orchestrator(session, llm=llm)
    run = await orchestrator.create_run(company)
    result = await orchestrator.execute(run.id)

    claims = [
        item.claim
        for item in await session.scalars(select(Evidence).where(Evidence.company_id == company.id))
    ]
    # The fabricated funding claim is not in the source text and must be dropped.
    assert not any("100 crore" in claim for claim in claims)
    assert result.llm_used is True


async def test_company_status_reflects_research_lifecycle(session, company):
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    orchestrator = _orchestrator(session)
    run = await orchestrator.create_run(company)
    await orchestrator.execute(run.id)

    await session.refresh(company)
    assert company.status == CompanyStatus.RESEARCHED
    assert company.last_researched_at is not None


async def test_a_run_already_completed_is_not_executed_again(session, company):
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)
    crawler = FakeCrawler({"https://news.test/acme": NEWS_TEXT})
    orchestrator = _orchestrator(
        session,
        research_provider=FakeResearchProvider([candidate("https://news.test/acme")]),
        crawler=crawler,
    )
    run = await orchestrator.create_run(company)
    await orchestrator.execute(run.id)
    fetches = len(crawler.fetched)

    await orchestrator.execute(run.id)
    assert len(crawler.fetched) == fetches


async def test_people_are_only_taken_from_first_party_sources(session, company):
    """A news article naming someone usually names an employee of a *different*
    company. Attributing them here would be a factual error."""
    await _page(session, company.id, "https://acme-retail.test/about", ABOUT_TEXT)

    news = (
        "Philippe Benacin, Co-founder and CEO of another group, said the segment is growing. "
        "Gayatri Yadav, Group CMO at a large conglomerate, shared her view."
    )
    orchestrator = _orchestrator(
        session,
        research_provider=FakeResearchProvider([candidate("https://news.test/industry")]),
        crawler=FakeCrawler({"https://news.test/industry": news}),
        people_provider=__import__(
            "app.providers.people.website_people", fromlist=["WebsitePeopleProvider"]
        ).WebsitePeopleProvider(),
    )
    run = await orchestrator.create_run(company)
    await orchestrator.execute(run.id)

    from sqlalchemy import select as _select

    from app.models import DecisionMaker as _DecisionMaker

    people = list(await session.scalars(_select(_DecisionMaker)))
    names = {person.name for person in people}
    assert "Philippe Benacin" not in names
    assert "Gayatri Yadav" not in names
