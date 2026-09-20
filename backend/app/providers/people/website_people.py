"""Extracts publicly listed people from company pages.

Reads team, leadership, about and contact pages that the crawler already
retrieved. Works on patterns of the form "Name — Role" / "Role: Name", which
is how team pages are almost always written.

LinkedIn is not used, and nothing here bypasses access controls.
"""

from __future__ import annotations

import re

from app.models.enums import VerificationStatus
from app.providers.people.base import (
    DecisionMakerProvider,
    DiscoveredPerson,
    PeopleProviderStatus,
)

# Roles worth surfacing for a B2B marketing conversation, grouped so the UI
# can cluster them. Order matters: longer titles are matched first.
ROLE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("founder", r"co[-\s]?founder"),
    ("founder", r"founder"),
    ("executive", r"chief executive officer|ceo\b"),
    ("marketing", r"chief marketing officer|cmo\b"),
    ("marketing", r"(?:vp|vice president|head|director|manager|lead)\s+of\s+(?:brand|marketing|communications?|growth)"),
    ("marketing", r"(?:brand|marketing|communications?|digital marketing|growth)\s+(?:head|director|manager|lead|officer)"),
    ("marketing", r"head of marketing|marketing head|brand head"),
    ("partnerships", r"(?:partnerships?|alliances?|business development|bd)\s+(?:head|director|manager|lead)"),
    ("partnerships", r"head of (?:partnerships?|alliances?|business development)"),
    ("executive", r"managing director|md\b|chief operating officer|coo\b|president\b"),
    ("executive", r"chief (?:brand|growth|revenue|digital) officer"),
    ("regional", r"(?:regional|zonal|state|city)\s+(?:head|manager|director|marketing head)"),
)

_COMPILED = tuple((category, re.compile(pattern, re.IGNORECASE)) for category, pattern in ROLE_PATTERNS)

# A person's name as written on a team page: 2-4 capitalised words.
_NAME = r"([A-Z][a-z'’\-]{1,20}(?:\s+[A-Z][a-z'’\-]{1,20}){1,3})"

# "Priya Nair, Head of Marketing" / "Priya Nair - Marketing Head"
_NAME_THEN_ROLE = re.compile(rf"{_NAME}\s*[,\-–—|:]\s*([A-Za-z][A-Za-z &/.\-]{{2,60}})")
# "Head of Marketing: Priya Nair"
_ROLE_THEN_NAME = re.compile(rf"([A-Za-z][A-Za-z &/.\-]{{2,60}})\s*[:\-–—]\s*{_NAME}")
# "COO Sudeep Nagar" / "CEO Jane Smith" — the press convention of putting a
# short title directly before the name, with no separator.
_TITLE_THEN_NAME = re.compile(
    rf"\b(CEO|CMO|COO|CFO|CTO|MD|Managing Director|Founder|Co-?Founder|President|"
    rf"Chairman|Chairperson|Director|Head of [A-Z][a-z]+)\s+{_NAME}"
)

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_WHITESPACE = re.compile(r"\s+")

# Words that look like names to the regex but are page furniture.
_NOT_A_NAME = re.compile(
    r"^(our team|the team|about us|contact us|read more|learn more|view profile|"
    r"privacy policy|terms|home page|get in touch|follow us|social media|"
    r"all rights|copyright|new delhi|new york|"
    # Fragments that the "Title Name" pattern can otherwise capture.
    r"positions? available|job openings?|apply now|vacancies open|"
    r"roles available|opportunities available|team members?)$",
    re.IGNORECASE,
)


def _segments(text: str) -> list[str]:
    """Split page text into candidate entries.

    Team pages use line breaks and bullets, but prose pages run long: a
    2,000-character paragraph would never fall inside the length window, so
    paragraphs are split into sentences as well.
    """
    segments: list[str] = []
    for chunk in re.split(r"[\n•]+", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        if len(chunk) <= 200:
            segments.append(chunk)
            continue
        segments.extend(
            part.strip() for part in re.split(r"(?<=[.!?])\s+", chunk) if part.strip()
        )
    return segments


def _clean(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip(" ,-–—|:\t")


def _match_role(text: str) -> tuple[str, str] | None:
    """Return (category, matched role text) for the first recognised role."""
    for category, pattern in _COMPILED:
        found = pattern.search(text)
        if found:
            return category, _clean(found.group(0))
    return None


def _plausible_name(value: str) -> bool:
    value = _clean(value)
    if not 4 <= len(value) <= 60 or _NOT_A_NAME.match(value):
        return False
    words = value.split()
    if not 2 <= len(words) <= 4:
        return False
    # A role accidentally captured as a name is rejected.
    return _match_role(value) is None


class WebsitePeopleProvider(DecisionMakerProvider):
    name = "website_pages"

    async def find_people(
        self, *, company_name: str, documents: list[tuple[str, str, str]]
    ) -> list[DiscoveredPerson]:
        found: list[DiscoveredPerson] = []
        seen: set[tuple[str | None, str]] = set()

        for url, _title, text in documents:
            if not text:
                continue
            for line in _segments(text):
                if not 6 <= len(line) <= 200:
                    continue
                role_match = _match_role(line)
                if role_match is None:
                    continue
                category, role_text = role_match

                name = self._name_in(line)
                key = ((name or "").lower(), category)
                if key in seen:
                    continue
                seen.add(key)

                found.append(
                    DiscoveredPerson(
                        name=name,
                        role=role_text,
                        role_category=category,
                        # Only an address written on the page itself.
                        email=self._email_in(line),
                        profile_url=url,
                        excerpt=_clean(line)[:400],
                        source_url=url,
                        verification_status=(
                            VerificationStatus.PUBLIC_COMPANY_SOURCE
                            if name
                            else VerificationStatus.ROLE_ONLY
                        ),
                    )
                )

        return found

    def _name_in(self, line: str) -> str | None:
        for pattern, name_group in (
            (_NAME_THEN_ROLE, 1),
            (_ROLE_THEN_NAME, 2),
            (_TITLE_THEN_NAME, 2),
        ):
            match = pattern.search(line)
            if not match:
                continue
            candidate = match.group(name_group)
            if _plausible_name(candidate):
                return _clean(candidate)
        return None

    def _email_in(self, line: str) -> str | None:
        match = _EMAIL.search(line)
        return match.group(0).lower() if match else None

    async def status(self) -> PeopleProviderStatus:
        return PeopleProviderStatus(
            self.name,
            True,
            "Reads publicly listed people from already-retrieved company pages.",
        )
