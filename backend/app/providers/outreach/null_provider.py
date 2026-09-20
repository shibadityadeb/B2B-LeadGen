"""Stand-in used when no mailbox is connected.

Its methods raise with an actionable message rather than returning None, so a
caller can never mistake "not connected" for "draft created".
"""

from __future__ import annotations

from app.core.errors import ProviderError
from app.providers.outreach.base import (
    DraftMessage,
    DraftResult,
    OutreachDeliveryProvider,
    OutreachProviderStatus,
)

_MESSAGE = "No mailbox is connected. Connect Gmail in Settings to create drafts."


class NotConnectedProvider(OutreachDeliveryProvider):
    name = "not_connected"

    @property
    def connected(self) -> bool:
        return False

    async def create_draft(self, message: DraftMessage) -> DraftResult:
        raise ProviderError(_MESSAGE, details={"provider": self.name, "needs_reauth": True})

    async def get_draft(self, draft_id: str) -> DraftResult | None:
        return None

    async def update_draft(self, draft_id: str, message: DraftMessage) -> DraftResult:
        raise ProviderError(_MESSAGE, details={"provider": self.name, "needs_reauth": True})

    async def delete_draft(self, draft_id: str) -> bool:
        return False

    async def status(self) -> OutreachProviderStatus:
        return OutreachProviderStatus(self.name, False, None, _MESSAGE, needs_reauth=True)
