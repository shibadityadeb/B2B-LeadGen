from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import ConfidenceLevel, Freshness
from app.services import confidence, freshness


def _ago(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


@pytest.mark.parametrize(
    "days,expected",
    [(0, Freshness.RECENT), (29, Freshness.RECENT), (60, Freshness.ACTIVE),
     (200, Freshness.OLDER), (800, Freshness.STALE)],
)
def test_freshness_thresholds(days, expected):
    assert freshness.classify(_ago(days)).freshness == expected


def test_freshness_is_unknown_without_any_date():
    result = freshness.classify(None, None)
    assert result.freshness == Freshness.UNKNOWN
    assert result.age_days is None and result.basis == "none"


def test_freshness_falls_back_to_observation_and_says_so():
    """An undated page must not masquerade as freshly published."""
    result = freshness.classify(None, _ago(1))
    assert result.freshness == Freshness.RECENT
    assert result.basis == "observed_at"


def test_thresholds_are_configurable(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "freshness_recent_days", 1)
    assert freshness.classify(_ago(10)).freshness != Freshness.RECENT


def test_best_freshness_wins_in_a_group():
    assert freshness.best([Freshness.STALE, Freshness.RECENT, Freshness.OLDER]) == Freshness.RECENT


def test_confidence_rises_with_better_evidence():
    weak = confidence.score_evidence(
        reliability="aggregated", epistemic_status="possible", freshness="stale"
    )
    strong = confidence.score_evidence(
        reliability="first_party",
        epistemic_status="known",
        freshness="recent",
        corroborating_sources=3,
        freshness_basis="published_at",
    )
    assert strong.score > weak.score
    assert strong.level == ConfidenceLevel.HIGH and weak.level == ConfidenceLevel.LOW


def test_confidence_components_are_exposed():
    """The number must be inspectable, not opaque."""
    result = confidence.score_evidence(
        reliability="first_party", epistemic_status="known", freshness="recent"
    )
    payload = result.dict()
    assert set(payload["components"]) == {
        "source_quality", "source_count", "recency", "directness", "agreement"
    }
    assert payload["weights"] and abs(sum(payload["weights"].values()) - 1.0) < 1e-9


def test_contradicted_evidence_can_never_be_high():
    result = confidence.score_evidence(
        reliability="first_party",
        epistemic_status="known",
        freshness="recent",
        corroborating_sources=3,
        contradicted=True,
        freshness_basis="published_at",
    )
    assert result.level != ConfidenceLevel.HIGH
    assert any("contradict" in note.lower() for note in result.notes)


def test_undated_source_is_discounted_versus_a_dated_one():
    dated = confidence.score_evidence(
        reliability="first_party",
        epistemic_status="known",
        freshness="recent",
        freshness_basis="published_at",
    )
    undated = confidence.score_evidence(
        reliability="first_party",
        epistemic_status="known",
        freshness="recent",
        freshness_basis="observed_at",
    )
    assert undated.score < dated.score
    assert any("publication date" in note for note in undated.notes)


def test_aggregate_flags_single_source_support():
    part = confidence.score_evidence(
        reliability="first_party", epistemic_status="known", freshness="recent"
    )
    result = confidence.aggregate([part], distinct_sources=1, freshness="recent")
    assert any("single source" in note for note in result.notes)


def test_aggregate_of_nothing_is_low_not_zero_division():
    result = confidence.aggregate([], distinct_sources=0, freshness="unknown")
    assert result.score == 0.0 and result.level == ConfidenceLevel.LOW
