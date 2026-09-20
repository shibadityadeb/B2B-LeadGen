"""Outreach writer contract.

Why this is separate from ``LLMProvider``: that interface is transport — it
turns a prompt into validated JSON. Composing an email is a domain concern
with its own inputs and its own output shape. Keeping them apart means the
deterministic writer needs no model at all, and a model-backed writer is one
more implementation rather than a special case threaded through the service.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from app.models.enums import ClaimKind
from app.services.outreach_strategy import OutreachStrategy
from app.services.personalization import PersonalizationData


@dataclass
class ComposedClaim:
    """One sentence, plus the evidence ids that justify it.

    ``evidence_ids`` must be non-empty whenever ``requires_evidence`` is true;
    the validator rejects the draft otherwise.
    """

    text: str
    kind: str = ClaimKind.COMPANY_FACT
    evidence_ids: list[int] = field(default_factory=list)

    @property
    def requires_evidence(self) -> bool:
        return self.kind in (ClaimKind.COMPANY_FACT, ClaimKind.SIGNAL_REFERENCE)


@dataclass
class ComposedEmail:
    subject: str
    greeting: str
    body_paragraphs: list[str]
    call_to_action: str
    signature: str
    claims: list[ComposedClaim] = field(default_factory=list)
    generated_by: str = "deterministic"

    @property
    def body(self) -> str:
        parts = [self.greeting, *self.body_paragraphs, self.call_to_action, self.signature]
        return "\n\n".join(part.strip() for part in parts if part and part.strip())


@dataclass
class WriterContext:
    company_name: str
    personalization: PersonalizationData
    strategy: OutreachStrategy
    capability_name: str
    capability_description: str
    sender_name: str
    sender_company: str
    sender_signature: str | None = None
    #: Present only for follow-ups.
    previous_subject: str | None = None
    previous_body: str | None = None
    days_since_sent: int | None = None


class OutreachWriter(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    async def generate_outreach(self, context: WriterContext) -> ComposedEmail: ...

    @abc.abstractmethod
    async def generate_follow_up(self, context: WriterContext) -> ComposedEmail: ...
