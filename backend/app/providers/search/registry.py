"""Chooses the active search provider from configuration."""

from __future__ import annotations

from app.core.config import settings
from app.core.errors import AppError
from app.providers.search.base import SearchProvider
from app.providers.search.duckduckgo import DuckDuckGoSearchProvider
from app.providers.search.searxng import SearxngSearchProvider

_BUILDERS: dict[str, type[SearchProvider]] = {
    "duckduckgo": DuckDuckGoSearchProvider,
    "searxng": SearxngSearchProvider,
}


def available_providers() -> list[str]:
    return sorted(_BUILDERS)


def get_search_provider(name: str | None = None) -> SearchProvider:
    key = (name or settings.search_provider).lower().strip()
    builder = _BUILDERS.get(key)
    if builder is None:
        raise AppError(
            f"Unknown search provider '{key}'. Available: {', '.join(available_providers())}."
        )
    return builder()
