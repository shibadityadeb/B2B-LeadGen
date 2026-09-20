from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    CampaignStatus,
    MessageLength,
    OutcomeReason,
    OutcomeStatus,
    OutreachObjective,
    OutreachStatus,
    OutreachTone,
)


def _enum_validator(enum_class, field_name: str):
    def check(value):
        if value is None:
            return value
        allowed = {str(item) for item in enum_class}
        if str(value) not in allowed:
            raise ValueError(f"{field_name} must be one of: {', '.join(sorted(allowed))}")
        return str(value)

    return check


# --------------------------------------------------------------------------- #
# sender profile
# --------------------------------------------------------------------------- #


class SenderProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str | None
    company: str
    email: str | None
    website: str | None
    signature: str | None
    is_default: bool
    created_at: datetime
    updated_at: datetime


class SenderProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    role: str | None = Field(default=None, max_length=160)
    company: str | None = Field(default=None, min_length=2, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    website: str | None = Field(default=None, max_length=255)
    signature: str | None = None

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value):
        if value in (None, ""):
            return None
        from app.services.outreach_validation import EMAIL_PATTERN

        if not EMAIL_PATTERN.match(value.strip()):
            raise ValueError("Not a valid email address")
        return value.strip()


# --------------------------------------------------------------------------- #
# evidence-bound claims
# --------------------------------------------------------------------------- #


class ClaimEvidenceRef(BaseModel):
    """What the reviewer checks a personalized sentence against."""

    evidence_id: int
    claim: str | None = None
    excerpt: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    published_at: datetime | None = None
    freshness: str | None = None
    freshness_basis: str | None = None


class OutreachClaimRead(BaseModel):
    id: int
    text: str
    kind: str
    requires_evidence: bool
    evidence: list[ClaimEvidenceRef] = []


class OutreachVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_number: int
    subject: str | None
    body: str | None
    generation_method: str
    is_active: bool
    created_at: datetime
    validation: dict = {}
    claims: list[OutreachClaimRead] = []


class OutreachOutcomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    reason: str | None
    notes: str | None
    recorded_by: str | None
    created_at: datetime


# --------------------------------------------------------------------------- #
# outreach
# --------------------------------------------------------------------------- #


class OutreachRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    opportunity_id: int | None
    decision_maker_id: int | None
    campaign_id: int | None
    parent_outreach_id: int | None
    follow_up_number: int

    status: str
    objective: str
    tone: str
    message_length: str

    to_email: str | None
    to_name: str | None
    cc: str | None
    bcc: str | None

    subject: str | None
    body: str | None
    ai_generated_subject: str | None
    ai_generated_body: str | None
    user_edited: bool
    generated_by: str

    strategy: dict = {}
    personalization: dict = {}
    validation: dict = {}

    gmail_draft_id: str | None
    gmail_draft_url: str | None
    approved_at: datetime | None
    gmail_draft_created_at: datetime | None
    sent_at: datetime | None
    next_follow_up_at: datetime | None

    outcome_status: str | None
    outcome_reason: str | None
    outcome_notes: str | None
    outcome_updated_at: datetime | None

    active_version_id: int | None
    owner: str | None
    created_at: datetime
    updated_at: datetime

    # --- denormalized for list rendering ---
    company_name: str | None = None
    company_domain: str | None = None
    company_industry: str | None = None
    opportunity_title: str | None = None
    capability_name: str | None = None
    campaign_name: str | None = None
    recipient_role: str | None = None
    #: True when next_follow_up_at has passed.
    follow_up_due: bool = False


class OutreachDetail(OutreachRead):
    versions: list[OutreachVersionRead] = []
    outcomes: list[OutreachOutcomeRead] = []
    follow_ups: list[OutreachRead] = []
    audit: list[dict] = []


class OutreachCreate(BaseModel):
    decision_maker_id: int | None = None
    campaign_id: int | None = None
    tone: str = OutreachTone.PROFESSIONAL
    message_length: str = MessageLength.SHORT
    objective: str | None = None

    _tone = field_validator("tone")(_enum_validator(OutreachTone, "tone"))
    _length = field_validator("message_length")(
        _enum_validator(MessageLength, "message_length")
    )
    _objective = field_validator("objective")(
        _enum_validator(OutreachObjective, "objective")
    )


