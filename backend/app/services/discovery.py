"""The discovery pipeline.

Stages, each of which writes real state to the ``discovery_runs`` row before
moving on, so the UI reports actual progress rather than an animation:

  1. generate queries        -> search_queries
  2. execute searches        -> search_results (raw payload kept verbatim)
  3. normalize + deduplicate -> company candidates keyed by canonical domain
  4. persist                 -> companies + company_sources (evidence)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError, ProviderError
from app.core.logging import get_logger
from app.models import Company, DiscoveryRun, SearchQuery, SearchResult, Target
from app.models.enums import CompanyStatus, RunStage, RunStatus, SourceType
from app.providers.search.base import SearchProvider, SearchResultItem
from app.providers.search.registry import get_search_provider
from app.repositories.companies import CompanyRepository, CompanySourceRepository
from app.repositories.runs import DiscoveryRunRepository
from app.services.candidates import CandidateExtraction, extract_candidates
from app.services.query_generation import generate_queries

logger = get_logger(__name__)


class DiscoveryService:
    def __init__(self, session: AsyncSession, provider: SearchProvider | None = None):
        self.session = session
        self.runs = DiscoveryRunRepository(session)
        self.companies = CompanyRepository(session)
        self.sources = CompanySourceRepository(session)
        self._provider = provider

    @property
    def provider(self) -> SearchProvider:
        if self._provider is None:
            self._provider = get_search_provider()
        return self._provider

    # ------------------------------------------------------------------ #
    # entry points
    # ------------------------------------------------------------------ #

    async def create_run(self, target: Target) -> DiscoveryRun:
        """Create a queued run. The job queue picks it up from here."""
        run = await self.runs.create(target_id=target.id, search_provider=self.provider.name)
        await self.session.commit()
        return run

    async def execute_run(self, run_id: int) -> DiscoveryRun:
        run = await self.runs.get_with_target(run_id)
        if run is None:
            raise NotFoundError(f"Discovery run {run_id} not found")
        if run.status in (RunStatus.RUNNING, RunStatus.COMPLETED):
            logger.info("run %s already %s; skipping", run_id, run.status)
            return run

        run.status = RunStatus.RUNNING
        run.stage = RunStage.GENERATING_QUERIES
        run.started_at = datetime.now(UTC)
        run.progress = 5
        run.errors = []
        await self.session.commit()

        try:
            queries = await self._stage_generate_queries(run, run.target)
            results = await self._stage_execute_searches(run, queries)
            extraction = await self._stage_normalize(run, results)
            await self._stage_persist(run, extraction, results)

            run.status = RunStatus.COMPLETED
            run.stage = RunStage.DONE
            run.progress = 100
            run.completed_at = datetime.now(UTC)
            await self.session.commit()
            logger.info(
                "run %s completed: %s queries, %s results, %s new companies",
                run.id, run.queries_count, run.results_count, run.new_companies_count,
            )
        except Exception as exc:
            await self.session.rollback()
            failed = await self.runs.get(run_id)
            if failed is not None:
                failed.status = RunStatus.FAILED
                failed.error_message = f"{type(exc).__name__}: {exc}"
                failed.completed_at = datetime.now(UTC)
                await self.session.commit()
            logger.exception("run %s failed", run_id)
            raise

        return run

    # ------------------------------------------------------------------ #
    # stages
    # ------------------------------------------------------------------ #

    async def _stage_generate_queries(self, run: DiscoveryRun, target: Target) -> list[SearchQuery]:
        generated = generate_queries(
            industry=target.industry,
            location=target.location,
            country=target.country,
            keywords=list(target.keywords or []),
            search_context=target.search_context,
            max_queries=settings.search_max_queries_per_run,
        )
        if not generated:
            raise ProviderError(
                "No search queries could be generated. The target needs an "
                "industry or at least one keyword."
            )

        rows = [
            SearchQuery(
                discovery_run_id=run.id,
                query=item.query,
                template=item.template,
                provider=self.provider.name,
                status="pending",
            )
            for item in generated
        ]
        self.session.add_all(rows)
        run.queries_count = len(rows)
        run.stage = RunStage.SEARCHING
        run.progress = 10
        await self.session.commit()
        return rows

    async def _stage_execute_searches(
        self, run: DiscoveryRun, queries: list[SearchQuery]
    ) -> list[tuple[SearchResult, SearchResultItem]]:
        collected: list[tuple[SearchResult, SearchResultItem]] = []
        seen_urls: set[str] = set()

        for index, query in enumerate(queries, start=1):
            try:
                items = await self.provider.search(
                    query.query, limit=settings.search_results_per_query
                )
                query.status = "completed"
                query.results_count = len(items)
            except ProviderError as exc:
                query.status = "failed"
                query.error_message = str(exc)
                run.failed_queries_count += 1
                run.errors = [
                    *(run.errors or []),
                    {"stage": "search", "query": query.query, "message": str(exc)},
                ]
                items = []
                logger.warning("query failed run=%s query=%r error=%s", run.id, query.query, exc)

            query.executed_at = datetime.now(UTC)

            for item in items:
                # Identical URLs returned by several queries are stored once.
                if item.url in seen_urls:
                    continue
                seen_urls.add(item.url)
                row = SearchResult(
                    search_query_id=query.id,
                    discovery_run_id=run.id,
                    title=item.title,
                    url=item.url,
                    snippet=item.snippet,
                    source_engine=item.source_engine,
                    position=item.position,
                    discovered_at=item.discovered_at,
                    raw=item.raw or {},
                )
                self.session.add(row)
                collected.append((row, item))

            run.results_count = len(collected)
            run.progress = 10 + int(60 * index / max(len(queries), 1))
            await self.session.commit()

            if settings.search_delay_seconds > 0 and index < len(queries):
                await asyncio.sleep(settings.search_delay_seconds)

        if run.failed_queries_count == len(queries) and queries:
            raise ProviderError(
                "Every search query failed. Check that the search provider is "
                "running and reachable (Settings -> Search Provider)."
            )
        return collected

    async def _stage_normalize(
        self, run: DiscoveryRun, collected: list[tuple[SearchResult, SearchResultItem]]
    ) -> CandidateExtraction:
        run.stage = RunStage.NORMALIZING
        run.progress = 75
        await self.session.commit()

        extraction = extract_candidates([item for _, item in collected])

        # Mirror each decision back onto its stored search_result row.
        for decision in extraction.decisions:
            row = collected[decision.result_index][0]
            row.accepted = decision.accepted
            row.extracted_domain = decision.domain
            row.rejection_reason = decision.rejection_reason

        run.unique_domains_count = len(extraction.candidates)
        run.rejected_results_count = extraction.rejected_count
        await self.session.commit()
        return extraction

    async def _stage_persist(
        self,
        run: DiscoveryRun,
        extraction: CandidateExtraction,
        collected: list[tuple[SearchResult, SearchResultItem]],
    ) -> None:
        run.stage = RunStage.SAVING
        run.progress = 85
        await self.session.commit()

        target = run.target
        domains = [candidate.domain for candidate in extraction.candidates]
        existing = await self.companies.get_by_domains(domains)

        new_count = 0
        duplicate_count = 0

        for candidate in extraction.candidates:
            company = existing.get(candidate.domain)
            if company is None:
                company = await self._create_company(candidate, run, target)
                new_count += 1
            else:
                duplicate_count += 1

            await self._attach_sources(company, candidate, run, target, collected)

        run.new_companies_count = new_count
        run.duplicate_companies_count = duplicate_count
        run.progress = 95
        await self.session.commit()

    async def _create_company(self, candidate, run: DiscoveryRun, target: Target) -> Company:
        return await self.companies.create(
            name=candidate.name,
            canonical_domain=candidate.domain,
            website_url=candidate.website_url,
            # Inherited from the target: these describe why the company was
            # looked for, and are the only attribution Phase 1 can honestly make.
            industry=target.industry,
            location=target.location,
            country=target.country,
            company_size=None,
            status=CompanyStatus.DISCOVERED,
            first_discovery_run_id=run.id,
        )

    async def _attach_sources(
        self,
        company: Company,
        candidate,
        run: DiscoveryRun,
        target: Target,
        collected: list[tuple[SearchResult, SearchResultItem]],
    ) -> None:
        urls = [evidence.url for evidence in candidate.evidence]
        already_stored = await self.sources.existing_urls(company.id, urls)

        for evidence in candidate.evidence:
            if evidence.url in already_stored:
                continue
            already_stored.add(evidence.url)
            self.sources.add(
                company_id=company.id,
                discovery_run_id=run.id,
                target_id=target.id,
                search_result_id=collected[evidence.result_index][0].id,
                url=evidence.url,
                title=evidence.title,
                snippet=evidence.snippet,
                source_type=SourceType.SEARCH_RESULT,
                source_engine=evidence.source_engine,
                discovered_at=evidence.discovered_at,
            )
        await self.session.flush()
