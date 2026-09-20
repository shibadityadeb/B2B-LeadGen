"""Phase 3 models: outreach, approval, Gmail drafts, follow-ups.

Two shaping decisions worth stating:

* A **follow-up is an outreach row** (``parent_outreach_id`` +
  ``follow_up_number``), not a separate table. A follow-up needs a subject,
  a body, versions, validation, its own Gmail draft and its own outcome —
  a second table would duplicate every one of those columns.
* A **claim is a row**, not a JSON blob. Each generated sentence that asserts
  something about the company links to the evidence rows behind it through a
  real foreign key, so a personalized statement can never drift away from the
  evidence that justified it.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import (
    CampaignStatus,
    ClaimKind,
    GenerationMethod,
    GmailConnectionStatus,
    MessageLength,
    OutreachObjective,
    OutreachStatus,
    OutreachTone,
)
from app.models.target import JSONType

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.intelligence import DecisionMaker, Opportunity
    from app.models.research import Evidence
    from app.models.target import Target


class SenderProfile(Base, TimestampMixin):
    """Who the outreach comes from.

    Configured by the user — no real person's details are shipped in code.
    """

    __tablename__ = "sender_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str | None] = mapped_column(String(160))
    company: Mapped[str] = mapped_column(String(160), nullable=False, default="Upshot Brand Media")
    email: Mapped[str | None] = mapped_column(String(320))
    website: Mapped[str | None] = mapped_column(String(255))
    signature: Mapped[str | None] = mapped_column(Text)
    #: Exactly one profile is the default; used when none is chosen explicitly.
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class OutreachCampaign(Base, TimestampMixin):
    """Grouping for organisation and reporting only.

    A campaign never sends anything: it collects outreach records and their
    shared defaults.
    """

    __tablename__ = "outreach_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[int | None] = mapped_column(
        ForeignKey("targets.id", ondelete="SET NULL"), index=True
    )
    sender_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("sender_profiles.id", ondelete="SET NULL")
    )

    tone: Mapped[str] = mapped_column(String(20), nullable=False, default=OutreachTone.PROFESSIONAL)
    message_length: Mapped[str] = mapped_column(
        String(10), nullable=False, default=MessageLength.SHORT
    )
    #: Days after "marked sent" at which each follow-up becomes due.
    follow_up_intervals: Mapped[list[int]] = mapped_column(
        JSONType, nullable=False, default=lambda: [3, 7, 14]
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CampaignStatus.ACTIVE, index=True
    )
    owner: Mapped[str | None] = mapped_column(String(160))

    target: Mapped["Target"] = relationship()
    sender_profile: Mapped["SenderProfile"] = relationship()
    outreach: Mapped[list["Outreach"]] = relationship(back_populates="campaign")


class Outreach(Base, TimestampMixin):
    """One prepared message to one person about one opportunity."""

    __tablename__ = "outreach"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"), index=True
    )
    decision_maker_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_makers.id", ondelete="SET NULL"), index=True
    )
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("outreach_campaigns.id", ondelete="SET NULL"), index=True
    )
    sender_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("sender_profiles.id", ondelete="SET NULL")
    )
    #: Set when this message is a follow-up to an earlier one.
    parent_outreach_id: Mapped[int | None] = mapped_column(
        ForeignKey("outreach.id", ondelete="SET NULL"), index=True
    )
    follow_up_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=OutreachStatus.DRAFT, index=True
    )
    objective: Mapped[str] = mapped_column(
        String(30), nullable=False, default=OutreachObjective.START_CONVERSATION
    )
    tone: Mapped[str] = mapped_column(String(20), nullable=False, default=OutreachTone.PROFESSIONAL)
    message_length: Mapped[str] = mapped_column(
        String(10), nullable=False, default=MessageLength.SHORT
    )

    # --- addressing ---
    to_email: Mapped[str | None] = mapped_column(String(320))
    to_name: Mapped[str | None] = mapped_column(String(200))
    cc: Mapped[str | None] = mapped_column(String(600))
    bcc: Mapped[str | None] = mapped_column(String(600))

    # --- content ---
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    #: Kept so "reset to the generated draft" is always possible.
    ai_generated_subject: Mapped[str | None] = mapped_column(Text)
    ai_generated_body: Mapped[str | None] = mapped_column(Text)
    user_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- reasoning, stored as structured output rather than model narration ---
    strategy: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    personalization: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    validation: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    generated_by: Mapped[str] = mapped_column(
        String(30), nullable=False, default=GenerationMethod.DETERMINISTIC
    )

    # --- delivery state ---
    gmail_draft_id: Mapped[str | None] = mapped_column(String(120), index=True)
    gmail_draft_url: Mapped[str | None] = mapped_column(Text)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(120))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gmail_draft_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- outcome (current value; history lives in outreach_outcomes) ---
    outcome_status: Mapped[str | None] = mapped_column(String(30), index=True)
    outcome_reason: Mapped[str | None] = mapped_column(String(40))
    outcome_notes: Mapped[str | None] = mapped_column(Text)
    outcome_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    active_version_id: Mapped[int | None] = mapped_column(Integer)
    owner: Mapped[str | None] = mapped_column(String(160), index=True)

    company: Mapped["Company"] = relationship()
    opportunity: Mapped["Opportunity"] = relationship()
    decision_maker: Mapped["DecisionMaker"] = relationship()
    campaign: Mapped["OutreachCampaign"] = relationship(back_populates="outreach")
    sender_profile: Mapped["SenderProfile"] = relationship()
    versions: Mapped[list["OutreachVersion"]] = relationship(
        back_populates="outreach",
        cascade="all, delete-orphan",
        order_by="OutreachVersion.version_number",
    )
    outcomes: Mapped[list["OutreachOutcome"]] = relationship(
        back_populates="outreach", cascade="all, delete-orphan", order_by="OutreachOutcome.id"
    )

    __table_args__ = (
        Index("ix_outreach_company_status", "company_id", "status"),
        Index("ix_outreach_followup_due", "status", "next_follow_up_at"),
    )


class OutreachVersion(Base):
    """A snapshot of the message. Regeneration adds one; nothing is destroyed."""

    __tablename__ = "outreach_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    outreach_id: Mapped[int] = mapped_column(
        ForeignKey("outreach.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    generation_method: Mapped[str] = mapped_column(
        String(30), nullable=False, default=GenerationMethod.DETERMINISTIC
    )
    strategy: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    personalization: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    validation: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    outreach: Mapped["Outreach"] = relationship(back_populates="versions")
    claims: Mapped[list["OutreachClaim"]] = relationship(
        back_populates="version", cascade="all, delete-orphan", order_by="OutreachClaim.id"
    )

    __table_args__ = (
        UniqueConstraint("outreach_id", "version_number", name="uq_outreach_version_number"),
    )


class OutreachClaim(Base):
    """One generated sentence, with the evidence that justifies it.

    This is the mechanism that keeps personalization honest: a sentence
    asserting something about the company is only allowed to exist here
    alongside the evidence rows it came from.
    """

    __tablename__ = "outreach_claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    outreach_version_id: Mapped[int] = mapped_column(
        ForeignKey("outreach_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default=ClaimKind.COMPANY_FACT)
    #: True when this kind of claim is required to cite evidence.
    requires_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    version: Mapped["OutreachVersion"] = relationship(back_populates="claims")
    evidence_links: Mapped[list["OutreachClaimEvidence"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class OutreachClaimEvidence(Base):
    __tablename__ = "outreach_claim_evidence"

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("outreach_claims.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )

    claim: Mapped["OutreachClaim"] = relationship(back_populates="evidence_links")
    evidence: Mapped["Evidence"] = relationship()


class OutreachOutcome(Base):
    """Outcome history. Each update appends; the current value also lives on
    the outreach row for querying."""

    __tablename__ = "outreach_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    outreach_id: Mapped[int] = mapped_column(
        ForeignKey("outreach.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    outreach: Mapped["Outreach"] = relationship(back_populates="outcomes")


class GmailConnection(Base, TimestampMixin):
    """Stored Google OAuth credentials.

    Tokens live server-side only and are never serialized into any API
    response — see ``app.schemas.outreach.GmailConnectionRead``.
    """

    __tablename__ = "gmail_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    access_token: Mapped[str | None] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GmailConnectionStatus.CONNECTED, index=True
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class AuditEvent(Base):
    """Append-only record of the actions that change outreach state."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    object_id: Mapped[int | None] = mapped_column(Integer, index=True)
    actor: Mapped[str | None] = mapped_column(String(160))
    detail: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (Index("ix_audit_object", "object_type", "object_id"),)
