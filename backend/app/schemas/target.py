from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

COMPANY_SIZES = ("any", "1-10", "11-50", "51-200", "201-500", "501-1000", "1000+")


class TargetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    industry: str = Field(min_length=2, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    company_size: str | None = None
    keywords: list[str] = Field(default_factory=list)
    search_context: str | None = Field(default=None, max_length=2000)

    @field_validator("name", "industry", "location", "country", "search_context", mode="before")
    @classmethod
    def _strip(cls, value):
        if isinstance(value, str):
            value = " ".join(value.split())
            return value or None
        return value

    @field_validator("company_size")
    @classmethod
    def _validate_size(cls, value):
        if value in (None, "", "any"):
            return None
        if value not in COMPANY_SIZES:
            raise ValueError(f"company_size must be one of: {', '.join(COMPANY_SIZES)}")
        return value

    @field_validator("keywords", mode="before")
    @classmethod
    def _clean_keywords(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            value = [part for part in value.replace("\n", ",").split(",")]
        cleaned: list[str] = []
        seen: set[str] = set()
        for keyword in value:
            if not isinstance(keyword, str):
                continue
            keyword = " ".join(keyword.split())
            if keyword and keyword.lower() not in seen and len(keyword) <= 120:
                seen.add(keyword.lower())
                cleaned.append(keyword)
        return cleaned[:25]


class TargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    industry: str
    location: str | None
    country: str | None
    company_size: str | None
    keywords: list[str]
    search_context: str | None
    created_at: datetime
    updated_at: datetime


class TargetListItem(TargetRead):
    companies_count: int = 0
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    last_run_id: int | None = None


class TargetPreview(BaseModel):
    """Queries a target would generate — lets the user sanity-check before running."""

    queries: list[str]
