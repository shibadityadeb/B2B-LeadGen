"""Decision-maker provider contract.

Hard rules this interface exists to enforce:

* A name is reported only when it was read from a public page. There is no
  path by which a name can be produced any other way.
* An email is reported only when the address itself appears in the text. An
  address is never derived from a name pattern.
* When only a role is evidenced, ``name`` is None — the role is still useful,
  and inventing a person to fill it would not be.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveredPerson:
    role: str
    role_category: str | None = None
    #: None when only the role is evidenced.
    name: str | None = None
    #: Only ever an address observed verbatim in the source text.
    email: str | None = None
    phone: str | None = None
    profile_url: str | None = None
    #: Verbatim text the person was read from, for verification.
    excerpt: str | None = None
    source_url: str | None = None
    verification_status: str = "unverified"


@dataclass(frozen=True)
class PeopleProviderStatus:
    name: str
    available: bool
    detail: str | None = None


class DecisionMakerProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    async def find_people(
        self, *, company_name: str, documents: list[tuple[str, str, str]]
    ) -> list[DiscoveredPerson]:
        """Extract people from ``(url, title, text)`` tuples already retrieved.

        Providers must not fetch anything themselves — the orchestrator owns
        retrieval, robots compliance and rate limiting.
        """

    @abc.abstractmethod
    async def status(self) -> PeopleProviderStatus: ...
