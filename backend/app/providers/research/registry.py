from __future__ import annotations

from app.core.errors import AppError
from app.providers.research.base import ResearchSourceProvider
from app.providers.research.web_research import WebResearchProvider

_BUILDERS: dict[str, type[ResearchSourceProvider]] = {
    "web_search": WebResearchProvider,
}


def available_providers() -> list[str]:
    return sorted(_BUILDERS)


def get_research_provider(name: str | None = None) -> ResearchSourceProvider:
    key = (name or "web_search").lower().strip()
    builder = _BUILDERS.get(key)
    if builder is None:
        raise AppError(
            f"Unknown research provider '{key}'. Available: {', '.join(available_providers())}."
        )
    return builder()
