"""Phase 2 models: research runs, sources and evidence.

Relationship to Phase 1
-----------------------
Phase 1's ``company_sources`` records *discovery* provenance — the search hit
that first surfaced a company. Phase 2 needs something richer: retrieved
content, a content hash, a reliability judgement and run scoping. That is
``research_sources``. The orchestrator ingests Phase 1 ``company_pages`` into
it, so the two never duplicate each other.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
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
    ContradictionStatus,
    EpistemicStatus,
    ObservationState,
    ResearchStage,
    ResearchStatus,
    ResearchSourceType,
    RetrievalStatus,
    SourceReliability,
)
from app.models.target import JSONType

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.intelligence import DecisionMaker, Opportunity, Signal


class ResearchRun(Base, TimestampMixin):
    """One execution of the research orchestrator for one company."""

    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ResearchStatus.QUEUED, index=True
    )
    stage: Mapped[str] = mapped_column(String(40), nullable=False, default=ResearchStage.PENDING)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Real counters, written as each stage completes.
    sources_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_retrieved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opportunities_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decision_makers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contradictions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Which providers actually ran, for reproducibility.
    search_provider: Mapped[str | None] = mapped_column(String(50))
    crawler_provider: Mapped[str | None] = mapped_column(String(50))
    llm_provider: Mapped[str | None] = mapped_column(String(50))
    llm_used: Mapped[bool] = mapped_column(nullable=False, default=False)

    error_message: Mapped[str | None] = mapped_column(Text)
    errors: Mapped[list[dict]] = mapped_column(JSONType, nullable=False, default=list)

    company: Mapped["Company"] = relationship()
    sources: Mapped[list["ResearchSource"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_research_runs_company_created", "company_id", "created_at"),)


class ResearchSource(Base):
    """A retrieved document backing one or more pieces of evidence."""

    __tablename__ = "research_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    research_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_runs.id", ondelete="SET NULL"), index=True
    )
    # Set when this source was ingested from a Phase 1 crawl rather than
    # fetched again, so the two stores stay reconcilable.
    company_page_id: Mapped[int | None] = mapped_column(
        ForeignKey("company_pages.id", ondelete="SET NULL")
    )

    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default=ResearchSourceType.OTHER, index=True
    )

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    content: Mapped[str | None] = mapped_column(Text)
    # sha256 of normalized content: lets a re-run skip unchanged pages.
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    content_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    retrieval_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RetrievalStatus.NOT_FETCHED
    )
    source_reliability: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SourceReliability.UNKNOWN
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)

    run: Mapped["ResearchRun"] = relationship(back_populates="sources")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="source")

    __table_args__ = (
        # A company keeps one row per URL; re-runs update it in place.
        UniqueConstraint("company_id", "url", name="uq_research_sources_company_url"),
        Index("ix_research_sources_company_type", "company_id", "source_type"),
    )


class Evidence(Base, TimestampMixin):
    """One observable claim, always attached to the source that carries it.

    Rows are never rewritten by a later run: a repeat observation updates
    ``last_seen_run_id`` and ``observation_state``, which is what makes change
    detection possible.
    """

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    research_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_runs.id", ondelete="SET NULL"), index=True
    )

    claim: Mapped[str] = mapped_column(Text, nullable=False)
    # Verbatim from the source. Never paraphrased, so the user can verify it.
    excerpt: Mapped[str | None] = mapped_column(Text)
    normalized_value: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    epistemic_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EpistemicStatus.KNOWN
    )
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_level: Mapped[str] = mapped_column(String(10), nullable=False, default="low")
    confidence_components: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)

    # Which layer produced it: "rules" or "llm:<model>". Keeps deterministic
    # extraction distinguishable from model output.
    extractor: Mapped[str] = mapped_column(String(40), nullable=False, default="rules")

    # sha256(company, type, normalized claim) — the idempotency key.
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    first_seen_run_id: Mapped[int | None] = mapped_column(Integer)
    last_seen_run_id: Mapped[int | None] = mapped_column(Integer)
    observation_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ObservationState.NEW
    )
    times_observed: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    source: Mapped["ResearchSource"] = relationship(back_populates="evidence")

    __table_args__ = (
        UniqueConstraint("company_id", "fingerprint", name="uq_evidence_company_fingerprint"),
        Index("ix_evidence_company_type", "company_id", "evidence_type"),
        Index("ix_evidence_company_published", "company_id", "published_at"),
    )


class Contradiction(Base, TimestampMixin):
    """Two sources disagreeing. Recorded, never silently resolved."""

    __tablename__ = "contradictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    research_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_runs.id", ondelete="SET NULL"), index=True
    )

    # What the two claims are about, e.g. "employee_count".
    subject: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_a_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False
    )
    evidence_b_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ContradictionStatus.UNRESOLVED
    )
    # Which side the heuristics favour, if any — the other is still shown.
    preferred_evidence_id: Mapped[int | None] = mapped_column(Integer)
    explanation: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "company_id", "evidence_a_id", "evidence_b_id", name="uq_contradiction_pair"
        ),
    )


class ResearchBrief(Base, TimestampMixin):
    """The human-readable output of a run, rendered deterministically."""

    __tablename__ = "research_briefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    research_run_id: Mapped[int] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    # The structured intelligence profile the markdown was rendered from.
    profile: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    generated_by: Mapped[str] = mapped_column(String(40), nullable=False, default="deterministic")
