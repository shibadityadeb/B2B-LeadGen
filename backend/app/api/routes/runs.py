from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.core.errors import NotFoundError
from app.models import DiscoveryRun
from app.repositories.runs import DiscoveryRunRepository
from app.schemas.common import Page
from app.schemas.discovery import (
    DiscoveryRunDetail,
    DiscoveryRunRead,
    SearchQueryRead,
    SearchResultRead,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _to_read(run: DiscoveryRun) -> DiscoveryRunRead:
    payload = DiscoveryRunRead.model_validate(run).model_dump(
        exclude={"target_name", "target_industry", "target_location"}
    )
    target = run.target
    return DiscoveryRunRead(
        **payload,
        target_name=target.name if target else None,
        target_industry=target.industry if target else None,
        target_location=target.location if target else None,
    )


@router.get("", response_model=Page[DiscoveryRunRead])
async def list_runs(
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    target_id: int | None = None,
):
    repo = DiscoveryRunRepository(session)
    runs, total = await repo.list(
        limit=page_size, offset=(page - 1) * page_size, target_id=target_id
    )
    return Page[DiscoveryRunRead](
        items=[_to_read(run) for run in runs], total=total, page=page, page_size=page_size
    )


@router.get("/{run_id}", response_model=DiscoveryRunDetail)
async def get_run(run_id: int, session: SessionDep):
    repo = DiscoveryRunRepository(session)
    run = await repo.get_with_target(run_id)
    if run is None:
        raise NotFoundError(f"Discovery run {run_id} not found")

    queries = await repo.queries_for_run(run_id)
    results = await repo.results_for_run(run_id)

    return DiscoveryRunDetail(
        **_to_read(run).model_dump(),
        queries=[SearchQueryRead.model_validate(query) for query in queries],
        results=[SearchResultRead.model_validate(result) for result in results],
    )
