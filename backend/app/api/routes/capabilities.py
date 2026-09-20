"""UBM capability catalogue.

Capabilities are configuration: they can be created, edited and deactivated
at runtime, and the matching engine picks the change up on the next research
run with no deploy.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, status

from app.api.deps import SessionDep
from app.core.errors import ConflictError, NotFoundError
from app.repositories.research import CapabilityRepository
from app.schemas.research import CapabilityCreate, CapabilityRead, CapabilityUpdate
from app.services.capability_seed import SEED_CAPABILITIES
from app.services.evidence_taxonomy import SIGNAL_GROUPS

router = APIRouter(prefix="/api/ubm", tags=["capabilities"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "capability"


@router.get("/capabilities", response_model=list[CapabilityRead])
async def list_capabilities(session: SessionDep, active_only: bool = False):
    repo = CapabilityRepository(session)
    # Seed on first read so the settings page is never empty before a run.
    if await repo.count() == 0:
        for entry in SEED_CAPABILITIES:
            await repo.create(**entry, is_seed=True, active=True)
        await session.commit()
    return await repo.list(active_only=active_only)


@router.get("/signal-types", response_model=list[dict])
async def list_signal_types():
    """The vocabulary a capability can be keyed to."""
    return [
        {"value": signal_type, "label": title}
        for signal_type, (title, _) in sorted(SIGNAL_GROUPS.items())
    ]


@router.post("/capabilities", response_model=CapabilityRead, status_code=status.HTTP_201_CREATED)
async def create_capability(payload: CapabilityCreate, session: SessionDep):
    repo = CapabilityRepository(session)
    slug = payload.slug or _slugify(payload.name)
    if await repo.get_by_slug(slug):
        raise ConflictError(f"A capability with slug '{slug}' already exists.")

    data = payload.model_dump(exclude={"slug"})
    capability = await repo.create(**data, slug=slug, is_seed=False)
    await session.commit()
    return capability


@router.patch("/capabilities/{capability_id}", response_model=CapabilityRead)
async def update_capability(
    capability_id: int, payload: CapabilityUpdate, session: SessionDep
):
    repo = CapabilityRepository(session)
    capability = await repo.get(capability_id)
    if capability is None:
        raise NotFoundError(f"Capability {capability_id} not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(capability, key, value)
    await session.commit()
    await session.refresh(capability)
    return capability
