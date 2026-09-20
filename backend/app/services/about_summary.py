"""Builds a short description of a company from its own pages.

Everything returned is a sentence copied verbatim from a page the company
published. Nothing is paraphrased or written by a model — the card that shows
this says "copied from their pages", and that has to be literally true.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_WHITESPACE = re.compile(r"\s+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

# Navigation, legal text and shop furniture describe no business.
_BOILERPLATE = re.compile(
    r"\b(cookie|privacy policy|terms (of|and) (use|service|conditions)|all rights reserved|"
    r"copyright|subscribe|newsletter|follow us|sign ?in|log ?in|add to cart|your cart|"
    r"javascript|read more|click here|view all|shop now|buy now|free shipping|"
    r"return policy|shipping policy|faq)\b",
    re.IGNORECASE,
)

# A sentence that describes the business usually speaks in the first person
# or names the company.
_SELF_DESCRIBING = re.compile(
    r"\b(we|our|us)\b|\b(is|are|was|were|has|have|offers?|provides?|specialis|specializ|"
    r"founded|established|serving|serves|crafts?|designs?|manufactur)\b",
    re.IGNORECASE,
)

MIN_LENGTH = 60
MAX_LENGTH = 320


@dataclass
class AboutLine:
    """One verbatim sentence, with the page it came from."""

    text: str
    source_url: str
    source_title: str | None = None

    def dict(self) -> dict:
        return asdict(self)


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for raw in _SENTENCE_SPLIT.split(text or ""):
        sentence = _WHITESPACE.sub(" ", raw).strip()
        if not MIN_LENGTH <= len(sentence) <= MAX_LENGTH:
            continue
        if _BOILERPLATE.search(sentence):
            continue
        # Mostly-symbol lines are menus and price lists, not prose.
        if sum(character.isalpha() for character in sentence) < len(sentence) * 0.6:
            continue
        out.append(sentence)
    return out


def _score(sentence: str, company_name: str, tokens: list[str]) -> int:
    """How much a sentence sounds like the company describing itself."""
    score = 0
    lowered = sentence.lower()
    if any(token in lowered for token in tokens):
        score += 3
    if re.search(r"\b(we|our)\b", lowered):
        score += 2
    if _SELF_DESCRIBING.search(sentence):
        score += 1
    # A sentence of natural length reads better than a fragment or an essay.
    if 90 <= len(sentence) <= 220:
        score += 1
    return score


def build_about(
    pages: list[tuple[str, str | None, str | None]],
    *,
    company_name: str,
    tokens: list[str],
    limit: int = 3,
) -> list[AboutLine]:
    """Pick the sentences that best describe the business.

    ``pages`` is ``(url, title, content)`` for the company's own pages only:
    a third-party page describes someone else's view, or someone else.
    """
    scored: list[tuple[int, AboutLine]] = []
    seen: set[str] = set()

    for url, title, content in pages:
        if not content:
            continue
        for sentence in _sentences(content):
            key = sentence.lower()[:80]
            if key in seen:
                continue
            value = _score(sentence, company_name, tokens)
            # Require some sign it is about this company, not generic filler.
            if value < 3:
                continue
            seen.add(key)
            scored.append((value, AboutLine(text=sentence, source_url=url, source_title=title)))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [line for _, line in scored[:limit]]
