"""Detects sources that disagree about the same attribute.

The system never silently picks a winner. It records both claims, states
which one the heuristics favour and why, and leaves the disagreement visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.models import Evidence
from app.models.enums import ContradictionStatus, SourceReliability

# Attributes where two different values genuinely conflict. Comparing free
# text would produce noise, so only structured values are checked.
COMPARABLE_ATTRIBUTES = ("employee_count", "founded_year")

# Headcounts drift; only a material gap counts as a contradiction.
NUMERIC_TOLERANCE = {"employee_count": 0.25, "founded_year": 0.0}

_RELIABILITY_RANK = {
    SourceReliability.FIRST_PARTY: 4,
    SourceReliability.PRESS: 3,
    SourceReliability.THIRD_PARTY: 2,
    SourceReliability.AGGREGATED: 1,
    SourceReliability.UNKNOWN: 0,
}


@dataclass
class DetectedContradiction:
    subject: str
    evidence_a_id: int
    evidence_b_id: int
    status: ContradictionStatus
    preferred_evidence_id: int | None
    explanation: str


def _conflicts(attribute: str, a: object, b: object) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a == b:
            return False
        tolerance = NUMERIC_TOLERANCE.get(attribute, 0.0)
        largest = max(abs(a), abs(b)) or 1
        return abs(a - b) / largest > tolerance
    return str(a).strip().lower() != str(b).strip().lower()


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _prefer(a: Evidence, b: Evidence) -> tuple[int | None, ContradictionStatus, str]:
    """Which claim the heuristics favour — recency first, then reliability.

    Returns no preference when neither rule separates them; the pair stays
    unresolved rather than being decided arbitrarily.
    """
    a_date, b_date = _as_utc(a.published_at), _as_utc(b.published_at)
    if a_date and b_date and a_date != b_date:
        newer, older = (a, b) if a_date > b_date else (b, a)
        return (
            newer.id,
            ContradictionStatus.RESOLVED_BY_RECENCY,
            f"The newer source ({newer.published_at:%d %b %Y}) is preferred over the "
            f"older one ({older.published_at:%d %b %Y}); both are kept on record.",
        )

    a_rank = _RELIABILITY_RANK.get(a.source.source_reliability if a.source else "unknown", 0)
    b_rank = _RELIABILITY_RANK.get(b.source.source_reliability if b.source else "unknown", 0)
    if a_rank != b_rank:
        stronger = a if a_rank > b_rank else b
        return (
            stronger.id,
            ContradictionStatus.RESOLVED_BY_RELIABILITY,
            "Neither claim carries a date, so the more direct source "
            f"({stronger.source.source_reliability if stronger.source else 'unknown'}) "
            "is preferred; both are kept on record.",
        )

    return (
        None,
        ContradictionStatus.UNRESOLVED,
        "Two public sources disagree and neither is clearly more recent or more "
        "direct. The conflict is reported rather than resolved.",
    )


def detect(evidence_items: list[Evidence]) -> list[DetectedContradiction]:
    """Find conflicting structured claims, one row per disputed attribute.

    Comparing every pair produces n-squared noise: six differing founding
    years would yield fifteen near-identical rows. Instead each attribute
    yields a single contradiction naming every distinct value, anchored to
    two representative evidence items.
    """
    by_attribute: dict[str, list[Evidence]] = {}
    for item in evidence_items:
        value = item.normalized_value or {}
        attribute = value.get("attribute")
        if attribute in COMPARABLE_ATTRIBUTES and value.get("value") is not None:
            by_attribute.setdefault(attribute, []).append(item)

    found: list[DetectedContradiction] = []
    for attribute, members in by_attribute.items():
        # One claim per source: a site repeating a figure is not a conflict.
        by_source: dict[int, Evidence] = {}
        for item in members:
            by_source.setdefault(item.source_id, item)
        distinct = list(by_source.values())
        if len(distinct) < 2:
            continue

        # Anchor on the two most divergent values, which is the clearest way
        # to show the disagreement.
        def sort_key(item: Evidence):
            raw = (item.normalized_value or {}).get("value")
            return (0, raw) if isinstance(raw, (int, float)) else (1, str(raw))

        ordered = sorted(distinct, key=sort_key)
        low, high = ordered[0], ordered[-1]
        low_value = (low.normalized_value or {}).get("value")
        high_value = (high.normalized_value or {}).get("value")
        if not _conflicts(attribute, low_value, high_value):
            continue

        a, b = (low, high) if low.id <= high.id else (high, low)
        preferred, status, explanation = _prefer(a, b)

        values = sorted({str((item.normalized_value or {}).get("value")) for item in distinct})
        label = attribute.replace("_", " ")
        found.append(
            DetectedContradiction(
                subject=attribute,
                evidence_a_id=a.id,
                evidence_b_id=b.id,
                status=status,
                preferred_evidence_id=preferred,
                explanation=(
                    f"Conflicting public information about {label}: "
                    f"{len(distinct)} sources give {', '.join(values)}. {explanation}"
                ),
            )
        )
    return found
