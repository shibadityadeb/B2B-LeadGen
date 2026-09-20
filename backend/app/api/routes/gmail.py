"""Google OAuth and Gmail connection state.

The whole flow runs server-side: the client ID, the client secret and the
resulting tokens never reach the browser. The frontend only ever sees whether
a mailbox is connected and which address it is.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.errors import AppError, ProviderError
from app.core.logging import get_logger
from app.models import GmailConnection
from app.models.enums import AuditAction, GmailConnectionStatus
from app.providers.outreach.gmail import (
    SCOPES,
    authorization_url,
    exchange_code,
    fetch_account_email,
)
from app.providers.outreach.registry import get_delivery_provider
from app.repositories.outreach import GmailConnectionRepository
from app.schemas.outreach import GmailAuthUrl, GmailConnectionRead
from app.services import audit

logger = get_logger(__name__)

router = APIRouter(prefix="/api/gmail", tags=["gmail"])

# Short-lived CSRF state values for in-flight authorization attempts.
# Single-process by design, matching the in-process job queue.
_PENDING_STATES: dict[str, datetime] = {}
_STATE_TTL = timedelta(minutes=10)


def _new_state() -> str:
    now = datetime.now(UTC)
    for key, created in list(_PENDING_STATES.items()):
        if now - created > _STATE_TTL:
            _PENDING_STATES.pop(key, None)
    state = secrets.token_urlsafe(24)
    _PENDING_STATES[state] = now
    return state


def _consume_state(state: str) -> bool:
    created = _PENDING_STATES.pop(state, None)
    return created is not None and datetime.now(UTC) - created <= _STATE_TTL


@router.get("/status", response_model=GmailConnectionRead)
async def gmail_status(session: SessionDep):
    connection = await GmailConnectionRepository(session).active()
    if not settings.gmail_configured:
        return GmailConnectionRead(
            connected=False,
            configured=False,
            detail=(
                "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET in the backend .env, then restart the API."
            ),
            needs_reauth=False,
        )
    if connection is None:
        return GmailConnectionRead(
            connected=False, configured=True, detail="No mailbox is connected yet."
        )

    provider = await get_delivery_provider(session)
    provider_status = await provider.status()
    return GmailConnectionRead(
        connected=provider_status.connected,
        configured=True,
        account_email=connection.account_email,
        status=connection.status,
        scopes=connection.scopes or list(SCOPES),
        connected_at=connection.connected_at,
        needs_reauth=provider_status.needs_reauth,
        detail=provider_status.detail,
    )


@router.get("/authorize", response_model=GmailAuthUrl)
async def gmail_authorize():
    """Return the Google consent URL for the frontend to open."""
    if not settings.gmail_configured:
        raise AppError(
            "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET in the backend .env and restart the API."
        )
    return GmailAuthUrl(
        authorization_url=authorization_url(
            state=_new_state(), redirect_uri=settings.google_redirect_uri
        )
    )


@router.get("/callback")
async def gmail_callback(
    session: SessionDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Google redirects here. Exchanges the code and returns the user to the app."""
    settings_url = f"{settings.frontend_url.rstrip('/')}/settings"

    if error:
        return RedirectResponse(f"{settings_url}?gmail=error&reason={error}")
    if not code or not state or not _consume_state(state):
        # A missing or stale state means this is not a flow we started.
        return RedirectResponse(f"{settings_url}?gmail=error&reason=invalid_state")

    try:
        tokens = await exchange_code(code=code, redirect_uri=settings.google_redirect_uri)
    except ProviderError as exc:
        logger.warning("gmail token exchange failed: %s", exc)
        return RedirectResponse(f"{settings_url}?gmail=error&reason=token_exchange_failed")

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_in = int(tokens.get("expires_in", 3600))
    account_email = await fetch_account_email(access_token) if access_token else None

    repo = GmailConnectionRepository(session)
    existing = await repo.by_email(account_email) if account_email else None
    await repo.deactivate_all()

    if existing is None:
        existing = GmailConnection(account_email=account_email or "unknown")
        session.add(existing)

    existing.access_token = access_token
    # Google only returns a refresh token on first consent; keep the old one
    # if this re-consent did not include one.
    if refresh_token:
        existing.refresh_token = refresh_token
    existing.token_expiry = datetime.now(UTC) + timedelta(seconds=expires_in)
    existing.scopes = (tokens.get("scope") or " ".join(SCOPES)).split()
    existing.status = GmailConnectionStatus.CONNECTED
    existing.connected_at = datetime.now(UTC)
    existing.is_active = True
    existing.last_error = None

    await audit.record(
        session,
        action=AuditAction.GMAIL_CONNECTED,
        object_type="gmail_connection",
        object_id=existing.id,
        detail={"account_email": account_email},
    )
    await session.commit()
    return RedirectResponse(f"{settings_url}?gmail=connected")


@router.post("/disconnect", response_model=GmailConnectionRead)
async def gmail_disconnect(session: SessionDep):
    """Forget the stored credentials. Any Gmail drafts already created stay
    in the user's mailbox."""
    repo = GmailConnectionRepository(session)
    connection = await repo.active()
    if connection is not None:
        connection.is_active = False
        connection.status = GmailConnectionStatus.DISCONNECTED
        connection.access_token = None
        connection.refresh_token = None
        await audit.record(
            session,
            action=AuditAction.GMAIL_DISCONNECTED,
            object_type="gmail_connection",
            object_id=connection.id,
        )
        await session.commit()

    return GmailConnectionRead(
        connected=False,
        configured=settings.gmail_configured,
        detail="Gmail has been disconnected. Drafts already created remain in your mailbox.",
    )
