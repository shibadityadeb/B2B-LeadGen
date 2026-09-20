from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.models.enums import CompanyStatus
from app.repositories.companies import (
    CompanyPageRepository,
    CompanyRepository,
    CompanySourceRepository,
)
from app.repositories.research import (
    CapabilityRepository,
    DecisionMakerRepository,
    EvidenceRepository,
    OpportunityRepository,
    ResearchRunRepository,
    SignalRepository,
)
from app.repositories.runs import DiscoveryRunRepository
from app.repositories.targets import TargetRepository
from app.schemas.system import (
    DashboardStats,
    RecentCompanySummary,
    RecentRunSummary,
    SystemStatus,
)
from app.services.system_status import collect_status

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/status", response_model=SystemStatus)
async def system_status(session: SessionDep):
    return await collect_status(session)


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(session: SessionDep):
    targets = TargetRepository(session)
    companies = CompanyRepository(session)
    runs = DiscoveryRunRepository(session)

    recent_runs, runs_total = await runs.list(limit=5)
    recent_companies = await companies.recent(limit=6)

    research_runs = ResearchRunRepository(session)
    _, research_total = await research_runs.list_all(limit=1, offset=0)
    evidence = EvidenceRepository(session)

    # "Fresh" means published recently, not merely re-observed recently.
    from datetime import UTC, datetime, timedelta

    from app.core.config import settings

    cutoff = datetime.now(UTC) - timedelta(days=settings.freshness_recent_days)

    return DashboardStats(
        targets_count=await targets.count(),
        companies_count=await companies.count(),
        researched_count=await companies.count(status=CompanyStatus.RESEARCHED),
        sources_count=await CompanySourceRepository(session).count_all(),
        pages_count=await CompanyPageRepository(session).count_all(),
        runs_count=runs_total,
        runs_by_status=await runs.count_by_status(),
        recent_runs=[
            RecentRunSummary(
                id=run.id,
                target_id=run.target_id,
                target_name=run.target.name if run.target else f"Target {run.target_id}",
                industry=run.target.industry if run.target else "",
                location=run.target.location if run.target else None,
                status=run.status,
                progress=run.progress,
                companies_found=run.new_companies_count + run.duplicate_companies_count,
                created_at=run.created_at,
                completed_at=run.completed_at,
            )
            for run in recent_runs
        ],
        research_runs_count=research_total,
        research_runs_by_status=await research_runs.count_by_status(),
        evidence_count=await evidence.count_all(),
        fresh_evidence_count=await evidence.count_fresh(cutoff),
        signals_count=await SignalRepository(session).count_all(),
        opportunities_count=await OpportunityRepository(session).count_all(),
        decision_makers_count=await DecisionMakerRepository(session).count_all(),
        capabilities_count=await CapabilityRepository(session).count(),
        recent_companies=[
            RecentCompanySummary.model_validate(company, from_attributes=True)
            for company in recent_companies
        ],
    )
