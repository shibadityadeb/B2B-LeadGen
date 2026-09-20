from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import QueueDep, SessionDep
from app.core.config import settings
from app.core.errors import NotFoundError
from app.repositories.targets import TargetRepository
from app.schemas.discovery import DiscoveryRunRead
from app.schemas.target import TargetCreate, TargetListItem, TargetPreview, TargetRead
from app.services.discovery import DiscoveryService
from app.services.query_generation import generate_queries
from app.workers.jobs import DISCOVERY_JOB

router = APIRouter(prefix="/api/targets", tags=["targets"])


@router.get("", response_model=list[TargetListItem])
async def list_targets(session: SessionDep):
    repo = TargetRepository(session)
    targets = await repo.list()
    stats = await repo.stats([target.id for target in targets])

    items = []
    for target in targets:
        stat = stats.get(target.id, {})
        run = stat.get("last_run")
        items.append(
            TargetListItem(
                **TargetRead.model_validate(target).model_dump(),
                companies_count=stat.get("companies_count", 0),
                last_run_at=run.created_at if run else None,
                last_run_status=run.status if run else None,
                last_run_id=run.id if run else None,
            )
        )
    return items


@router.post("", response_model=TargetRead, status_code=status.HTTP_201_CREATED)
async def create_target(payload: TargetCreate, session: SessionDep):
    target = await TargetRepository(session).create(**payload.model_dump())
    await session.commit()
    return target


@router.post("/preview", response_model=TargetPreview)
async def preview_queries(payload: TargetCreate):
    """Show the queries a target would generate, without saving anything."""
    queries = generate_queries(
        industry=payload.industry,
        location=payload.location,
        country=payload.country,
        keywords=payload.keywords,
        search_context=payload.search_context,
        max_queries=settings.search_max_queries_per_run,
    )
    return TargetPreview(queries=[item.query for item in queries])


@router.get("/{target_id}", response_model=TargetRead)
async def get_target(target_id: int, session: SessionDep):
    target = await TargetRepository(session).get(target_id)
    if target is None:
        raise NotFoundError(f"Target {target_id} not found")
    return target


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(target_id: int, session: SessionDep):
    repo = TargetRepository(session)
    target = await repo.get(target_id)
    if target is None:
        raise NotFoundError(f"Target {target_id} not found")
    await repo.delete(target)
    await session.commit()


@router.post(
    "/{target_id}/discover",
    response_model=DiscoveryRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_discovery(target_id: int, session: SessionDep, queue: QueueDep):
    target = await TargetRepository(session).get(target_id)
    if target is None:
        raise NotFoundError(f"Target {target_id} not found")

    service = DiscoveryService(session)
    run = await service.create_run(target)
    await queue.enqueue(DISCOVERY_JOB, run_id=run.id)

    return DiscoveryRunRead(
        **DiscoveryRunRead.model_validate(run).model_dump(
            exclude={"target_name", "target_industry", "target_location"}
        ),
        target_name=target.name,
        target_industry=target.industry,
        target_location=target.location,
    )
