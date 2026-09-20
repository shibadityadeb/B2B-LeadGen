"""Application configuration, sourced entirely from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- application ---
    app_name: str = "UBM Growth Opportunity Engine"
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # --- database ---
    # postgresql+asyncpg://user:password@host:5432/dbname
    database_url: str = "postgresql+asyncpg://ubm:ubm@localhost:5432/ubm"
    db_echo: bool = False

    # --- search provider ---
    # duckduckgo needs no setup at all; searxng needs a running instance.
    search_provider: str = "duckduckgo"
    searxng_url: str = "http://localhost:8080"
    search_timeout_seconds: float = 25.0
    search_results_per_query: int = 20
    search_max_queries_per_run: int = 12
    search_delay_seconds: float = 1.0
    # Comma-separated extra domains to treat as directories/aggregators,
    # added to the built-in list in app.services.normalization.
    search_excluded_domains: str = ""

    # --- crawler provider ---
    crawler_provider: str = "auto"  # auto | crawl4ai | httpx
    crawl_max_pages: int = 8
    crawl_timeout_seconds: float = 20.0
    crawl_delay_seconds: float = 1.0
    crawl_respect_robots: bool = True
    crawl_user_agent: str = "UBM-GrowthEngine/1.0 (+https://www.upshotbrandmedia.com/; research crawler)"
    crawl_max_content_chars: int = 40000

    # --- research (phase 2) ---
    research_max_sources: int = 25
    research_max_search_queries: int = 6
    research_results_per_query: int = 10
    research_max_pages_to_crawl: int = 10
    # Short factual statements ("X opened 3 new stores in Indore.") are real
    # evidence; 40+ characters discarded them.
    research_min_excerpt_chars: int = 30
    research_max_excerpt_chars: int = 400
    # How many companies a bulk research batch may process concurrently.
    research_batch_concurrency: int = 2

    # Freshness thresholds in days. Configurable: these are reporting
    # conventions, not business rules, and no industry may override them.
    freshness_recent_days: int = 30
    freshness_active_days: int = 90
    freshness_older_days: int = 365

    # --- LLM reasoning layer (optional; the pipeline works without it) ---
    # none | ollama
    llm_provider: str = "none"
    llm_model: str = "llama3.1:8b"
    llm_timeout_seconds: float = 120.0
    llm_max_evidence_items: int = 40

    # --- optional local LLM ---
    ollama_url: str = "http://localhost:11434"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
