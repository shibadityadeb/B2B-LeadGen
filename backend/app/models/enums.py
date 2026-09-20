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
