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

    # --- optional local LLM (NOT used by Phase 1 logic) ---
    ollama_url: str = "http://localhost:11434"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
