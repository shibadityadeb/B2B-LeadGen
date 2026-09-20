"""The Phase 2 research pipeline.

Stages, each of which commits real state to ``research_runs`` before the next
begins, so the UI reports actual progress:

    load company
    -> ingest Phase 1 pages       (already-crawled first-party content)
    -> discover public sources    (research provider)
    -> retrieve sources           (crawler provider, robots-respecting)
    -> extract evidence           (rules, then optionally an LLM)
    -> detect contradictions
    -> derive signals
    -> discover decision makers
    -> match UBM capabilities -> opportunity hypotheses
    -> render the research brief

Every stage is a separate method taking explicit inputs, so each can be
exercised on its own in tests.

Idempotency: sources key on (company, url) and everything derived keys on a
fingerprint. A second run updates rows and records that the observation was
seen again; it never deletes history.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError, ProviderError
from app.core.logging import get_logger
from app.models import (
    Company,
    CompanyPage,
    Contradiction,
    DecisionMaker,
    Evidence,
    Opportunity,
    ResearchRun,
    ResearchSource,
    Signal,
)
from app.models.enums import (
    CompanyStatus,
    EvidenceType,
    ObservationState,
    PageType,
    ResearchSourceType,
    ResearchStage,
    ResearchStatus,
    RetrievalStatus,
    SourceReliability,
)
from app.providers.crawler.base import CrawlerProvider
from app.providers.crawler.registry import get_crawler_provider
from app.providers.llm.base import LLMProvider
from app.providers.llm.registry import get_llm_provider
from app.providers.people.base import DecisionMakerProvider
from app.providers.people.registry import get_people_provider
from app.providers.research.base import ResearchSourceProvider
from app.providers.research.registry import get_research_provider
from app.repositories.companies import CompanyPageRepository, CompanyRepository
from app.repositories.research import (
    BriefRepository,
    CapabilityRepository,
    ContradictionRepository,
    DecisionMakerRepository,
    EvidenceRepository,
    OpportunityRepository,
    ResearchRunRepository,
    ResearchSourceRepository,
    SignalRepository,
)
from app.services import capability_matching, confidence as confidence_service
from app.services import contradictions as contradiction_service
from app.services import evidence_extraction, freshness as freshness_service
from app.services import llm_reasoning, signal_engine
from app.services.capability_seed import SEED_CAPABILITIES
from app.services.fingerprints import (
    content_hash,
    decision_maker_fingerprint,
    evidence_fingerprint,
    opportunity_fingerprint,
    signal_fingerprint,
)
from app.services.normalization import extract_domain, normalize_url, root_url
from app.services.page_classifier import classify_page
from app.services.research_brief import build_profile, render_brief
from app.services.robots import RobotsPolicy

logger = get_logger(__name__)

# Phase 1 page types map onto research source types one-for-one.
_PAGE_TYPE_TO_SOURCE_TYPE = {
    PageType.HOME: ResearchSourceType.COMPANY_WEBSITE,
    PageType.ABOUT: ResearchSourceType.COMPANY_ABOUT,
    PageType.PRODUCTS: ResearchSourceType.COMPANY_PRODUCTS,
    PageType.SERVICES: ResearchSourceType.COMPANY_SERVICES,
    PageType.CONTACT: ResearchSourceType.COMPANY_CONTACT,
    PageType.NEWS: ResearchSourceType.COMPANY_NEWS,
    PageType.BLOG: ResearchSourceType.COMPANY_BLOG,
    PageType.CAREERS: ResearchSourceType.COMPANY_CAREERS,
    PageType.OTHER: ResearchSourceType.OTHER,
}

# Pages people are listed on, used for decision-maker discovery. Company
# press and news pages are included because appointments are usually
# announced there; the first-party restriction in the stage still applies,
# so a third-party article can never contribute a person.
_PEOPLE_SOURCE_TYPES = {
    ResearchSourceType.COMPANY_ABOUT,
    ResearchSourceType.COMPANY_CONTACT,
    ResearchSourceType.COMPANY_WEBSITE,
    ResearchSourceType.COMPANY_NEWS,
    ResearchSourceType.COMPANY_BLOG,
    ResearchSourceType.PRESS_RELEASE,
    ResearchSourceType.OTHER,
}

# Additional on-site paths worth looking for beyond the Phase 1 crawl.
_EXTRA_PATHS = (
    "/about", "/about-us", "/team", "/our-team", "/leadership", "/management",
    "/news", "/press", "/media", "/blog", "/events", "/careers", "/contact",
)


@dataclass
class StageResult:
    """What a stage produced, for the caller to fold into run counters."""

    created: int = 0
    updated: int = 0
    failed: int = 0


class ResearchOrchestrator:
    def __init__(
        self,
        session: AsyncSession,
        *,
        research_provider: ResearchSourceProvider | None = None,
        crawler: CrawlerProvider | None = None,
        people_provider: DecisionMakerProvider | None = None,
        llm: LLMProvider | None = None,
    ):
        self.session = session
        self.companies = CompanyRepository(session)
        self.company_pages = CompanyPageRepository(session)
        self.runs = ResearchRunRepository(session)
        self.sources = ResearchSourceRepository(session)
        self.evidence = EvidenceRepository(session)
        self.signals = SignalRepository(session)
        self.capabilities = CapabilityRepository(session)
        self.opportunities = OpportunityRepository(session)
        self.people = DecisionMakerRepository(session)
        self.contradictions = ContradictionRepository(session)
        self.briefs = BriefRepository(session)

        self._research_provider = research_provider
        self._crawler = crawler
        self._people_provider = people_provider
        self._llm = llm

    # -- lazily resolved providers ---------------------------------------- #

    @property
    def research_provider(self) -> ResearchSourceProvider:
        if self._research_provider is None:
            self._research_provider = get_research_provider()
        return self._research_provider

    @property
    def crawler(self) -> CrawlerProvider:
        if self._crawler is None:
            self._crawler = get_crawler_provider()
        return self._crawler

    @property
    def people_provider(self) -> DecisionMakerProvider:
        if self._people_provider is None:
            self._people_provider = get_people_provider()
        return self._people_provider

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = get_llm_provider()
        return self._llm

    # -- entry points ------------------------------------------------------ #

    async def create_run(self, company: Company) -> ResearchRun:
        run = await self.runs.create(
            company_id=company.id,
            search_provider=getattr(self.research_provider, "name", None),
            crawler_provider=getattr(self.crawler, "name", None),
            llm_provider=self.llm.name if self.llm.enabled else None,
        )
        await self.session.commit()
        return run

    async def execute(self, run_id: int) -> ResearchRun:
        run = await self.runs.get_with_company(run_id)
        if run is None:
            raise NotFoundError(f"Research run {run_id} not found")
        if run.status in (ResearchStatus.RESEARCHING, ResearchStatus.COMPLETED):
            logger.info("research run %s already %s; skipping", run_id, run.status)
            return run

        company = run.company
        run.started_at = datetime.now(UTC)
        run.errors = []
        await self._set_stage(run, ResearchStatus.RESEARCHING, ResearchStage.LOADING_COMPANY, 3)
        company.status = CompanyStatus.RESEARCHING
        await self.session.commit()

        try:
            await self._ensure_capabilities_seeded()

            ingested = await self._stage_ingest_pages(run, company)
            discovered = await self._stage_discover_sources(run, company)
            await self._stage_retrieve(run, company, discovered)

            sources = await self.sources.list_for_company(company.id)
            await self._stage_extract_evidence(run, company, sources)

            evidence_items = await self.evidence.list_for_company(company.id)
            await self._stage_contradictions(run, company, evidence_items)
            await self._stage_signals(run, company, evidence_items)
            await self._stage_people(run, company, sources)
            await self._stage_opportunities(run, company)
            await self._stage_brief(run, company)

            run.status = ResearchStatus.COMPLETED
            run.stage = ResearchStage.DONE
            run.progress = 100
            run.completed_at = datetime.now(UTC)
            company.status = CompanyStatus.RESEARCHED
            company.last_researched_at = run.completed_at
            company.crawl_error = None
            await self.session.commit()

            logger.info(
                "research run %s complete: %s sources, %s evidence, %s signals, %s opportunities",
                run.id, run.sources_retrieved, run.evidence_count,
                run.signals_count, run.opportunities_count,
            )
        except Exception as exc:
            await self.session.rollback()
            failed = await self.runs.get(run_id)
            if failed is not None:
                failed.status = ResearchStatus.FAILED
                failed.error_message = f"{type(exc).__name__}: {exc}"
                failed.completed_at = datetime.now(UTC)
                stale_company = await self.companies.get(failed.company_id)
                if stale_company is not None:
                    stale_company.status = CompanyStatus.RESEARCH_FAILED
                    stale_company.crawl_error = failed.error_message
                await self.session.commit()
            logger.exception("research run %s failed", run_id)
            raise

        return run

    # -- stages ------------------------------------------------------------ #

    async def _set_stage(
        self, run: ResearchRun, status: ResearchStatus, stage: ResearchStage, progress: int
    ) -> None:
        run.status = status
        run.stage = stage
        run.progress = progress
        await self.session.commit()

    async def _ensure_capabilities_seeded(self) -> None:
        """Load the capability catalogue on first use. Existing rows — including
        user edits — are left untouched."""
        if await self.capabilities.count() > 0:
            return
        for entry in SEED_CAPABILITIES:
            await self.capabilities.create(**entry, is_seed=True, active=True)
        await self.session.commit()
        logger.info("seeded %s UBM capabilities", len(SEED_CAPABILITIES))

    async def _stage_ingest_pages(self, run: ResearchRun, company: Company) -> StageResult:
        """Bring Phase 1's crawled pages into the research source store.

        Content already retrieved is not fetched again.
        """
        await self._set_stage(run, ResearchStatus.RESEARCHING, ResearchStage.COLLECTING_PAGES, 8)

        pages = await self.company_pages.list_for_company(company.id)
        result = StageResult()
        for page in pages:
            if not page.content:
                continue
            url = normalize_url(page.url) or page.url
            source_type = _PAGE_TYPE_TO_SOURCE_TYPE.get(
                PageType(page.page_type), ResearchSourceType.OTHER
            )
            _, created = await self.sources.upsert(
                company_id=company.id,
                url=url,
                research_run_id=run.id,
                company_page_id=page.id,
                domain=extract_domain(url),
                title=page.title,
                source_type=source_type,
                content=page.content,
                content_hash=content_hash(page.content),
                content_length=page.content_length or len(page.content),
                retrieval_status=RetrievalStatus.RETRIEVED,
                # The company's own website speaks for itself.
                source_reliability=SourceReliability.FIRST_PARTY,
                discovered_at=page.crawled_at,
                retrieved_at=page.crawled_at,
                published_at=evidence_extraction.published_date_from_text(page.content),
            )
            result.created += int(created)
        await self.session.commit()
        return result

    async def _stage_discover_sources(self, run: ResearchRun, company: Company) -> list:
        """Find public documents about the company, plus standard on-site paths."""
        await self._set_stage(
            run, ResearchStatus.RESEARCHING, ResearchStage.DISCOVERING_SOURCES, 18
        )

        candidates = []
        try:
            candidates = await self.research_provider.find_sources(
                company_name=company.name,
                domain=company.canonical_domain,
                location=company.location,
                industry=company.industry,
                limit=settings.research_max_sources,
            )
        except ProviderError as exc:
            # Search being unavailable degrades the run; it does not fail it,
            # because first-party pages still yield evidence.
            run.errors = [
                *(run.errors or []),
                {"stage": "discover_sources", "message": str(exc)},
            ]
            logger.warning("source discovery failed for company=%s: %s", company.id, exc)

        # Standard company paths the Phase 1 crawl may not have reached.
        base = root_url(company.website_url) or company.website_url
        known_urls = {
            source.url for source in await self.sources.list_for_company(company.id)
        }
        from app.providers.research.base import ResearchCandidate

        extra = [
            ResearchCandidate(
                url=candidate_url,
                title=None,
                snippet=None,
                source_type=_PAGE_TYPE_TO_SOURCE_TYPE.get(
                    classify_page(candidate_url), ResearchSourceType.OTHER
                ),
            )
            for path in _EXTRA_PATHS
            if (candidate_url := normalize_url(f"{base}{path}")) and candidate_url not in known_urls
        ]

        # Search-discovered URLs are known to exist; the standard paths are
        # guesses and most sites answer 404 for most of them. Trying guesses
        # first would spend the whole crawl budget on 404s, so real results
        # lead and guesses fill whatever budget is left.
        combined = [*candidates, *extra]
        run.sources_discovered = len(combined)
        await self.session.commit()
        return combined

    async def _stage_retrieve(self, run: ResearchRun, company: Company, candidates: list) -> None:
        """Fetch candidate documents, respecting robots.txt and rate limits."""
        await self._set_stage(
            run, ResearchStatus.RESEARCHING, ResearchStage.CRAWLING_SOURCES, 25
        )
        if not candidates:
            return

        robots = RobotsPolicy()
        budget = min(len(candidates), settings.research_max_pages_to_crawl)
        retrieved = 0
        failed = 0

        for index, candidate in enumerate(candidates[:budget]):
            url = normalize_url(candidate.url)
            if not url:
                continue

            existing = await self.sources.get_by_url(company.id, url)
            if existing and existing.retrieval_status == RetrievalStatus.RETRIEVED and existing.content:
                # Already have the content; do not re-fetch on a repeat run.
                continue

            domain = extract_domain(url)
            reliability = (
                SourceReliability.FIRST_PARTY
                if domain == company.canonical_domain
                else _reliability_for(candidate.source_type)
            )

            if not await robots.can_fetch(url):
                await self.sources.upsert(
                    company_id=company.id,
                    url=url,
                    research_run_id=run.id,
                    domain=domain,
                    title=candidate.title,
                    source_type=candidate.source_type,
                    retrieval_status=RetrievalStatus.SKIPPED,
                    source_reliability=reliability,
                    error_message="Disallowed by robots.txt",
                    discovered_at=datetime.now(UTC),
                    meta={"query": candidate.query} if candidate.query else {},
                )
                await self.session.commit()
                continue

            page = await self.crawler.fetch(url)
            if page.ok and page.text:
                retrieved += 1
                text = page.text
                await self.sources.upsert(
                    company_id=company.id,
                    url=url,
                    research_run_id=run.id,
                    domain=domain,
                    title=page.title or candidate.title,
                    source_type=candidate.source_type,
                    content=text,
                    content_hash=content_hash(text),
                    content_length=len(text),
                    retrieval_status=RetrievalStatus.RETRIEVED,
                    source_reliability=reliability,
                    discovered_at=datetime.now(UTC),
                    retrieved_at=datetime.now(UTC),
                    published_at=(
                        candidate.published_at
                        or evidence_extraction.published_date_from_text(text)
                    ),
                    meta={"query": candidate.query} if candidate.query else {},
                )
            else:
                failed += 1
                await self.sources.upsert(
                    company_id=company.id,
                    url=url,
                    research_run_id=run.id,
                    domain=domain,
                    title=candidate.title,
                    source_type=candidate.source_type,
                    retrieval_status=RetrievalStatus.FAILED,
                    source_reliability=reliability,
                    error_message=page.error,
                    discovered_at=datetime.now(UTC),
                )

            run.sources_failed = failed
            run.progress = 25 + int(25 * (index + 1) / budget)
            await self.session.commit()

            if settings.crawl_delay_seconds > 0 and index < budget - 1:
                await asyncio.sleep(settings.crawl_delay_seconds)

        # Report every source that now has content — pages ingested from the
        # Phase 1 crawl count too, not only what this run fetched.
        all_sources = await self.sources.list_for_company(company.id)
        run.sources_retrieved = sum(
            1 for source in all_sources if source.retrieval_status == RetrievalStatus.RETRIEVED
        )
        await self.session.commit()
        logger.info(
            "run %s retrieval: %s newly fetched, %s failed, %s total with content",
            run.id, retrieved, failed, run.sources_retrieved,
        )

    async def _stage_extract_evidence(
        self, run: ResearchRun, company: Company, sources: list[ResearchSource]
    ) -> None:
        await self._set_stage(
            run, ResearchStatus.ANALYZING, ResearchStage.EXTRACTING_EVIDENCE, 55
        )

        usable = [
            source
            for source in sources
            if source.content and source.retrieval_status == RetrievalStatus.RETRIEVED
        ]

        # --- deterministic layer (always runs) ---
        candidates: list[tuple[ResearchSource, evidence_extraction.ExtractedEvidence]] = []
        for source in usable:
            items = evidence_extraction.extract_from_text(
                source.content, company_name=company.name
            )
            items += evidence_extraction.extract_identity(
                source.content, company_name=company.name
            )
            for item in evidence_extraction.deduplicate(items):
                candidates.append((source, item))

        # --- optional model layer (adds only verifiable claims) ---
        if self.llm.enabled and usable:
            try:
                documents = [
                    (source.title or source.url, (source.content or "")[:6000])
                    for source in usable[: settings.llm_max_evidence_items]
                ]
                verified, uncertainties, stats = await llm_reasoning.extract_claims(
                    self.llm, company_name=company.name, documents=documents
                )
                run.llm_used = True
                run.errors = [
                    *(run.errors or []),
                    {"stage": "llm_extraction", "message": "LLM claim stats", "stats": stats},
                ]
                for claim in verified:
                    source = usable[claim.source_index]
                    candidates.append(
                        (
                            source,
                            evidence_extraction.ExtractedEvidence(
                                evidence_type=EvidenceType(claim.evidence_type),
                                claim=claim.claim,
                                excerpt=claim.excerpt,
                                epistemic_status=claim.epistemic_status,
                            ),
                        )
                    )
                for note in uncertainties:
                    run.errors = [
                        *(run.errors or []),
                        {"stage": "llm_uncertainty", "message": note},
                    ]
            except ProviderError as exc:
                # A model failure must never fail a run that already has
                # deterministic evidence.
                run.errors = [*(run.errors or []), {"stage": "llm", "message": str(exc)}]
                logger.warning("llm extraction failed for company=%s: %s", company.id, exc)

        await self._persist_evidence(run, company, candidates)

    async def _persist_evidence(
        self,
        run: ResearchRun,
        company: Company,
        candidates: list[tuple[ResearchSource, evidence_extraction.ExtractedEvidence]],
    ) -> None:
        fingerprints = [
            evidence_fingerprint(company.id, str(item.evidence_type), item.claim)
            for _, item in candidates
        ]
        existing = await self.evidence.by_fingerprints(company.id, fingerprints)

        seen_ids: set[int] = set()
        new_count = 0

        for (source, item), fingerprint in zip(candidates, fingerprints, strict=True):
            published_at = source.published_at
            observed_at = source.retrieved_at or datetime.now(UTC)
            freshness = freshness_service.classify(published_at, observed_at)
            scored = confidence_service.score_evidence(
                reliability=source.source_reliability,
                epistemic_status=str(item.epistemic_status),
                freshness=str(freshness.freshness),
                corroborating_sources=1,
                freshness_basis=freshness.basis,
            )

            row = existing.get(fingerprint)
            if row is None:
                row = Evidence(
                    company_id=company.id,
                    source_id=source.id,
                    research_run_id=run.id,
                    claim=item.claim,
                    excerpt=item.excerpt,
                    normalized_value=item.normalized_value,
                    evidence_type=str(item.evidence_type),
                    epistemic_status=str(item.epistemic_status),
                    observed_at=observed_at,
                    published_at=published_at,
                    confidence=scored.score,
                    confidence_level=str(scored.level),
                    confidence_components=scored.dict(),
                    extractor="rules",
                    fingerprint=fingerprint,
                    first_seen_run_id=run.id,
                    last_seen_run_id=run.id,
                    observation_state=ObservationState.NEW,
                    times_observed=1,
                )
                self.session.add(row)
                await self.session.flush()
                existing[fingerprint] = row
                new_count += 1
            else:
                # Seen before: record the re-observation, keep the original.
                row.last_seen_run_id = run.id
                row.times_observed += 1
                row.observed_at = observed_at
                row.observation_state = (
                    ObservationState.UPDATED
                    if row.excerpt != item.excerpt
                    else ObservationState.STILL_PRESENT
                )
                if row.excerpt != item.excerpt:
                    row.excerpt = item.excerpt
                row.confidence = scored.score
                row.confidence_level = str(scored.level)
                row.confidence_components = scored.dict()
            seen_ids.add(row.id)

        await self.evidence.mark_not_found(company.id, seen_ids)

        run.evidence_count = len(seen_ids)
        run.new_evidence_count = new_count
        await self.session.commit()

    async def _stage_contradictions(
        self, run: ResearchRun, company: Company, evidence_items: list[Evidence]
    ) -> None:
        detected = contradiction_service.detect(evidence_items)
        created = 0
        for item in detected:
            if await self.contradictions.exists(
                company.id, item.evidence_a_id, item.evidence_b_id
            ):
                continue
            self.session.add(
                Contradiction(
                    company_id=company.id,
                    research_run_id=run.id,
                    subject=item.subject,
                    evidence_a_id=item.evidence_a_id,
                    evidence_b_id=item.evidence_b_id,
                    status=str(item.status),
                    preferred_evidence_id=item.preferred_evidence_id,
                    explanation=item.explanation,
                )
            )
            created += 1
        run.contradictions_count = len(detected)
        await self.session.commit()
        self._contradicted_ids = {
            id_ for item in detected for id_ in (item.evidence_a_id, item.evidence_b_id)
        }

    async def _stage_signals(
        self, run: ResearchRun, company: Company, evidence_items: list[Evidence]
    ) -> None:
        await self._set_stage(run, ResearchStatus.ANALYZING, ResearchStage.DERIVING_SIGNALS, 68)

        derived = signal_engine.derive_signals(
            evidence_items,
            company_name=company.name,
            contradicted_evidence_ids=getattr(self, "_contradicted_ids", set()),
        )

        for item in derived:
            fingerprint = signal_fingerprint(company.id, item.signal_type)
            row = await self.signals.by_fingerprint(company.id, fingerprint)
            if row is None:
                row = Signal(
                    company_id=company.id,
                    research_run_id=run.id,
                    signal_type=item.signal_type,
                    fingerprint=fingerprint,
                    observation_state=ObservationState.NEW,
                )
                self.session.add(row)
            else:
                row.observation_state = ObservationState.UPDATED
                row.research_run_id = run.id

            row.title = item.title
            row.description = item.description
            row.strength = item.strength
            row.freshness = str(item.freshness)
            row.confidence = item.confidence
            row.confidence_level = str(item.confidence_level)
            row.confidence_components = item.confidence_components
            row.latest_evidence_at = item.latest_evidence_at
            row.evidence_count = item.evidence_count
            await self.session.flush()

            await self.session.refresh(row, ["evidence_links"])
            await self.signals.replace_evidence_links(row, item.evidence_ids)

        run.signals_count = len(derived)
        await self.session.commit()

    async def _stage_people(
        self, run: ResearchRun, company: Company, sources: list[ResearchSource]
    ) -> None:
        await self._set_stage(run, ResearchStatus.ANALYZING, ResearchStage.FINDING_PEOPLE, 78)

        # Only the company's own pages. A news article naming a marketing head
        # is usually naming someone at a *different* company, and attributing
        # them here would be worse than finding nobody.
        documents = [
            (source.url, source.title or "", source.content or "")
            for source in sources
            if source.content
            and source.source_reliability == SourceReliability.FIRST_PARTY
            and (
                source.source_type in _PEOPLE_SOURCE_TYPES
                or "team" in source.url
                or "leadership" in source.url
            )
        ]
        by_url = {source.url: source for source in sources}

        discovered = await self.people_provider.find_people(
            company_name=company.name, documents=documents
        )

        count = 0
        for person in discovered:
            fingerprint = decision_maker_fingerprint(company.id, person.name, person.role)
            row = await self.people.by_fingerprint(company.id, fingerprint)
            source = by_url.get(person.source_url or "")

            # A named person read off a company page is better evidenced than
            # a bare role, and the score reflects only that.
            scored = confidence_service.score_evidence(
                reliability=(
                    source.source_reliability if source else SourceReliability.UNKNOWN
                ),
                epistemic_status="known" if person.name else "inferred",
                freshness="recent" if person.name else "unknown",
                corroborating_sources=1,
            )

            if row is None:
                row = DecisionMaker(
                    company_id=company.id,
                    fingerprint=fingerprint,
                    observation_state=ObservationState.NEW,
                )
                self.session.add(row)
                count += 1
            else:
                row.observation_state = ObservationState.STILL_PRESENT

            row.research_run_id = run.id
            row.name = person.name
            row.role = person.role
            row.role_category = person.role_category
            row.email = person.email
            row.phone = person.phone
            row.profile_url = person.profile_url
            row.source_id = source.id if source else None
            row.verification_status = person.verification_status
            row.excerpt = person.excerpt
            row.confidence = scored.score
            row.confidence_level = str(scored.level)
            await self.session.flush()

        run.decision_makers_count = len(discovered)
        await self.session.commit()

    async def _stage_opportunities(self, run: ResearchRun, company: Company) -> None:
        await self._set_stage(
            run, ResearchStatus.ANALYZING, ResearchStage.MATCHING_CAPABILITIES, 86
        )

        stored_signals = await self.signals.list_for_company(company.id)
        capabilities = await self.capabilities.list(active_only=True)

        derived = [
            signal_engine.DerivedSignal(
                signal_type=signal.signal_type,
                title=signal.title,
                description=signal.description,
                evidence_ids=[link.evidence_id for link in signal.evidence_links],
                strength=signal.strength,
                freshness=signal.freshness,
                confidence=signal.confidence,
                confidence_level=signal.confidence_level,
                confidence_components=signal.confidence_components,
                latest_evidence_at=signal.latest_evidence_at,
                evidence_count=signal.evidence_count,
                distinct_sources=(signal.confidence_components or {})
                .get("distinct_sources", 1),
            )
            for signal in stored_signals
        ]
        signal_ids_by_type = {signal.signal_type: signal.id for signal in stored_signals}

        matches = capability_matching.match(derived, capabilities, company_name=company.name)

        for item in matches:
            fingerprint = opportunity_fingerprint(company.id, item.capability_id)
            row = await self.opportunities.by_fingerprint(company.id, fingerprint)
            if row is None:
                row = Opportunity(
                    company_id=company.id,
                    capability_id=item.capability_id,
                    fingerprint=fingerprint,
                    observation_state=ObservationState.NEW,
                )
                self.session.add(row)
            else:
                row.observation_state = ObservationState.UPDATED

            row.research_run_id = run.id
            row.title = item.title
            row.description = item.description
            row.why_relevant = item.why_relevant
            row.confidence = item.confidence
            row.confidence_level = str(item.confidence_level)
            row.confidence_components = item.confidence_components
            row.freshness = str(item.freshness)
            # A human "dismissed" verdict is never overwritten by a re-run.
            if row.status != "dismissed":
                row.status = str(item.status)
            row.evidence_count = item.evidence_count
            await self.session.flush()

            await self.session.refresh(row, ["evidence_links", "signal_links"])
            await self.opportunities.link(
                row,
                evidence_ids=item.evidence_ids,
                signal_ids=[
                    signal_ids_by_type[signal_type]
                    for signal_type in item.signal_types
                    if signal_type in signal_ids_by_type
                ],
            )

        run.opportunities_count = len(matches)
        await self.session.commit()

    async def _stage_brief(self, run: ResearchRun, company: Company) -> None:
        await self._set_stage(run, ResearchStatus.ANALYZING, ResearchStage.WRITING_BRIEF, 94)

        profile = await build_profile(self.session, company, run)
        await self.briefs.upsert(
            company_id=company.id,
            research_run_id=run.id,
            markdown=render_brief(profile),
            profile=profile,
            generated_by="llm+deterministic" if run.llm_used else "deterministic",
        )
        await self.session.commit()


def _reliability_for(source_type: str) -> str:
    """How much weight an off-site source carries."""
    return {
        ResearchSourceType.PRESS_RELEASE: SourceReliability.PRESS,
        ResearchSourceType.NEWS: SourceReliability.PRESS,
        ResearchSourceType.EVENT: SourceReliability.THIRD_PARTY,
        ResearchSourceType.PUBLIC_PROFILE: SourceReliability.THIRD_PARTY,
        ResearchSourceType.SEARCH_RESULT: SourceReliability.AGGREGATED,
    }.get(source_type, SourceReliability.UNKNOWN)
