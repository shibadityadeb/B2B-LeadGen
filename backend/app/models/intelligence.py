"""Phase 2 models: signals, capabilities, opportunities and people.

Every derived object links back to the evidence it rests on through an
association table, so a reader can always walk from a conclusion to the
source text behind it.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
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
    ConfidenceLevel,
    EpistemicStatus,
    Freshness,
    ObservationState,
    OpportunityStatus,
    VerificationStatus,
)
from app.models.target import JSONType

if TYPE_CHECKING:
    from app.models.research import Evidence, ResearchSource


class Signal(Base, TimestampMixin):
    """A structured interpretation of one or more evidence items."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    research_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_runs.id", ondelete="SET NULL"), index=True
    )

    signal_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Derived from the evidence, never asserted by a model on its own.
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    freshness: Mapped[str] = mapped_column(
        String(20), nullable=False, default=Freshness.UNKNOWN, index=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_level: Mapped[str] = mapped_column(
        String(10), nullable=False, default=ConfidenceLevel.LOW
    )
    confidence_components: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    epistemic_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EpistemicStatus.INFERRED
    )

    latest_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observation_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ObservationState.NEW
    )
    generated_by: Mapped[str] = mapped_column(String(40), nullable=False, default="rules")

    evidence_links: Mapped[list["SignalEvidence"]] = relationship(
        back_populates="signal", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("company_id", "fingerprint", name="uq_signals_company_fingerprint"),
        Index("ix_signals_company_type", "company_id", "signal_type"),
    )


class SignalEvidence(Base):
    """Signal -> evidence. A real foreign key, not an id array."""

    __tablename__ = "signal_evidence"

    signal_id: Mapped[int] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )

    signal: Mapped["Signal"] = relationship(back_populates="evidence_links")
    evidence: Mapped["Evidence"] = relationship()


class UbmCapability(Base, TimestampMixin):
    """A UBM service area, stored as data so it is editable without a deploy.

    ``signal_types`` is the matching rule: a capability becomes relevant when
    a company exhibits one of these signal types. There is no industry
    branching anywhere — adding a vertical requires no code change.
    """

    __tablename__ = "ubm_capabilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), index=True)

    signal_types: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    # Optional extra lift when these words appear in the evidence text.
    keywords: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    # Template with {company}/{signals} placeholders, used to phrase the
    # rationale deterministically when no LLM is configured.
    rationale_template: Mapped[str | None] = mapped_column(Text)

    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="capability")


class Opportunity(Base, TimestampMixin):
    """A *hypothesis* that a UBM capability may be relevant to a company.

    Never stated as fact: the wording, the status vocabulary and the
    confidence level all keep it provisional.
    """

    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability_id: Mapped[int] = mapped_column(
        ForeignKey("ubm_capabilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    research_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_runs.id", ondelete="SET NULL"), index=True
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    why_relevant: Mapped[str] = mapped_column(Text, nullable=False)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_level: Mapped[str] = mapped_column(
        String(10), nullable=False, default=ConfidenceLevel.LOW
    )
    confidence_components: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    freshness: Mapped[str] = mapped_column(
        String(20), nullable=False, default=Freshness.UNKNOWN, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OpportunityStatus.CANDIDATE, index=True
    )

    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observation_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ObservationState.NEW
    )
    generated_by: Mapped[str] = mapped_column(String(40), nullable=False, default="rules")

    capability: Mapped["UbmCapability"] = relationship(back_populates="opportunities")
    evidence_links: Mapped[list["OpportunityEvidence"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )
    signal_links: Mapped[list["OpportunitySignal"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "fingerprint", name="uq_opportunities_company_fingerprint"
        ),
    )


class OpportunityEvidence(Base):
    __tablename__ = "opportunity_evidence"

    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )

    opportunity: Mapped["Opportunity"] = relationship(back_populates="evidence_links")
    evidence: Mapped["Evidence"] = relationship()


class OpportunitySignal(Base):
    __tablename__ = "opportunity_signals"

    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True
    )
    signal_id: Mapped[int] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True
    )

    opportunity: Mapped["Opportunity"] = relationship(back_populates="signal_links")
    signal: Mapped["Signal"] = relationship()


class DecisionMaker(Base, TimestampMixin):
    """A publicly documented person or role at a company.

    A name is stored only when it was actually observed on a public page.
    When only the role is evidenced, ``name`` stays NULL — the system does
    not invent people, and never derives an email from a name pattern.
    """

    __tablename__ = "decision_makers"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    research_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_runs.id", ondelete="SET NULL"), index=True
    )
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_sources.id", ondelete="SET NULL"), index=True
    )

    name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    # Normalized bucket (e.g. "marketing", "founder") for grouping.
    role_category: Mapped[str | None] = mapped_column(String(50), index=True)

    # Only ever populated from text actually present on a public page.
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    profile_url: Mapped[str | None] = mapped_column(Text)

    verification_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=VerificationStatus.UNVERIFIED
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_level: Mapped[str] = mapped_column(
        String(10), nullable=False, default=ConfidenceLevel.LOW
    )
    excerpt: Mapped[str | None] = mapped_column(Text)

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observation_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ObservationState.NEW
    )

    source: Mapped["ResearchSource"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "company_id", "fingerprint", name="uq_decision_makers_company_fingerprint"
        ),
    )