class OutreachUpdate(BaseModel):
    subject: str | None = None
    body: str | None = None
    to_email: str | None = None
    to_name: str | None = None
    cc: str | None = None
    bcc: str | None = None

    @field_validator("to_email")
    @classmethod
    def _valid_email(cls, value):
        if value in (None, ""):
            return value
        from app.services.outreach_validation import EMAIL_PATTERN

        if not EMAIL_PATTERN.match(value.strip()):
            raise ValueError("Not a valid email address")
        return value.strip()


class RegenerateRequest(BaseModel):
    tone: str | None = None
    message_length: str | None = None
    objective: str | None = None

    _tone = field_validator("tone")(_enum_validator(OutreachTone, "tone"))
    _length = field_validator("message_length")(
        _enum_validator(MessageLength, "message_length")
    )
    _objective = field_validator("objective")(
        _enum_validator(OutreachObjective, "objective")
    )


class RejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class GmailDraftRequest(BaseModel):
    #: Only set when the user explicitly wants a second draft.
    force_new: bool = False


class MarkSentRequest(BaseModel):
    sent_at: datetime | None = None


class OutcomeUpdate(BaseModel):
    status: str
    reason: str | None = None
    notes: str | None = Field(default=None, max_length=2000)

    _status = field_validator("status")(_enum_validator(OutcomeStatus, "status"))
    _reason = field_validator("reason")(_enum_validator(OutcomeReason, "reason"))


class ActivateVersionRequest(BaseModel):
    version_id: int


# --------------------------------------------------------------------------- #
# campaigns
# --------------------------------------------------------------------------- #


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    target_id: int | None
    sender_profile_id: int | None
    tone: str
    message_length: str
    follow_up_intervals: list[int]
    status: str
    owner: str | None
    created_at: datetime
    updated_at: datetime

    target_name: str | None = None
    outreach_counts: dict[str, int] = {}
    outreach_total: int = 0


class CampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None
    target_id: int | None = None
    tone: str = OutreachTone.PROFESSIONAL
    message_length: str = MessageLength.SHORT
    follow_up_intervals: list[int] = Field(default_factory=lambda: [3, 7, 14])

    _tone = field_validator("tone")(_enum_validator(OutreachTone, "tone"))
    _length = field_validator("message_length")(
        _enum_validator(MessageLength, "message_length")
    )

    @field_validator("follow_up_intervals")
    @classmethod
    def _positive_increasing(cls, value: list[int]) -> list[int]:
        if not value:
            return [3, 7, 14]
        if any(day <= 0 for day in value):
            raise ValueError("Follow-up intervals must be positive numbers of days")
        if list(value) != sorted(value):
            raise ValueError("Follow-up intervals must increase")
        return value[:5]


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    status: str | None = None

    _status = field_validator("status")(_enum_validator(CampaignStatus, "status"))


class PrepareOutreachRequest(BaseModel):
    """Prepare drafts for several opportunities at once. Nothing is sent."""

    opportunity_ids: list[int] = Field(min_length=1, max_length=50)

    @field_validator("opportunity_ids")
    @classmethod
    def _unique(cls, value: list[int]) -> list[int]:
        seen: set[int] = set()
        ordered: list[int] = []
        for item in value:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered


class PrepareOutreachResponse(BaseModel):
    created: list[OutreachRead] = []
    skipped: list[dict] = []


# --------------------------------------------------------------------------- #
# gmail + analytics
# --------------------------------------------------------------------------- #


class GmailConnectionRead(BaseModel):
    """Connection state for the UI.

    Deliberately carries no token fields: credentials stay server-side.
    """

    connected: bool
    configured: bool
    account_email: str | None = None
    status: str | None = None
    scopes: list[str] = []
    connected_at: datetime | None = None
    needs_reauth: bool = False
    detail: str | None = None


class GmailAuthUrl(BaseModel):
    authorization_url: str


class OutreachAnalytics(BaseModel):
    """Real counts only. Rates are omitted below a usable sample size."""

    opportunities_total: int
    outreach_total: int
    by_status: dict[str, int]
    by_outcome: dict[str, int]
    drafts: int
    awaiting_review: int
    approved: int
    gmail_drafts: int
    marked_sent: int
    follow_ups_due: int
    replies: int
    meetings: int
    won: int
    lost: int
    edited_before_approval: int
    versions_total: int
    approval_rate: float | None = None
    reply_rate: float | None = None
    #: Explains why a rate is null rather than showing a misleading number.
    rate_note: str | None = None
    recent: list[OutreachRead] = []
