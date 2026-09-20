"""Turn raw search results into deduplicated company candidates.

Pure and side-effect free so the rules are directly unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.providers.search.base import SearchResultItem
from app.services.normalization import (
    derive_company_name,
    extract_domain,
    is_excluded_domain,
    is_probable_document,
    normalize_url,
    root_url,
)

REJECT_INVALID_URL = "invalid_url"
REJECT_EXCLUDED_DOMAIN = "excluded_domain"
REJECT_DOCUMENT = "document_or_asset"


@dataclass
class CandidateEvidence:
    url: str
    title: str | None
    snippet: str | None
    source_engine: str | None
    discovered_at: datetime
    result_index: int


@dataclass
class CompanyCandidate:
    """One prospective company, keyed on its canonical domain."""

    domain: str
    name: str
    website_url: str
    evidence: list[CandidateEvidence] = field(default_factory=list)


@dataclass
class ResultDecision:
    """Per-result outcome, mirrored onto the stored ``search_results`` row."""

    result_index: int
    accepted: bool
    domain: str | None = None
    rejection_reason: str | None = None


@dataclass
class CandidateExtraction:
    candidates: list[CompanyCandidate]
    decisions: list[ResultDecision]

    @property
    def rejected_count(self) -> int:
        return sum(1 for decision in self.decisions if not decision.accepted)


def extract_candidates(results: list[SearchResultItem]) -> CandidateExtraction:
    """Group search results by canonical domain, discarding non-company hits.

    Deduplication is domain-based only. Companies are never merged on name
    similarity, which would wrongly collapse distinct businesses.
    """
    candidates: dict[str, CompanyCandidate] = {}
    decisions: list[ResultDecision] = []

    for index, item in enumerate(results):
        normalized = normalize_url(item.url)
        if not normalized:
            decisions.append(ResultDecision(index, False, rejection_reason=REJECT_INVALID_URL))
            continue

        domain = extract_domain(normalized)
        if not domain:
            decisions.append(ResultDecision(index, False, rejection_reason=REJECT_INVALID_URL))
            continue

        if is_excluded_domain(domain):
            decisions.append(
                ResultDecision(index, False, domain=domain, rejection_reason=REJECT_EXCLUDED_DOMAIN)
            )
            continue

        if is_probable_document(normalized):
            decisions.append(
                ResultDecision(index, False, domain=domain, rejection_reason=REJECT_DOCUMENT)
            )
            continue

        evidence = CandidateEvidence(
            url=normalized,
            title=item.title,
            snippet=item.snippet,
            source_engine=item.source_engine,
            discovered_at=item.discovered_at,
            result_index=index,
        )

        candidate = candidates.get(domain)
        if candidate is None:
            candidates[domain] = CompanyCandidate(
                domain=domain,
                name=derive_company_name(item.title, domain),
                website_url=root_url(normalized) or normalized,
                evidence=[evidence],
            )
        else:
            candidate.evidence.append(evidence)

        decisions.append(ResultDecision(index, True, domain=domain))

    return CandidateExtraction(candidates=list(candidates.values()), decisions=decisions)
