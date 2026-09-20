from typing import TYPE_CHECKING

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.discovery import DiscoveryRun

# JSONB on PostgreSQL, plain JSON elsewhere (tests run on SQLite).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Target(Base, TimestampMixin):
    """A user-defined prospecting target: what kind of company to look for, where."""

    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(100))
    company_size: Mapped[str | None] = mapped_column(String(50))
    keywords: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    search_context: Mapped[str | None] = mapped_column(Text)

    runs: Mapped[list["DiscoveryRun"]] = relationship(
        back_populates="target",
        cascade="all, delete-orphan",
        order_by="DiscoveryRun.id.desc()",
    )

    __table_args__ = (Index("ix_targets_industry_location", "industry", "location"),)
