"""String-valued enums.

Stored as plain VARCHAR so that adding a new value in a later phase does not
require a PostgreSQL enum migration.
"""

from enum import StrEnum


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunStage(StrEnum):
    PENDING = "pending"
    GENERATING_QUERIES = "generating_queries"
    SEARCHING = "searching"
    NORMALIZING = "normalizing"
    SAVING = "saving"
    DONE = "done"


class CompanyStatus(StrEnum):
    DISCOVERED = "discovered"
    RESEARCHING = "researching"
    RESEARCHED = "researched"
    RESEARCH_FAILED = "research_failed"


class SourceType(StrEnum):
    SEARCH_RESULT = "search_result"
    COMPANY_WEBSITE = "company_website"
    ABOUT_PAGE = "about_page"
    OTHER = "other"


class PageType(StrEnum):
    HOME = "home"
    ABOUT = "about"
    PRODUCTS = "products"
    SERVICES = "services"
    CONTACT = "contact"
    NEWS = "news"
    BLOG = "blog"
    CAREERS = "careers"
    OTHER = "other"


class CrawlStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# --------------------------------------------------------------------------- #
# Phase 2: research, evidence, signals, opportunities
# --------------------------------------------------------------------------- #


class ResearchStatus(StrEnum):
    NOT_STARTED = "not_started"
    QUEUED = "queued"
    RESEARCHING = "researching"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchStage(StrEnum):
    PENDING = "pending"
    LOADING_COMPANY = "loading_company"
    COLLECTING_PAGES = "collecting_pages"
    DISCOVERING_SOURCES = "discovering_sources"
    CRAWLING_SOURCES = "crawling_sources"
    EXTRACTING_EVIDENCE = "extracting_evidence"
    DERIVING_SIGNALS = "deriving_signals"
    FINDING_PEOPLE = "finding_people"
    MATCHING_CAPABILITIES = "matching_capabilities"
    WRITING_BRIEF = "writing_brief"
    DONE = "done"


class ResearchSourceType(StrEnum):
    """Where a piece of research material came from."""

    COMPANY_WEBSITE = "company_website"
    COMPANY_ABOUT = "company_about"
    COMPANY_PRODUCTS = "company_products"
    COMPANY_SERVICES = "company_services"
    COMPANY_NEWS = "company_news"
    COMPANY_BLOG = "company_blog"
    COMPANY_CAREERS = "company_careers"
    COMPANY_CONTACT = "company_contact"
    PRESS_RELEASE = "press_release"
    NEWS = "news"
    EVENT = "event"
    SEARCH_RESULT = "search_result"
    PUBLIC_PROFILE = "public_profile"
    OTHER = "other"


class RetrievalStatus(StrEnum):
    RETRIEVED = "retrieved"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_FETCHED = "not_fetched"


class SourceReliability(StrEnum):
    """How directly a source speaks for the company.

    Ordered: a company's own site is first-party; a news article is
    second-hand; an aggregator restates others.
    """

    FIRST_PARTY = "first_party"
    PRESS = "press"
    THIRD_PARTY = "third_party"
    AGGREGATED = "aggregated"
    UNKNOWN = "unknown"


class EvidenceType(StrEnum):
    """Generic business-event taxonomy.

    Deliberately industry-neutral: these describe what a company *did*, not
    what sector it belongs to. New values can be added without a migration.
    """

    COMPANY_IDENTITY = "company_identity"
    BUSINESS_MODEL = "business_model"
    PRODUCT_LAUNCH = "product_launch"
    SERVICE_LAUNCH = "service_launch"
    GEOGRAPHIC_EXPANSION = "geographic_expansion"
    NEW_LOCATION = "new_location"
    NEW_STORE = "new_store"
    HIRING = "hiring"
    MARKETING_HIRING = "marketing_hiring"
    LEADERSHIP_CHANGE = "leadership_change"
    PARTNERSHIP = "partnership"
    SPONSORSHIP = "sponsorship"
    EVENT_PARTICIPATION = "event_participation"
    EVENT_ORGANIZATION = "event_organization"
    CAMPAIGN = "campaign"
    BRAND_ACTIVITY = "brand_activity"
    CONTENT_ACTIVITY = "content_activity"
    COMMUNITY_ACTIVITY = "community_activity"
    DIGITAL_ACTIVITY = "digital_activity"
    CUSTOMER_GROWTH = "customer_growth"
    FUNDING = "funding"
    INVESTMENT = "investment"
    ACQUISITION = "acquisition"
    NEW_MARKET = "new_market"
    NEW_PRODUCT = "new_product"
    SEASONAL_ACTIVITY = "seasonal_activity"
    AWARD = "award"
    PRESS_ACTIVITY = "press_activity"
    OTHER = "other"


class EpistemicStatus(StrEnum):
    """How firmly a claim is held. Uncertainty is never promoted to fact."""

    KNOWN = "known"
    INFERRED = "inferred"
    POSSIBLE = "possible"
    UNKNOWN = "unknown"


