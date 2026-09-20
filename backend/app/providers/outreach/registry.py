"""Resolves the delivery provider from stored credentials.

Callers ask for "the provider"; whether that is Gmail or a not-connected stub
is decided here, so no business logic branches on Gmail specifically.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GmailConnection
from app.models.enums import GmailConnectionStatus
from app.providers.outreach.base import OutreachDeliveryProvider
from app.providers.outreach.gmail import GmailProvider
from app.providers.outreach.null_provider import NotConnectedProvider


async def active_connection(session: AsyncSession) -> GmailConnection | None:
    return await session.scalar(
        select(GmailConnection)
        .where(GmailConnection.is_active.is_(True))
        .order_by(GmailConnection.id.desc())
        .limit(1)
    )


async def get_delivery_provider(session: AsyncSession) -> OutreachDeliveryProvider:
    connection = await active_connection(session)
    if connection is None or connection.status in (
        GmailConnectionStatus.REVOKED,
        GmailConnectionStatus.DISCONNECTED,
    ):
        return NotConnectedProvider()

    async def persist(access_token: str, expiry: datetime) -> None:
        connection.access_token = access_token
        connection.token_expiry = expiry
        connection.status = GmailConnectionStatus.CONNECTED
        connection.last_error = None
        await session.commit()

    return GmailProvider(
        access_token=connection.access_token,
        refresh_token=connection.refresh_token,
        token_expiry=connection.token_expiry,
        account_email=connection.account_email,
        on_token_refresh=persist,
    )
