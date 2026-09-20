"""Generic search-query generation.

Queries are produced by expanding templates with the target's own values.
There is no per-industry or per-location branching anywhere in this module:
an unknown industry behaves exactly like a known one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Applied to the target's industry, which is a bare noun like "Jewellery".
# `{term}` is the industry, `{location}` the place (city or country).
INDUSTRY_TEMPLATES_LOCATED: tuple[tuple[str, str], ...] = (
    ("companies", "{term} companies {location}"),
    ("brands", "{term} brands {location}"),
    ("business", "{term} business {location}"),
    ("stores", "{term} stores {location}"),
    ("manufacturers", "{term} manufacturers {location}"),
    ("top_list", "top {term} companies in {location}"),
)

INDUSTRY_TEMPLATES_UNLOCATED: tuple[tuple[str, str], ...] = (
    ("companies", "{term} companies"),
    ("brands", "{term} brands"),
    ("business", "{term} business"),
    ("manufacturers", "{term} manufacturers"),
)

# Applied to user-supplied keywords, which are already phrases like
# "jewellery stores" — so they are not padded with extra business nouns.
KEYWORD_TEMPLATES_LOCATED: tuple[tuple[str, str], ...] = (
    ("keyword", "{term} {location}"),
    ("keyword_site", '"{term}" {location} official website'),
)

KEYWORD_TEMPLATES_UNLOCATED: tuple[tuple[str, str], ...] = (
    ("keyword", "{term}"),
    ("keyword_site", '"{term}" official website'),
)

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class GeneratedQuery:
    query: str
    template: str


def _clean(value: str | None) -> str:
    return _WHITESPACE.sub(" ", (value or "").strip())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = _clean(value)
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


def generate_queries(
    *,
    industry: str,
    location: str | None = None,
    country: str | None = None,
    keywords: list[str] | None = None,
    search_context: str | None = None,
    max_queries: int = 12,
) -> list[GeneratedQuery]:
    """Build a deterministic, deduplicated list of search queries for a target.

    Ordering is breadth-first across templates, so a small ``max_queries``
    still covers every keyword the user supplied.
    """
    industry = _clean(industry)
    country = _clean(country)
    location = _clean(location)
    context = _clean(search_context)
    place = location or country

    if not industry and not keywords:
        return []

    keyword_terms = [term for term in _dedupe(keywords or []) if term.lower() != industry.lower()]

    industry_templates = INDUSTRY_TEMPLATES_LOCATED if place else INDUSTRY_TEMPLATES_UNLOCATED
    keyword_templates = KEYWORD_TEMPLATES_LOCATED if place else KEYWORD_TEMPLATES_UNLOCATED

    # (priority, template_name, term, template) — lower priority runs first.
    plan: list[tuple[int, str, str, str]] = []
    if industry:
        for index, (name, template) in enumerate(industry_templates):
            plan.append((index * 2, name, industry, template))
    for index, (name, template) in enumerate(keyword_templates):
        for term in keyword_terms:
            plan.append((index * 2 + 1, name, term, template))

    plan.sort(key=lambda row: row[0])

    generated: list[GeneratedQuery] = []
    seen: set[str] = set()

    def add(query: str, template_name: str) -> None:
        query = _clean(query)
        key = query.lower()
        if query and key not in seen:
            seen.add(key)
            generated.append(GeneratedQuery(query=query, template=template_name))

    for _, name, term, template in plan:
        query = template.format(term=term, location=place)
        # Free-text context widens only the primary query, so it does not
        # distort every variation.
        if context and name == "companies":
            add(f"{query} {context}", "companies_context")
        add(query, name)

    if location and country and industry:
        add(f"{industry} companies {location} {country}", "companies_country")

    return generated[:max_queries]
