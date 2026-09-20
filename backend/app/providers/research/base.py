"""Research source provider contract.

A research source provider answers: "what else is publicly published about
this company?" — news, press, event listings. Phase 2 implements this on top
of the existing free search provider; a paid research API later implements the
same interface without the intelligence engine changing.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ResearchCandidate:
    """A public document worth retrieving."""

    url: str
    title: str | None
    snippet: str | None
    source_type: str
    published_at: datetime | None = None
    source_engine: str | None = None
    query: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchProviderStatus:
    name: str
    available: bool
    detail: str | None = None


class ResearchSourceProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    async def find_sources(
        self,
        *,
        company_name: str,
        domain: str,
        location: str | None = None,
        industry: str | None = None,
        limit: int = 25,
    ) -> list[ResearchCandidate]:
        """Public documents about the company, best-effort and deduplicated."""

    @abc.abstractmethod
    async def status(self) -> ResearchProviderStatus: ...
