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
