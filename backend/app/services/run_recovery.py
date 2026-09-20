"""Recovers runs that were interrupted by a restart.

Background work happens inside the API process, so a deploy, a crash or a
platform putting the instance to sleep kills any run in flight. Without this,
that run stays "researching" forever and the UI spins indefinitely.

Marking them failed on startup is honest: we genuinely do not know how far
they got, and the user can simply run it again.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Company, DiscoveryRun, ResearchRun
from app.models.enums import CompanyStatus, ResearchStatus, RunStatus

logger = get_logger(__name__)

INTERRUPTED_MESSAGE = (
    "This run was interrupted when the server restarted. Nothing was lost — "
    "run it again to pick up from where the data stands."
)


async def recover_interrupted_runs(session: AsyncSession) -> dict[str, int]:
    """Fail runs left mid-flight by a restart. Returns what was recovered."""
    now = datetime.now(UTC)
    recovered = {"discovery_runs": 0, "research_runs": 0, "companies": 0}

    discovery = await session.scalars(
        select(DiscoveryRun).where(
            DiscoveryRun.status.in_([RunStatus.QUEUED, RunStatus.RUNNING])
        )
    )
    for run in discovery:
        run.status = RunStatus.FAILED
        run.error_message = INTERRUPTED_MESSAGE
        run.completed_at = now
        recovered["discovery_runs"] += 1

    research = await session.scalars(
        select(ResearchRun).where(
            ResearchRun.status.in_(
                [ResearchStatus.QUEUED, ResearchStatus.RESEARCHING, ResearchStatus.ANALYZING]
            )
        )
    )
    interrupted_company_ids: set[int] = set()
    for run in research:
        run.status = ResearchStatus.FAILED
        run.error_message = INTERRUPTED_MESSAGE
        run.completed_at = now
        interrupted_company_ids.add(run.company_id)
        recovered["research_runs"] += 1

    # A company left showing "researching" would never settle on its own.
    companies = await session.scalars(
        select(Company).where(Company.status == CompanyStatus.RESEARCHING)
    )
    for company in companies:
        # Keep an earlier successful result rather than overwriting it.
        company.status = (
            CompanyStatus.RESEARCHED
            if company.last_researched_at
            else CompanyStatus.DISCOVERED
        )
        recovered["companies"] += 1

    if any(recovered.values()):
        await session.commit()
        logger.warning(
            "recovered interrupted work on startup: %s discovery run(s), "
            "%s research run(s), %s company status(es)",
            recovered["discovery_runs"],
            recovered["research_runs"],
            recovered["companies"],
        )
    return recovered
