from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import RunStage, RunStatus
from app.models.target import JSONType

if TYPE_CHECKING:
    from app.models.company import CompanySource
    from app.models.target import Target


class DiscoveryRun(Base, TimestampMixin):
    """One execution of the discovery pipeline for a target."""

    __tablename__ = "discovery_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(
        ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RunStatus.QUEUED, index=True
    )
    stage: Mapped[str] = mapped_column(String(40), nullable=False, default=RunStage.PENDING)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Real counters, written by the pipeline as it progresses.
    queries_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    results_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_domains_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_companies_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_companies_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_results_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_queries_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    search_provider: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)
    errors: Mapped[list[dict]] = mapped_column(JSONType, nullable=False, default=list)

    target: Mapped["Target"] = relationship(back_populates="runs")
    queries: Mapped[list["SearchQuery"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="SearchQuery.id"
    )
    sources: Mapped[list["CompanySource"]] = relationship(back_populates="run")


class SearchQuery(Base):
    """A single query string generated for a run, plus its execution outcome."""

    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    discovery_run_id: Mapped[int] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    template: Mapped[str | None] = mapped_column(String(100))
    provider: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    results_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped["DiscoveryRun"] = relationship(back_populates="queries")
    results: Mapped[list["SearchResult"]] = relationship(
        back_populates="query", cascade="all, delete-orphan"
    )


class SearchResult(Base):
    """A raw, unmodified search hit. Kept verbatim for provenance."""

    __tablename__ = "search_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    search_query_id: Mapped[int] = mapped_column(
        ForeignKey("search_queries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    discovery_run_id: Mapped[int] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text)
    source_engine: Mapped[str | None] = mapped_column(String(100))
    position: Mapped[int | None] = mapped_column(Integer)
    extracted_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    accepted: Mapped[bool] = mapped_column(nullable=False, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(100))
    raw: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    query: Mapped["SearchQuery"] = relationship(back_populates="results")

    __table_args__ = (Index("ix_search_results_run_domain", "discovery_run_id", "extracted_domain"),)
