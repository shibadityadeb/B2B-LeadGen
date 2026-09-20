"""Outreach delivery provider contract.

Deliberately draft-only in Phase 3. There is **no `send` method** on this
interface: the capability to send autonomously does not exist in the code, so
it cannot be triggered by accident, by a bug or by a future caller who assumes
it is there. Sending is something a human does in their mail client.

A later provider (a sequencing tool, a different mailbox) implements the same
interface; the outreach service never names a concrete provider.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DraftMessage:
    to: str
    subject: str
    body: str
    cc: str | None = None
    bcc: str | None = None
    from_name: str | None = None
    thread_id: str | None = None


@dataclass(frozen=True)
class DraftResult:
    draft_id: str
    #: Deep link the user can open in their mail client.
    url: str | None = None
    thread_id: str | None = None
    message_id: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class OutreachProviderStatus:
    name: str
    connected: bool
    account_email: str | None = None
    detail: str | None = None
    #: True when reconnecting would fix it (expired or revoked credentials).
    needs_reauth: bool = False


class OutreachDeliveryProvider(abc.ABC):
    name: str = "base"

    @property
    @abc.abstractmethod
    def connected(self) -> bool: ...

    @abc.abstractmethod
    async def create_draft(self, message: DraftMessage) -> DraftResult:
        """Create a draft in the user's mailbox. Never sends."""

    @abc.abstractmethod
    async def get_draft(self, draft_id: str) -> DraftResult | None: ...

    @abc.abstractmethod
    async def update_draft(self, draft_id: str, message: DraftMessage) -> DraftResult: ...

    @abc.abstractmethod
    async def delete_draft(self, draft_id: str) -> bool: ...

    @abc.abstractmethod
    async def status(self) -> OutreachProviderStatus: ...
