from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import CompanyStatus, CrawlStatus, PageType, SourceType

if TYPE_CHECKING:
    from app.models.discovery import DiscoveryRun


class Company(Base, TimestampMixin):
    """A discovered company, keyed on its canonical domain."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    canonical_domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    website_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Everything below may legitimately be unknown in Phase 1.
    description: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(200), index=True)
    location: Mapped[str | None] = mapped_column(String(200), index=True)
    country: Mapped[str | None] = mapped_column(String(100))
    company_size: Mapped[str | None] = mapped_column(String(50))

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=CompanyStatus.DISCOVERED, index=True
    )
    crawl_error: Mapped[str | None] = mapped_column(Text)

    first_discovery_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="SET NULL"), index=True
    )
    last_researched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sources: Mapped[list["CompanySource"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="CompanySource.id",
    )
    pages: Mapped[list["CompanyPage"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="CompanyPage.id",
    )


class CompanySource(Base):
    """Evidence provenance: where a company (or a fact about it) came from."""

    __tablename__ = "company_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    discovery_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="SET NULL"), index=True
    )
    target_id: Mapped[int | None] = mapped_column(
        ForeignKey("targets.id", ondelete="SET NULL"), index=True
    )
    search_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("search_results.id", ondelete="SET NULL")
    )

    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default=SourceType.SEARCH_RESULT
    )
    source_engine: Mapped[str | None] = mapped_column(String(100))
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    company: Mapped["Company"] = relationship(back_populates="sources")
    run: Mapped["DiscoveryRun"] = relationship(back_populates="sources")

    __table_args__ = (
        UniqueConstraint("company_id", "url", name="uq_company_sources_company_url"),
    )


class CompanyPage(Base):
    """A page fetched from a company website during the initial crawl."""

    __tablename__ = "company_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    page_type: Mapped[str] = mapped_column(String(30), nullable=False, default=PageType.OTHER)
    title: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    content_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CrawlStatus.SUCCESS)
    http_status: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped["Company"] = relationship(back_populates="pages")

    __table_args__ = (
        UniqueConstraint("company_id", "url", name="uq_company_pages_company_url"),
        Index("ix_company_pages_company_type", "company_id", "page_type"),
    )
