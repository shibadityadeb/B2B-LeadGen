"""Append-only audit log for the actions that change outreach state."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent
from app.models.enums import AuditAction


async def record(
    session: AsyncSession,
    *,
    action: AuditAction | str,
    object_type: str,
    object_id: int | None = None,
    actor: str | None = None,
    detail: dict | None = None,
) -> AuditEvent:
    """Write one audit row. Never raises into the caller's happy path."""
    event = AuditEvent(
        action=str(action),
        object_type=object_type,
        object_id=object_id,
        actor=actor or "local",
        detail=detail or {},
        created_at=datetime.now(UTC),
    )
    session.add(event)
    await session.flush()
    return event


async def for_object(
    session: AsyncSession, *, object_type: str, object_id: int, limit: int = 100
) -> list[AuditEvent]:
    rows = await session.scalars(
        select(AuditEvent)
        .where(AuditEvent.object_type == object_type, AuditEvent.object_id == object_id)
        .order_by(AuditEvent.id.desc())
        .limit(limit)
    )
    return list(rows)


async def recent(session: AsyncSession, *, limit: int = 50) -> list[AuditEvent]:
    rows = await session.scalars(
        select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    )
    return list(rows)
