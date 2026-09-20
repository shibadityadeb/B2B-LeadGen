from __future__ import annotations

from app.core.errors import AppError
from app.providers.people.base import DecisionMakerProvider
from app.providers.people.website_people import WebsitePeopleProvider

_BUILDERS: dict[str, type[DecisionMakerProvider]] = {
    "website_pages": WebsitePeopleProvider,
}


def available_providers() -> list[str]:
    return sorted(_BUILDERS)


def get_people_provider(name: str | None = None) -> DecisionMakerProvider:
    key = (name or "website_pages").lower().strip()
    builder = _BUILDERS.get(key)
    if builder is None:
        raise AppError(
            f"Unknown decision-maker provider '{key}'. Available: {', '.join(available_providers())}."
        )
    return builder()
