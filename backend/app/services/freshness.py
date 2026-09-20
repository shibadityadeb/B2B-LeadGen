"""Freshness classification.

Old evidence is never deleted — its age is exposed instead, so the reader can
weigh it themselves. Thresholds come from configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import settings
from app.models.enums import Freshness


@dataclass(frozen=True)
class FreshnessResult:
    freshness: Freshness
    age_days: int | None
    reference: datetime | None
    basis: str  # "published_at" | "observed_at" | "none"

    def dict(self) -> dict:
        return {
            "freshness": str(self.freshness),
            "age_days": self.age_days,
            "basis": self.basis,
        }


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def classify(
    published_at: datetime | None,
    observed_at: datetime | None = None,
    *,
    now: datetime | None = None,
) -> FreshnessResult:
    """Classify an item by its publication date, falling back to observation.

    An item we merely *observed* recently is not evidence that the underlying
    event is recent, so the basis is reported alongside the verdict.
    """
    now = _as_utc(now) or datetime.now(UTC)
    published_at = _as_utc(published_at)
    observed_at = _as_utc(observed_at)

    reference, basis = (
        (published_at, "published_at") if published_at else (observed_at, "observed_at")
    )
    if reference is None:
        return FreshnessResult(Freshness.UNKNOWN, None, None, "none")

    age_days = max(0, (now - reference).days)

    if age_days <= settings.freshness_recent_days:
        level = Freshness.RECENT
    elif age_days <= settings.freshness_active_days:
        level = Freshness.ACTIVE
    elif age_days <= settings.freshness_older_days:
        level = Freshness.OLDER
    else:
        level = Freshness.STALE

    return FreshnessResult(level, age_days, reference, basis)


# Used when aggregating: a group is only as fresh as its freshest member.
_RANK = {
    Freshness.RECENT: 4,
    Freshness.ACTIVE: 3,
    Freshness.OLDER: 2,
    Freshness.STALE: 1,
    Freshness.UNKNOWN: 0,
}


def best(values: list[Freshness | str]) -> Freshness:
    if not values:
        return Freshness.UNKNOWN
    return max((Freshness(value) for value in values), key=lambda item: _RANK[item])


def score(freshness: Freshness | str) -> float:
    """0..1 recency contribution for the confidence formula."""
    return {
        Freshness.RECENT: 1.0,
        Freshness.ACTIVE: 0.75,
        Freshness.OLDER: 0.45,
        Freshness.STALE: 0.2,
        Freshness.UNKNOWN: 0.35,
    }[Freshness(freshness)]
