"""Gmail draft provider.

Uses only ``gmail.compose``, the narrowest scope that can create a draft. It
does **not** request `gmail.send`, `gmail.modify` or any read scope: the
application cannot send mail or read the user's inbox even if asked to.

Tokens are held server-side and refreshed here; they never reach the client.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import httpx

from app.core.config import settings
from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.providers.outreach.base import (
    DraftMessage,
    DraftResult,
    OutreachDeliveryProvider,
    OutreachProviderStatus,
)

logger = get_logger(__name__)

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

#: The only scope requested. Creating drafts, nothing else.
SCOPES = ("https://www.googleapis.com/auth/gmail.compose",)


def authorization_url(*, state: str, redirect_uri: str) -> str:
    """Build the Google consent URL. No secret is involved at this step."""
    from urllib.parse import urlencode

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        # A refresh token is only issued with these two together.
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(*, code: str, redirect_uri: str) -> dict:
    """Trade an authorization code for tokens. Server-side only."""
    payload = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(TOKEN_URL, data=payload)
    if response.status_code >= 400:
        raise ProviderError(
            f"Google rejected the authorization code: {response.text[:200]}",
            details={"provider": "gmail"},
        )
    return response.json()


async def fetch_account_email(access_token: str) -> str | None:
    """The mailbox the token belongs to, used for display only."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{GMAIL_API}/users/me/profile",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if response.status_code == 200:
            return response.json().get("emailAddress")
    except httpx.HTTPError:
        return None
    return None


class GmailProvider(OutreachDeliveryProvider):
    name = "gmail"

    def __init__(
        self,
        *,
        access_token: str | None,
        refresh_token: str | None = None,
        token_expiry: datetime | None = None,
        account_email: str | None = None,
        on_token_refresh=None,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expiry = token_expiry
        self.account_email = account_email
        #: Called with the new token payload so the caller can persist it.
        self._on_token_refresh = on_token_refresh

    @property
    def connected(self) -> bool:
        return bool(self.access_token or self.refresh_token)

    # -- auth ------------------------------------------------------------- #

    def _expired(self) -> bool:
        if not self.token_expiry:
            return False
        expiry = (
            self.token_expiry
            if self.token_expiry.tzinfo
            else self.token_expiry.replace(tzinfo=UTC)
        )
        # Refresh a minute early rather than racing the expiry.
        return datetime.now(UTC) >= expiry - timedelta(seconds=60)

    async def authenticate(self) -> str:
        """Return a usable access token, refreshing it if necessary."""
        if self.access_token and not self._expired():
            return self.access_token
        if not self.refresh_token:
            raise ProviderError(
                "Gmail is not connected, or the stored credentials have expired. "
                "Reconnect Gmail in Settings.",
                details={"provider": self.name, "needs_reauth": True},
            )

        payload = {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(TOKEN_URL, data=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Could not reach Google to refresh the Gmail token: {exc}",
                details={"provider": self.name},
            ) from exc

        if response.status_code >= 400:
            # A revoked grant cannot be recovered without the user.
            raise ProviderError(
                "The Gmail authorization is no longer valid. Reconnect Gmail in Settings.",
                details={"provider": self.name, "needs_reauth": True},
            )

        data = response.json()
        self.access_token = data.get("access_token")
        expires_in = int(data.get("expires_in", 3600))
        self.token_expiry = datetime.now(UTC) + timedelta(seconds=expires_in)
        if self._on_token_refresh:
            await self._on_token_refresh(self.access_token, self.token_expiry)
        return self.access_token

    # -- drafts ----------------------------------------------------------- #

    def _encode(self, message: DraftMessage) -> str:
        mail = EmailMessage()
        mail["To"] = message.to
        if message.cc:
            mail["Cc"] = message.cc
        if message.bcc:
            mail["Bcc"] = message.bcc
        mail["Subject"] = message.subject
        if self.account_email:
            mail["From"] = (
                f"{message.from_name} <{self.account_email}>"
                if message.from_name
                else self.account_email
            )
        mail.set_content(message.body)
        return base64.urlsafe_b64encode(mail.as_bytes()).decode()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        token = await self.authenticate()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method,
                    f"{GMAIL_API}{path}",
                    headers={"Authorization": f"Bearer {token}"},
                    **kwargs,
                )
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Could not reach the Gmail API: {exc}", details={"provider": self.name}
            ) from exc

        if response.status_code in (401, 403):
            raise ProviderError(
                "Gmail rejected the request. The connection may have been revoked — "
                "reconnect Gmail in Settings.",
                details={"provider": self.name, "needs_reauth": True},
            )
        if response.status_code == 429:
            raise ProviderError(
                "Gmail is rate limiting this account. Try again shortly.",
                details={"provider": self.name},
            )
        return response

    async def create_draft(self, message: DraftMessage) -> DraftResult:
        body: dict = {"message": {"raw": self._encode(message)}}
        if message.thread_id:
            body["message"]["threadId"] = message.thread_id

        response = await self._request("POST", "/users/me/drafts", json=body)
        if response.status_code >= 400:
            raise ProviderError(
                f"Gmail could not create the draft: {response.text[:200]}",
                details={"provider": self.name},
            )
        data = response.json()
        draft_id = data.get("id")
        thread_id = (data.get("message") or {}).get("threadId")
        return DraftResult(
            draft_id=draft_id,
            url=f"https://mail.google.com/mail/u/0/#drafts?compose={draft_id}",
            thread_id=thread_id,
            message_id=(data.get("message") or {}).get("id"),
            raw=data,
        )

    async def get_draft(self, draft_id: str) -> DraftResult | None:
        response = await self._request("GET", f"/users/me/drafts/{draft_id}")
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise ProviderError(
                f"Gmail could not return the draft: {response.text[:200]}",
                details={"provider": self.name},
            )
        data = response.json()
        return DraftResult(
            draft_id=data.get("id"),
            url=f"https://mail.google.com/mail/u/0/#drafts?compose={data.get('id')}",
            thread_id=(data.get("message") or {}).get("threadId"),
            raw=data,
        )

    async def update_draft(self, draft_id: str, message: DraftMessage) -> DraftResult:
        response = await self._request(
            "PUT",
            f"/users/me/drafts/{draft_id}",
            json={"message": {"raw": self._encode(message)}},
        )
        if response.status_code >= 400:
            raise ProviderError(
                f"Gmail could not update the draft: {response.text[:200]}",
                details={"provider": self.name},
            )
        data = response.json()
        return DraftResult(
            draft_id=data.get("id"),
            url=f"https://mail.google.com/mail/u/0/#drafts?compose={data.get('id')}",
            thread_id=(data.get("message") or {}).get("threadId"),
            raw=data,
        )

    async def delete_draft(self, draft_id: str) -> bool:
        response = await self._request("DELETE", f"/users/me/drafts/{draft_id}")
        return response.status_code in (200, 204, 404)

    async def status(self) -> OutreachProviderStatus:
        if not self.connected:
            return OutreachProviderStatus(
                self.name, False, None, "Gmail is not connected.", needs_reauth=True
            )
        try:
            await self.authenticate()
        except ProviderError as exc:
            return OutreachProviderStatus(
                self.name,
                False,
                self.account_email,
                str(exc),
                needs_reauth=bool(exc.details.get("needs_reauth")),
            )
        return OutreachProviderStatus(
            self.name,
            True,
            self.account_email,
            f"Connected as {self.account_email}. Draft-only access (gmail.compose).",
        )