class Freshness(StrEnum):
    RECENT = "recent"
    ACTIVE = "active"
    OLDER = "older"
    STALE = "stale"
    UNKNOWN = "unknown"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ObservationState(StrEnum):
    """Change detection across successive research runs."""

    NEW = "new"
    STILL_PRESENT = "still_present"
    UPDATED = "updated"
    NOT_FOUND = "not_found"


class OpportunityStatus(StrEnum):
    CANDIDATE = "candidate"
    SUPPORTED = "supported"
    UNCERTAIN = "uncertain"
    DISMISSED = "dismissed"


class ContradictionStatus(StrEnum):
    UNRESOLVED = "unresolved"
    RESOLVED_BY_RECENCY = "resolved_by_recency"
    RESOLVED_BY_RELIABILITY = "resolved_by_reliability"


class VerificationStatus(StrEnum):
    """How a person/contact detail was established. Never inferred."""

    PUBLIC_COMPANY_SOURCE = "public_company_source"
    PUBLIC_THIRD_PARTY = "public_third_party"
    ROLE_ONLY = "role_only"
    UNVERIFIED = "unverified"


# --------------------------------------------------------------------------- #
# Phase 3: outreach, approval, Gmail drafts, follow-ups
# --------------------------------------------------------------------------- #


class OutreachStatus(StrEnum):
    """Lifecycle of one outreach message.

    ``GMAIL_DRAFT_CREATED`` deliberately sits before ``SENT``: creating a
    draft is not sending, and the system never claims otherwise.
    """

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    GMAIL_DRAFT_CREATED = "gmail_draft_created"
    SENT = "sent"
    FOLLOW_UP_DUE = "follow_up_due"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OutreachObjective(StrEnum):
    START_CONVERSATION = "start_conversation"
    REQUEST_SHORT_CALL = "request_short_call"
    SHARE_IDEA = "share_idea"
    EXPLORE_PARTNERSHIP = "explore_partnership"
    INTRODUCE_CAPABILITY = "introduce_capability"
    FOLLOW_UP = "follow_up"
    RECONNECT = "reconnect"


class OutreachTone(StrEnum):
    PROFESSIONAL = "professional"
    CONVERSATIONAL = "conversational"
    DIRECT = "direct"
    WARM = "warm"


class MessageLength(StrEnum):
    SHORT = "short"
    MEDIUM = "medium"


class GenerationMethod(StrEnum):
    AI = "ai"
    DETERMINISTIC = "deterministic"
    USER_EDIT = "user_edit"
    REGENERATED = "regenerated"


class ClaimKind(StrEnum):
    """What role a generated sentence plays.

    ``COMPANY_FACT`` and ``SIGNAL_REFERENCE`` must carry evidence;
    the others are about UBM or the ask, so they carry none.
    """

    COMPANY_FACT = "company_fact"
    SIGNAL_REFERENCE = "signal_reference"
    CAPABILITY_STATEMENT = "capability_statement"
    CALL_TO_ACTION = "call_to_action"
    GREETING = "greeting"
    CLOSING = "closing"


class OutcomeStatus(StrEnum):
    NO_RESPONSE = "no_response"
    REPLIED = "replied"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    MEETING_SCHEDULED = "meeting_scheduled"
    OPPORTUNITY_WON = "opportunity_won"
    OPPORTUNITY_LOST = "opportunity_lost"
    DO_NOT_CONTACT = "do_not_contact"


class OutcomeReason(StrEnum):
    """Optional structured feedback, stored for later analysis of the
    opportunity engine. Nothing is trained on it automatically."""

    WRONG_OPPORTUNITY = "wrong_opportunity"
    WRONG_PERSON = "wrong_person"
    WRONG_COMPANY = "wrong_company"
    TIMING = "timing"
    ALREADY_HAS_PROVIDER = "already_has_provider"
    NO_BUDGET = "no_budget"
    NOT_RELEVANT = "not_relevant"
    OTHER = "other"


class CampaignStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class GmailConnectionStatus(StrEnum):
    CONNECTED = "connected"
    EXPIRED = "expired"
    REVOKED = "revoked"
    DISCONNECTED = "disconnected"


class AuditAction(StrEnum):
    OUTREACH_CREATED = "outreach_created"
    EMAIL_GENERATED = "email_generated"
    EMAIL_EDITED = "email_edited"
    EMAIL_REGENERATED = "email_regenerated"
    VERSION_ACTIVATED = "version_activated"
    EMAIL_APPROVED = "email_approved"
    EMAIL_REJECTED = "email_rejected"
    GMAIL_DRAFT_CREATED = "gmail_draft_created"
    GMAIL_CONNECTED = "gmail_connected"
    GMAIL_DISCONNECTED = "gmail_disconnected"
    MARKED_SENT = "marked_sent"
    FOLLOW_UP_CREATED = "follow_up_created"
    OUTCOME_UPDATED = "outcome_updated"
    OUTREACH_CANCELLED = "outreach_cancelled"
    CAMPAIGN_CREATED = "campaign_created"
