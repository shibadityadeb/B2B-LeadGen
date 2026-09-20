from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResearchSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    domain: str | None
    title: str | None
    source_type: str
    source_reliability: str
    retrieval_status: str
    published_at: datetime | None
    discovered_at: datetime | None
    retrieved_at: datetime | None
    content_length: int
    error_message: str | None


class EvidenceSourceRef(BaseModel):
    """The provenance shown next to every claim in the UI."""

    id: int
    url: str
    title: str | None = None
    type: str | None = None
    reliability: str | None = None


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim: str
    excerpt: str | None
    evidence_type: str
    epistemic_status: str
    normalized_value: dict = {}
    confidence: float
    confidence_level: str
    confidence_components: dict = {}
    observation_state: str
    times_observed: int
    published_at: datetime | None
    observed_at: datetime | None
    extractor: str
    source: EvidenceSourceRef | None = None
    # Computed at serialization time from the configured thresholds.
    freshness: str | None = None
    age_days: int | None = None
    # "published_at" | "observed_at" | "none". Without this, an undated page
    # retrieved today looks indistinguishable from a story published today.
    freshness_basis: str | None = None


class SignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    signal_type: str
    title: str
    description: str
    strength: float
    freshness: str
    confidence: float
    confidence_level: str
    confidence_components: dict = {}
    evidence_count: int
    observation_state: str
    latest_evidence_at: datetime | None
    evidence_ids: list[int] = []


class CapabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: str
    category: str | None
    signal_types: list[str] = []
    keywords: list[str] = []
    rationale_template: str | None
    weight: float
    active: bool
    is_seed: bool
    created_at: datetime
    updated_at: datetime


class CapabilityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=10)
    slug: str | None = Field(default=None, max_length=80)
    category: str | None = Field(default=None, max_length=80)
    signal_types: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    rationale_template: str | None = None
    weight: float = Field(default=1.0, ge=0.1, le=2.0)
    active: bool = True

    @field_validator("signal_types")
    @classmethod
    def _known_signal_types(cls, value: list[str]) -> list[str]:
        """Reject unknown types: a capability keyed to a signal that can never
        fire would silently never match."""
        from app.services.evidence_taxonomy import SIGNAL_GROUPS

        unknown = [item for item in value if item not in SIGNAL_GROUPS]
        if unknown:
            raise ValueError(
                f"Unknown signal types: {', '.join(unknown)}. "
                f"Valid values: {', '.join(sorted(SIGNAL_GROUPS))}."
            )
        return value


class CapabilityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, min_length=10)
    category: str | None = None
    signal_types: list[str] | None = None
    keywords: list[str] | None = None
    rationale_template: str | None = None
    weight: float | None = Field(default=None, ge=0.1, le=2.0)
    active: bool | None = None

    _known = field_validator("signal_types")(CapabilityCreate._known_signal_types.__func__)


class OpportunityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    capability_id: int
    capability_name: str | None = None
    capability_category: str | None = None
    title: str
    description: str
    why_relevant: str
    confidence: float
    confidence_level: str
    confidence_components: dict = {}
    freshness: str
    status: str
    evidence_count: int
    observation_state: str
    evidence_ids: list[int] = []
    signal_ids: list[int] = []
    created_at: datetime
    updated_at: datetime


class OpportunityStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _valid(cls, value: str) -> str:
        from app.models.enums import OpportunityStatus

        allowed = {str(item) for item in OpportunityStatus}
        if value not in allowed:
            raise ValueError(f"status must be one of: {', '.join(sorted(allowed))}")
        return value


class DecisionMakerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None
    role: str
    role_category: str | None
    email: str | None
    phone: str | None
    profile_url: str | None
    verification_status: str
    confidence: float
    confidence_level: str
    excerpt: str | None
    observation_state: str
    source_url: str | None = None
    created_at: datetime


class ContradictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    status: str
    explanation: str | None
    evidence_a_id: int
    evidence_b_id: int
    preferred_evidence_id: int | None


class ResearchRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    status: str
    stage: str
    progress: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    sources_discovered: int
    sources_retrieved: int
    sources_failed: int
    evidence_count: int
    new_evidence_count: int
    signals_count: int
    opportunities_count: int
    decision_makers_count: int
    contradictions_count: int

    search_provider: str | None
    crawler_provider: str | None
    llm_provider: str | None
    llm_used: bool
    error_message: str | None
    errors: list[dict] = []

    company_name: str | None = None
    company_domain: str | None = None


class ResearchRunDetail(ResearchRunRead):
    sources: list[ResearchSourceRead] = []
    brief_markdown: str | None = None
    #: The structured profile the markdown was rendered from. The UI renders
    #: this rather than parsing the markdown back out again.
    brief_profile: dict | None = None


class ResearchBriefRead(BaseModel):
    research_run_id: int
    markdown: str
    profile: dict
    generated_by: str
    created_at: datetime


class CompanyResearchState(BaseModel):
    """Everything the company page needs to render its research tabs."""

    company_id: int
    research_status: str
    latest_run: ResearchRunRead | None = None
    runs: list[ResearchRunRead] = []
    counts: dict[str, int] = {}
    brief: ResearchBriefRead | None = None


class BulkResearchRequest(BaseModel):
    company_ids: list[int] = Field(min_length=1, max_length=50)

    @field_validator("company_ids")
    @classmethod
    def _unique(cls, value: list[int]) -> list[int]:
        seen: set[int] = set()
        ordered: list[int] = []
        for item in value:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered


class BulkResearchResponse(BaseModel):
    queued: list[ResearchRunRead]
    skipped: list[dict] = []
