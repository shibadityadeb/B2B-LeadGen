"""End-to-end tests of the discovery pipeline against a fake search provider."""

import pytest
from sqlalchemy import func, select

from app.models import Company, CompanySource, SearchQuery, SearchResult, Target
from app.models.enums import RunStatus
from app.services.discovery import DiscoveryService
from tests.factories import FakeSearchProvider, result


async def _target(session, **overrides) -> Target:
    target = Target(
        **{
            "name": "Jewellery — Indore",
            "industry": "Jewellery",
            "location": "Indore",
            "country": "India",
            "keywords": ["jewellery showroom"],
            **overrides,
        }
    )
    session.add(target)
    await session.commit()
    return target


async def _run(session, provider, target) -> object:
    service = DiscoveryService(session, provider=provider)
    run = await service.create_run(target)
    return await service.execute_run(run.id)


@pytest.fixture
def provider():
    return FakeSearchProvider(
        default=[
            result("https://www.acme-jewels.com/about", "Acme Jewels | About Us"),
            result("https://acme-jewels.com/products", "Acme Jewels - Products"),
            result("https://beta-gold.in/", "Beta Gold"),
            result("https://www.justdial.com/Indore/Jewellery", "Jewellery in Indore"),
            result("https://beta-gold.in/catalogue.pdf", "Catalogue"),
        ]
    )


async def test_run_completes_and_records_real_counters(session, provider):
    target = await _target(session)
    run = await _run(session, provider, target)

    assert run.status == RunStatus.COMPLETED
    assert run.progress == 100
    assert run.started_at and run.completed_at
    assert run.queries_count == len(provider.queries) > 0
    # Identical URLs returned by several queries are stored once.
    assert run.results_count == 5
    assert run.unique_domains_count == 2
    assert run.new_companies_count == 2
    assert run.rejected_results_count == 2
    assert run.failed_queries_count == 0


async def test_companies_are_deduplicated_by_domain(session, provider):
    target = await _target(session)
    await _run(session, provider, target)

    domains = list(await session.scalars(select(Company.canonical_domain)))
    assert sorted(domains) == ["acme-jewels.com", "beta-gold.in"]


async def test_a_second_run_creates_no_duplicates(session, provider):
    target = await _target(session)
    await _run(session, provider, target)
    second = await _run(session, provider, target)

    assert second.new_companies_count == 0
    assert second.duplicate_companies_count == 2
    assert await session.scalar(select(func.count(Company.id))) == 2


async def test_every_company_has_a_source_url(session, provider):
    target = await _target(session)
    run = await _run(session, provider, target)

    companies = list(await session.scalars(select(Company)))
    for company in companies:
        sources = list(
            await session.scalars(
                select(CompanySource).where(CompanySource.company_id == company.id)
            )
        )
        assert sources, f"{company.canonical_domain} has no source"
        assert all(source.url.startswith("http") for source in sources)
        assert all(source.discovery_run_id == run.id for source in sources)
        assert all(source.target_id == target.id for source in sources)


async def test_re_running_does_not_duplicate_sources(session, provider):
    target = await _target(session)
    await _run(session, provider, target)
    before = await session.scalar(select(func.count(CompanySource.id)))
    await _run(session, provider, target)
    assert await session.scalar(select(func.count(CompanySource.id))) == before


async def test_raw_search_results_are_persisted_with_decisions(session, provider):
    target = await _target(session)
    run = await _run(session, provider, target)

    results = list(
        await session.scalars(select(SearchResult).where(SearchResult.discovery_run_id == run.id))
    )
    assert len(results) == 5
    assert all(row.raw for row in results), "the original payload must be kept"

    rejected = [row for row in results if not row.accepted]
    assert {row.rejection_reason for row in rejected} == {"excluded_domain", "document_or_asset"}

    accepted = [row for row in results if row.accepted]
    assert {row.extracted_domain for row in accepted} == {"acme-jewels.com", "beta-gold.in"}


async def test_queries_are_persisted_for_the_run(session, provider):
    target = await _target(session)
    run = await _run(session, provider, target)

    queries = list(
        await session.scalars(select(SearchQuery).where(SearchQuery.discovery_run_id == run.id))
    )
    assert [query.query for query in queries] == provider.queries
    assert all(query.status == "completed" and query.executed_at for query in queries)


async def test_discovered_company_inherits_target_attribution(session, provider):
    target = await _target(session)
    run = await _run(session, provider, target)

    company = await session.scalar(
        select(Company).where(Company.canonical_domain == "acme-jewels.com")
    )
    assert company.industry == target.industry
    assert company.location == target.location
    assert company.first_discovery_run_id == run.id
    # Phase 1 never guesses size.
    assert company.company_size is None


async def test_a_run_whose_searches_all_fail_is_marked_failed(session):
    target = await _target(session)
    service = DiscoveryService(session, provider=FakeSearchProvider(failing=True))
    run = await service.create_run(target)

    with pytest.raises(Exception):
        await service.execute_run(run.id)

    failed = await service.runs.get(run.id)
    assert failed.status == RunStatus.FAILED
    assert failed.error_message
    assert failed.completed_at is not None


async def test_a_run_with_no_usable_results_still_completes(session):
    target = await _target(session)
    provider = FakeSearchProvider(default=[result("https://www.justdial.com/x", "Directory")])
    run = await _run(session, provider, target)

    assert run.status == RunStatus.COMPLETED
    assert run.new_companies_count == 0
    assert run.rejected_results_count == 1


async def test_a_completed_run_is_not_executed_twice(session, provider):
    target = await _target(session)
    service = DiscoveryService(session, provider=provider)
    run = await service.create_run(target)
    await service.execute_run(run.id)
    queries_after_first = len(provider.queries)

    await service.execute_run(run.id)
    assert len(provider.queries) == queries_after_first


async def test_a_blocked_search_is_reported_as_blocked_not_as_no_results(session):
    """When a provider refuses us, later empty responses are the same refusal.
    Reporting them as '0 results' would tell the user their target is bad when
    the search engine is the problem."""
    from app.core.errors import ProviderError

    target = await _target(session)

    class RefusesAfterFirst(FakeSearchProvider):
        """Mirrors the real endpoint: an explicit challenge, then silence."""

        def __init__(self):
            super().__init__(default=[])
            self.calls = 0

        async def search(self, query: str, *, limit: int = 20):
            self.calls += 1
            if self.calls == 1:
                raise ProviderError(
                    "Serving a bot-check page instead of results.",
                    details={"provider": "fake", "retryable": True, "needs_searxng": True},
                )
            return []

    service = DiscoveryService(session, provider=RefusesAfterFirst())
    run = await service.create_run(target)

    with pytest.raises(ProviderError):
        await service.execute_run(run.id)

    failed = await service.runs.get(run.id)
    assert failed.status == RunStatus.FAILED
    assert "bot-check" in (failed.error_message or "").lower()

    # Every query is marked failed, not quietly "completed with 0 results".
    queries = await service.runs.queries_for_run(run.id)
    assert queries
    assert all(query.status == "failed" for query in queries)
