"""Phase 2 API: research runs, evidence, signals, opportunities, people."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import QueueDep, SessionDep
from app.core.errors import NotFoundError, ValidationError
from app.models.enums import CompanyStatus, ObservationState, ResearchStatus
from app.repositories.companies import CompanyRepository
from app.repositories.research import (
    BriefRepository,
    ContradictionRepository,
    DecisionMakerRepository,
    EvidenceRepository,
    OpportunityRepository,
    ResearchRunRepository,
    ResearchSourceRepository,
    SignalRepository,
)
from app.schemas.common import Page
from app.schemas.research import (
    BulkResearchRequest,
    BulkResearchResponse,
    CompanyResearchState,
    ContradictionRead,
    DecisionMakerRead,
    EvidenceRead,
    OpportunityRead,
    OpportunityStatusUpdate,
    ResearchBriefRead,
    ResearchRunDetail,
    ResearchRunRead,
    ResearchSourceRead,
    SignalRead,
)
from app.services.research_orchestrator import ResearchOrchestrator
from app.services.research_serialization import (
    decision_maker_to_schema,
    evidence_to_schema,
    opportunity_to_schema,
    run_to_schema,
    signal_to_schema,
)
from app.workers.jobs import RESEARCH_JOB

router = APIRouter(prefix="/api", tags=["research"])


async def _require_company(session, company_id: int):
    company = await CompanyRepository(session).get(company_id)
    if company is None:
        raise NotFoundError(f"Company {company_id} not found")
    return company


# --------------------------------------------------------------------------- #
# running research
# --------------------------------------------------------------------------- #


@router.post(
    "/companies/{company_id}/research",
    response_model=ResearchRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_research(company_id: int, session: SessionDep, queue: QueueDep):
    company = await _require_company(session, company_id)

    runs = ResearchRunRepository(session)
    latest = await runs.latest_for_company(company_id)
    if latest and latest.status in (ResearchStatus.QUEUED, ResearchStatus.RESEARCHING, ResearchStatus.ANALYZING):
        # Re-issuing the request returns the run already in flight rather than
        # starting a second crawl of the same site.
        return run_to_schema(latest)

    orchestrator = ResearchOrchestrator(session)
    run = await orchestrator.create_run(company)
    company.status = CompanyStatus.RESEARCHING
    await session.commit()

    await queue.enqueue(RESEARCH_JOB, run_id=run.id)
    await session.refresh(run)
    return run_to_schema(run)


@router.post(
    "/companies/research/bulk",
    response_model=BulkResearchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_bulk_research(
    payload: BulkResearchRequest, session: SessionDep, queue: QueueDep
):
    """Queue research for several companies.

    Concurrency is bounded by the job queue, so this enqueues rather than
    running anything here — a large selection cannot fan out into unbounded
    simultaneous crawling.
    """
    companies = CompanyRepository(session)
    runs = ResearchRunRepository(session)
    orchestrator = ResearchOrchestrator(session)

    queued: list[ResearchRunRead] = []
    skipped: list[dict] = []

    for company_id in payload.company_ids:
        company = await companies.get(company_id)
        if company is None:
            skipped.append({"company_id": company_id, "reason": "Company not found"})
            continue

        latest = await runs.latest_for_company(company_id)
        if latest and latest.status in (
            ResearchStatus.QUEUED,
            ResearchStatus.RESEARCHING,
            ResearchStatus.ANALYZING,
        ):
            skipped.append(
                {
                    "company_id": company_id,
                    "company_name": company.name,
                    "reason": "Research is already running",
                    "run_id": latest.id,
                }
            )
            continue

        run = await orchestrator.create_run(company)
        company.status = CompanyStatus.RESEARCHING
        await session.commit()
        await queue.enqueue(RESEARCH_JOB, run_id=run.id)
        await session.refresh(run)
        queued.append(run_to_schema(run))

    return BulkResearchResponse(queued=queued, skipped=skipped)


# --------------------------------------------------------------------------- #
# reading research
# --------------------------------------------------------------------------- #


@router.get("/companies/{company_id}/research", response_model=CompanyResearchState)
async def get_company_research(company_id: int, session: SessionDep):
    company = await _require_company(session, company_id)

    runs_repo = ResearchRunRepository(session)
    history = await runs_repo.list_for_company(company_id, limit=20)
    latest = history[0] if history else None

    brief_row = await BriefRepository(session).latest_for_company(company_id)
    brief = (
        ResearchBriefRead(
            research_run_id=brief_row.research_run_id,
            markdown=brief_row.markdown,
            profile=brief_row.profile,
            generated_by=brief_row.generated_by,
            created_at=brief_row.created_at,
        )
        if brief_row
        else None
    )

    # Counts must match what each tab actually renders, so retired items are
    # excluded here exactly as they are in the endpoints above.
    all_evidence = await EvidenceRepository(session).list_for_company(company_id)
    live_signals = [
        s
        for s in await SignalRepository(session).list_for_company(company_id)
        if s.observation_state != ObservationState.NOT_FOUND
    ]
    live_opportunities = [
        o
        for o in await OpportunityRepository(session).list_for_company(company_id)
        if o.observation_state != ObservationState.NOT_FOUND
    ]
    counts = {
        "sources": await ResearchSourceRepository(session).count_for_company(company_id),
        # What the tab shows: items still visible on the web. The ones we can
        # no longer find sit behind a disclosure inside the tab.
        "evidence": sum(
            1 for e in all_evidence if e.observation_state != ObservationState.NOT_FOUND
        ),
        "evidence_retired": sum(
            1 for e in all_evidence if e.observation_state == ObservationState.NOT_FOUND
        ),
        "signals": len(live_signals),
        "opportunities": len(live_opportunities),
        "decision_makers": len(await DecisionMakerRepository(session).list_for_company(company_id)),
        "contradictions": len(await ContradictionRepository(session).list_for_company(company_id)),
        "runs": len(history),
    }

    research_status = (
        latest.status if latest else ResearchStatus.NOT_STARTED
    )
    return CompanyResearchState(
        company_id=company.id,
        research_status=str(research_status),
        latest_run=run_to_schema(latest) if latest else None,
        runs=[run_to_schema(run) for run in history],
        counts=counts,
        brief=brief,
    )


@router.get("/companies/{company_id}/evidence", response_model=list[EvidenceRead])
async def get_company_evidence(
    company_id: int,
    session: SessionDep,
    evidence_type: str | None = None,
    ids: str | None = Query(None, description="Comma-separated evidence ids"),
):
    await _require_company(session, company_id)
    items = await EvidenceRepository(session).list_for_company(
        company_id, evidence_type=evidence_type
    )
    if ids:
        try:
            wanted = {int(part) for part in ids.split(",") if part.strip()}
        except ValueError as exc:
            raise ValidationError("`ids` must be a comma-separated list of integers.") from exc
        items = [item for item in items if item.id in wanted]
    return [evidence_to_schema(item) for item in items]


@router.get("/companies/{company_id}/signals", response_model=list[SignalRead])
async def get_company_signals(
    company_id: int, session: SessionDep, include_retired: bool = False
):
    """Current signals. Ones whose evidence has since disappeared are kept in
    the database but excluded unless explicitly requested."""
    await _require_company(session, company_id)
    signals = await SignalRepository(session).list_for_company(company_id)
    if not include_retired:
        signals = [s for s in signals if s.observation_state != ObservationState.NOT_FOUND]
    return [signal_to_schema(signal) for signal in signals]


@router.get("/companies/{company_id}/opportunities", response_model=list[OpportunityRead])
async def get_company_opportunities(
    company_id: int, session: SessionDep, include_retired: bool = False
):
    """Current opportunities, excluding any whose supporting signals are gone."""
    await _require_company(session, company_id)
    items = await OpportunityRepository(session).list_for_company(company_id)
    if not include_retired:
        items = [i for i in items if i.observation_state != ObservationState.NOT_FOUND]
    return [opportunity_to_schema(item) for item in items]


@router.get("/companies/{company_id}/decision-makers", response_model=list[DecisionMakerRead])
async def get_company_decision_makers(company_id: int, session: SessionDep):
    await _require_company(session, company_id)
    people = await DecisionMakerRepository(session).list_for_company(company_id)
    return [decision_maker_to_schema(person) for person in people]


@router.get("/companies/{company_id}/research-sources", response_model=list[ResearchSourceRead])
async def get_company_research_sources(company_id: int, session: SessionDep):
    await _require_company(session, company_id)
    return await ResearchSourceRepository(session).list_for_company(company_id)


@router.get("/companies/{company_id}/contradictions", response_model=list[ContradictionRead])
async def get_company_contradictions(company_id: int, session: SessionDep):
    await _require_company(session, company_id)
    return await ContradictionRepository(session).list_for_company(company_id)


@router.get("/companies/{company_id}/brief", response_model=ResearchBriefRead)
async def get_company_brief(company_id: int, session: SessionDep):
    await _require_company(session, company_id)
    brief = await BriefRepository(session).latest_for_company(company_id)
    if brief is None:
        raise NotFoundError(f"No research brief exists for company {company_id} yet")
    return ResearchBriefRead(
        research_run_id=brief.research_run_id,
        markdown=brief.markdown,
        profile=brief.profile,
        generated_by=brief.generated_by,
        created_at=brief.created_at,
    )


# --------------------------------------------------------------------------- #
# research runs
# --------------------------------------------------------------------------- #


@router.get("/research-runs", response_model=Page[ResearchRunRead])
async def list_research_runs(
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    runs, total = await ResearchRunRepository(session).list_all(
        limit=page_size, offset=(page - 1) * page_size
    )
    return Page[ResearchRunRead](
        items=[run_to_schema(run) for run in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/research-runs/{run_id}", response_model=ResearchRunDetail)
async def get_research_run(run_id: int, session: SessionDep):
    run = await ResearchRunRepository(session).get_with_company(run_id)
    if run is None:
        raise NotFoundError(f"Research run {run_id} not found")

    sources = [
        source
        for source in await ResearchSourceRepository(session).list_for_company(run.company_id)
        if source.research_run_id == run_id
    ]
    brief = await BriefRepository(session).for_run(run_id)

    return ResearchRunDetail(
        **run_to_schema(run).model_dump(),
        sources=[ResearchSourceRead.model_validate(source, from_attributes=True) for source in sources],
        brief_markdown=brief.markdown if brief else None,
        brief_profile=brief.profile if brief else None,
    )


@router.patch("/opportunities/{opportunity_id}", response_model=OpportunityRead)
async def update_opportunity_status(
    opportunity_id: int, payload: OpportunityStatusUpdate, session: SessionDep
):
    """Let a human accept or dismiss a hypothesis. A dismissal survives
    subsequent research runs."""
    from app.models import Opportunity

    opportunity = await session.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise NotFoundError(f"Opportunity {opportunity_id} not found")

    opportunity.status = payload.status
    await session.commit()

    refreshed = await OpportunityRepository(session).list_for_company(opportunity.company_id)
    match = next((item for item in refreshed if item.id == opportunity_id), None)
    return opportunity_to_schema(match or opportunity)
