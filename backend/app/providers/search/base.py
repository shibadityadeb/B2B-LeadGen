"""Search provider contract.

Nothing outside this package may import a concrete provider. The pipeline
depends only on :class:`SearchProvider` and :class:`SearchResultItem`, so a
different engine (paid or free) can be added in a later phase by writing one
new module and registering it.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SearchResultItem:
    """A single normalized search hit."""

    title: str | None
    url: str
    snippet: str | None
    source_engine: str | None
    discovered_at: datetime
    position: int | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    available: bool
    detail: str | None = None


class SearchProvider(abc.ABC):
    """Interface every search backend implements."""

    name: str = "base"

    @abc.abstractmethod
    async def search(self, query: str, *, limit: int = 20) -> list[SearchResultItem]:
        """Execute one query and return normalized results.

        Implementations must raise :class:`app.core.errors.ProviderError` on
        transport or upstream failure rather than returning an empty list, so
        the pipeline can record a real error against the query.
        """

    @abc.abstractmethod
    async def status(self) -> ProviderStatus:
        """Cheap reachability check used by the settings page."""

    async def close(self) -> None:  # pragma: no cover - optional hook
        return None
